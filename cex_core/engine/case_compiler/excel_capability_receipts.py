# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/excel_capability_receipts.py（sha256 5ed8806dce20ec4d）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from cex_core.engine.case_compiler._sealed_io import canonical_json as _sealed_canonical_json, lexical_absolute as _lexical_absolute, open_directory_nofollow, read_regular_at_nofollow, sha256_bytes as _sha256_bytes, validate_json_budget
SCHEMA = 'ist.excel.capability-certification'
RUNTIME_VERSION = 'ist.excel.runtime'
_HEX_RE = re.compile('^[0-9a-f]{64}$')
_PHASES = frozenset({'certification', 'release'})
_VERDICTS = frozenset({'pass', 'fail', 'unavailable'})
_CLEANUP = frozenset({'pass', 'fail', 'unavailable', 'not_required'})
_ROOT = _cex_data_path('')
_DEFAULT_TRUSTED_ROOT = _ROOT / 'runtime' / 'excel_capability_receipts'
_MAX_RECEIPT_FILES = 4096
_MAX_RECEIPT_BYTES = 512 * 1024

class ExcelCapabilityReceiptError(ValueError):
    pass

@dataclass(frozen=True)
class ValidatedReceiptSet:
    receipts: tuple[dict[str, Any], ...]
    receipt_set_sha256: str
    phase: str

def _canonical_json(value: Any) -> bytes:
    return _sealed_canonical_json(value, ensure_ascii=True)

def _require_sha(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not _HEX_RE.fullmatch(value):
        raise ExcelCapabilityReceiptError(f'{label} must be a SHA-256 hex digest')
    return value

def _require_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or '\x00' in value or any((ord(char) < 32 for char in value)):
        raise ExcelCapabilityReceiptError(f'{label} must be non-empty safe text')
    return value

def receipt_sha256(receipt: Mapping[str, Any]) -> str:
    body = dict(receipt)
    body.pop('receipt_sha256', None)
    return _sha256_bytes(_canonical_json(body))

def source_closure_sha256(contract: Mapping[str, Any]) -> str:
    hashes = contract.get('source_hashes')
    if not isinstance(hashes, Mapping) or not hashes:
        raise ExcelCapabilityReceiptError('contract source hash closure is unavailable')
    normalized: dict[str, str] = {}
    for path, digest in hashes.items():
        if not isinstance(path, str) or not path or path.startswith('/') or ('..' in Path(path).parts):
            raise ExcelCapabilityReceiptError('contract source path is unsafe')
        normalized[path] = _require_sha(digest, label=f'source {path}')
    return _sha256_bytes(_canonical_json(normalized))

def _object(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExcelCapabilityReceiptError(f'{label} must be an object')
    return value

def _entry_for_receipt(contract: Mapping[str, Any], capability: Mapping[str, Any]) -> Mapping[str, Any]:
    e_value = _require_text(capability.get('e'), label='capability.e')
    f_value = _require_text(capability.get('f'), label='capability.f')
    symbol = _require_text(capability.get('python_symbol'), label='capability.python_symbol')
    matches = [entry for entry in contract.get('entries', []) if isinstance(entry, Mapping) and entry.get('e') == e_value and (entry.get('f') == f_value) and (entry.get('python_symbol') == symbol)]
    if len(matches) != 1:
        raise ExcelCapabilityReceiptError('receipt has no unique E/F contract binding')
    return matches[0]

def _action_for_receipt(contract: Mapping[str, Any], capability: Mapping[str, Any]) -> Mapping[str, Any]:
    e_value = _require_text(capability.get('e'), label='capability.e')
    dispatcher = _require_text(capability.get('dispatcher'), label='capability.dispatcher')
    normalized = _require_text(capability.get('normalized'), label='capability.normalized')
    canonical = _require_text(capability.get('canonical'), label='capability.canonical')
    symbol = _require_text(capability.get('python_symbol'), label='capability.python_symbol')
    matches = [action for action in contract.get('execute_actions', []) if isinstance(action, Mapping) and action.get('dispatcher') == dispatcher and (action.get('normalized') == normalized) and (action.get('canonical') == canonical) and (action.get('python_symbol') == symbol) and (e_value in (action.get('allowed_es') or []))]
    if len(matches) != 1:
        raise ExcelCapabilityReceiptError('receipt has no unique execute action/E contract binding')
    return matches[0]

def validate_capability_receipt(raw: Mapping[str, Any], *, contract: Mapping[str, Any], phase: str, contract_file_sha256: str, deployment_receipt_sha256: str) -> dict[str, Any]:
    if phase not in _PHASES:
        raise ExcelCapabilityReceiptError('unknown receipt phase')
    receipt = dict(raw)
    from cex_core.engine.common.schema_identity import accepts_schema
    if not accepts_schema(receipt.get('schema'), SCHEMA) or receipt.get('phase') != phase:
        raise ExcelCapabilityReceiptError('receipt schema or phase mismatch')
    stored = _require_sha(receipt.get('receipt_sha256'), label='receipt_sha256')
    if receipt_sha256(receipt) != stored:
        raise ExcelCapabilityReceiptError('receipt canonical digest mismatch')
    status = receipt.get('status')
    if status not in _VERDICTS:
        raise ExcelCapabilityReceiptError('receipt status is invalid')
    contract_info = _object(receipt.get('contract'), label='contract')
    basis_sha = _require_sha(contract_info.get('basis_sha256'), label='contract.basis_sha256')
    observed_sha = _require_sha(contract_info.get('observed_sha256'), label='contract.observed_sha256')
    expected_contract_sha = _require_sha(contract.get('contract_sha256'), label='contract.contract_sha256')
    if not accepts_schema(contract_info.get('runtime_version'), RUNTIME_VERSION) or _require_sha(contract_info.get('contract_file_sha256'), label='contract.contract_file_sha256') != _require_sha(contract_file_sha256, label='expected contract file'):
        raise ExcelCapabilityReceiptError('receipt contract file/runtime identity mismatch')
    if phase == 'certification':
        if basis_sha != expected_contract_sha or observed_sha != expected_contract_sha:
            raise ExcelCapabilityReceiptError('certification receipt does not observe the basis contract')
    else:
        certification = contract.get('certification')
        expected_basis_sha = certification.get('basis_contract_sha256') if isinstance(certification, Mapping) else expected_contract_sha
        if basis_sha != expected_basis_sha or observed_sha != expected_contract_sha:
            raise ExcelCapabilityReceiptError('release receipt does not bind the basis/final contract identity')
    source = _object(receipt.get('source'), label='source')
    closure_sha = source_closure_sha256(contract)
    if _require_sha(source.get('closure_sha256'), label='source.closure_sha256') != closure_sha or _require_sha(source.get('remote_closure_sha256'), label='source.remote_closure_sha256') != closure_sha or _require_sha(source.get('runner_sha256'), label='source.runner_sha256') != contract.get('runtime', {}).get('runner_sha256') or (_require_sha(source.get('deployment_receipt_sha256'), label='source.deployment_receipt_sha256') != _require_sha(deployment_receipt_sha256, label='expected deployment receipt')):
        raise ExcelCapabilityReceiptError('receipt source/deployment closure mismatch')
    environment = _object(receipt.get('environment'), label='environment')
    for field in ('environment_id', 'bed_lease_id', 'host_key_sha256'):
        _require_text(environment.get(field), label=f'environment.{field}')
    _require_sha(environment.get('facts_sha256'), label='environment.facts_sha256')
    if not str(environment['host_key_sha256']).startswith('SHA256:'):
        raise ExcelCapabilityReceiptError('environment host key fingerprint is invalid')
    device = _object(receipt.get('device'), label='device')
    _require_sha(device.get('device_id_sha256'), label='device.device_id_sha256')
    _require_sha(device.get('facts_sha256'), label='device.facts_sha256')
    _require_text(device.get('os_build'), label='device.os_build')
    _require_text(device.get('module'), label='device.module')
    capability = _object(receipt.get('capability'), label='capability')
    kind = capability.get('kind')
    if kind == 'entry':
        target = _entry_for_receipt(contract, capability)
    elif kind == 'execute_action':
        target = _action_for_receipt(contract, capability)
    else:
        raise ExcelCapabilityReceiptError('receipt capability kind is invalid')
    source_info = _object(target.get('source'), label='capability source')
    source_path = source_info.get('path')
    expected_source_sha = contract.get('source_hashes', {}).get(source_path)
    if _require_sha(capability.get('source_file_sha256'), label='capability.source_file_sha256') != expected_source_sha:
        raise ExcelCapabilityReceiptError('receipt capability source SHA mismatch')
    sample = _object(receipt.get('sample'), label='sample')
    _require_text(sample.get('sample_id'), label='sample.sample_id')
    for field in ('sample_manifest_sha256', 'g_sha256', 'artifact_sha256', 'remote_artifact_sha256'):
        _require_sha(sample.get(field), label=f'sample.{field}')
    if sample['artifact_sha256'] != sample['remote_artifact_sha256']:
        raise ExcelCapabilityReceiptError('local/remote sample artifact SHA mismatch')
    run = _object(receipt.get('run'), label='run')
    _require_text(run.get('run_id'), label='run.run_id')
    verdict = run.get('verdict')
    cleanup = run.get('cleanup_verdict')
    if verdict not in _VERDICTS or verdict != status or cleanup not in _CLEANUP:
        raise ExcelCapabilityReceiptError('receipt run verdict is inconsistent')
    _require_sha(run.get('evidence_sha256'), label='run.evidence_sha256')
    _require_sha(run.get('cleanup_evidence_sha256'), label='run.cleanup_evidence_sha256')
    if phase == 'certification' and kind == 'execute_action' and (cleanup != 'pass'):
        raise ExcelCapabilityReceiptError('execute action certification requires verified cleanup')
    return json.loads(json.dumps(receipt, ensure_ascii=True))

def validate_receipt_set(raw_receipts: Iterable[Mapping[str, Any]], *, contract: Mapping[str, Any], phase: str, contract_file_sha256: str, deployment_receipt_sha256: str) -> ValidatedReceiptSet:
    receipts: list[dict[str, Any]] = []
    seen_sha: set[str] = set()
    seen_run: set[tuple[str, ...]] = set()
    for raw in raw_receipts:
        receipt = validate_capability_receipt(raw, contract=contract, phase=phase, contract_file_sha256=contract_file_sha256, deployment_receipt_sha256=deployment_receipt_sha256)
        digest = receipt['receipt_sha256']
        capability = receipt['capability']
        identity = (phase, str(capability.get('kind') or ''), str(capability.get('e') or ''), str(capability.get('f') or ''), str(capability.get('dispatcher') or ''), str(capability.get('normalized') or ''), str(receipt['sample']['sample_id']), str(receipt['run']['run_id']))
        if digest in seen_sha or identity in seen_run:
            raise ExcelCapabilityReceiptError('duplicate capability receipt identity')
        seen_sha.add(digest)
        seen_run.add(identity)
        receipts.append(receipt)
    if not receipts:
        raise ExcelCapabilityReceiptError('capability receipt set is empty')
    receipts.sort(key=lambda item: item['receipt_sha256'])
    aggregate = _sha256_bytes(_canonical_json([item['receipt_sha256'] for item in receipts]))
    return ValidatedReceiptSet(tuple(receipts), aggregate, phase)

def _secure_receipt_directory(path: Path, trusted_root: Path) -> tuple[Path, int]:
    root = _lexical_absolute(trusted_root)
    selected = _lexical_absolute(path)
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise ExcelCapabilityReceiptError('receipt directory escapes the trusted root') from exc
    return (selected, open_directory_nofollow(selected, error_type=ExcelCapabilityReceiptError, invalid_message='receipt directory path is invalid', unavailable_message='receipt directory cannot be opened without following symlinks'))

def _read_receipt_file_at(directory_fd: int, name: str) -> bytes:
    if not name.endswith('.json') or name in {'.', '..'} or '/' in name or ('\\' in name):
        raise ExcelCapabilityReceiptError(f'receipt directory contains a non-JSON file: {name!r}')
    return read_regular_at_nofollow(directory_fd, name, error_type=ExcelCapabilityReceiptError, open_message='capability receipt file cannot be opened safely', bounds_message='capability receipt must be a bounded single-link regular file', changed_message='capability receipt changed while being read', max_bytes=_MAX_RECEIPT_BYTES, min_bytes=1, chunk_bytes=64 * 1024)

def load_receipt_directory(directory: str | Path, *, contract: Mapping[str, Any], phase: str, contract_file_sha256: str, deployment_receipt_sha256: str, trusted_root: str | Path=_DEFAULT_TRUSTED_ROOT) -> ValidatedReceiptSet:
    _selected, directory_fd = _secure_receipt_directory(Path(directory), Path(trusted_root))
    raw_receipts: list[Mapping[str, Any]] = []
    try:
        names = sorted((n for n in os.listdir(directory_fd) if not n.startswith('.')))
        if len(names) > _MAX_RECEIPT_FILES:
            raise ExcelCapabilityReceiptError('capability receipt directory exceeds the file-count limit')
        for name in names:
            raw = _read_receipt_file_at(directory_fd, name)
            try:
                validate_json_budget(raw, error_type=ExcelCapabilityReceiptError, message='capability receipt exceeds the JSON structure budget')
                text = raw.decode('utf-8')
                payload = json.loads(text)
            except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
                raise ExcelCapabilityReceiptError('capability receipt JSON is unreadable') from exc
            if not isinstance(payload, Mapping):
                raise ExcelCapabilityReceiptError('capability receipt JSON is not an object')
            raw_receipts.append(payload)
    finally:
        os.close(directory_fd)
    return validate_receipt_set(raw_receipts, contract=contract, phase=phase, contract_file_sha256=contract_file_sha256, deployment_receipt_sha256=deployment_receipt_sha256)

def _capability_group(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    capability = receipt['capability']
    if capability['kind'] == 'entry':
        return ('entry', capability['e'], capability['f'], capability['python_symbol'])
    return ('execute_action', capability['e'], capability['dispatcher'], capability['canonical'], capability['python_symbol'])

def passed_receipt_groups(receipt_set: ValidatedReceiptSet) -> dict[tuple[str, ...], tuple[str, ...]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = {}
    for receipt in receipt_set.receipts:
        grouped.setdefault(_capability_group(receipt), []).append(receipt)
    passed: dict[tuple[str, ...], tuple[str, ...]] = {}
    for key, items in grouped.items():
        verdicts = {item['status'] for item in items}
        if verdicts == {'pass'}:
            passed[key] = tuple(sorted((item['receipt_sha256'] for item in items)))
    return passed

def validate_release_coverage(receipt_set: ValidatedReceiptSet, contract: Mapping[str, Any]) -> dict[str, Any]:
    if receipt_set.phase != 'release':
        raise ExcelCapabilityReceiptError('release coverage requires release receipts')
    passed = passed_receipt_groups(receipt_set)
    missing_entries: list[str] = []
    for entry in contract.get('entries', []):
        if not isinstance(entry, Mapping) or entry.get('status') != 'enabled':
            continue
        if entry.get('dispatch') == 'execute_registry':
            continue
        key = ('entry', entry['e'], entry['f'], entry['python_symbol'])
        if key not in passed:
            missing_entries.append(f"{entry['e']}::{entry['f']}")
    enabled_execute_es = {entry['e'] for entry in contract.get('entries', []) if isinstance(entry, Mapping) and entry.get('status') == 'enabled' and (entry.get('dispatch') == 'execute_registry')}
    required_actions: set[tuple[str, ...]] = set()
    for action in contract.get('execute_actions', []):
        if not isinstance(action, Mapping) or action.get('status') != 'enabled':
            continue
        for e_value in action.get('allowed_es', []):
            if e_value not in enabled_execute_es:
                continue
            required_actions.add(('execute_action', e_value, action['dispatcher'], action['canonical'], action['python_symbol']))
    missing_actions = sorted(('::'.join(key[1:]) for key in required_actions if key not in passed))
    if missing_entries or missing_actions:
        raise ExcelCapabilityReceiptError(f'release receipt coverage is incomplete: entries={len(missing_entries)}, actions={len(missing_actions)}')
    return {'schema': 'ist.excel.capability-release-set', 'contract_sha256': contract['contract_sha256'], 'receipt_set_sha256': receipt_set.receipt_set_sha256, 'receipt_count': len(receipt_set.receipts), 'enabled_entry_count': sum((1 for item in contract.get('entries', []) if isinstance(item, Mapping) and item.get('status') == 'enabled')), 'enabled_action_binding_count': len(required_actions)}
__all__ = ['SCHEMA', 'RUNTIME_VERSION', 'ExcelCapabilityReceiptError', 'ValidatedReceiptSet', 'receipt_sha256', 'source_closure_sha256', 'validate_capability_receipt', 'validate_receipt_set', 'load_receipt_directory', 'passed_receipt_groups', 'validate_release_coverage']
