# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/ssl_lifecycle_contract.py（sha256 e0551b5573e4d643）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import re
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow, sha256_bytes, validate_json_budget
SCHEMA = 'ist.ssl-lifecycle-contract-source'
_ROOT = _cex_data_path('')
_ASSET_ROOT = _ROOT / 'scripts' / 'maintenance' / 'assets'
_SOURCE = _ASSET_ROOT / 'ssl_lifecycle_contract.json'
_HASH_RE = re.compile('[0-9a-f]{64}')
_MAX_JSON_BYTES = 256 * 1024
_MAX_REFERENCE_BYTES = 8 * 1024 * 1024

class SSLLifecycleContractError(RuntimeError):
    pass

def _read(path: Path, *, root: Path, max_bytes: int, label: str) -> bytes:
    return read_regular_nofollow(path, error_type=SSLLifecycleContractError, invalid_message=f'{label} path is invalid', directory_message=f'{label} parent is unavailable', open_message=f'{label} is unavailable', bounds_message=f'{label} exceeds its sealed size boundary', changed_message=f'{label} changed while being read', max_bytes=max_bytes, min_bytes=2, trusted_root=root)

def _build_suffix(value: str) -> str:
    match = re.search('(?:^|[._-])(\\d+)$', str(value or '').strip())
    return match.group(1) if match else str(value or '').strip()

def _hash_field(value: object, *, label: str) -> str:
    text = str(value or '')
    if not _HASH_RE.fullmatch(text):
        raise SSLLifecycleContractError(f'{label} is not a SHA-256 digest')
    return text

def _load_source_payload() -> tuple[dict[str, Any], bytes]:
    raw = _read(_SOURCE, root=_ASSET_ROOT, max_bytes=_MAX_JSON_BYTES, label='SSL lifecycle evidence')
    validate_json_budget(raw, error_type=SSLLifecycleContractError, message='SSL lifecycle evidence exceeds its JSON structure boundary', max_depth=32, max_tokens=20000)
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SSLLifecycleContractError('SSL lifecycle evidence is not valid JSON') from exc
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA:
        raise SSLLifecycleContractError('SSL lifecycle evidence schema mismatch')
    contracts = payload.get('contracts')
    if not isinstance(contracts, list) or any((not isinstance(item, dict) for item in contracts)):
        raise SSLLifecycleContractError('SSL lifecycle contract list is invalid')
    return (payload, raw)

def ssl_lifecycle_contract_declares_build(device_build: str) -> bool:
    requested = _build_suffix(device_build)
    if not requested:
        return False
    payload, _raw = _load_source_payload()
    matches = [item for item in payload['contracts'] if _build_suffix(str(item.get('device_build') or '')) == requested]
    if len(matches) > 1:
        raise SSLLifecycleContractError(f'SSL lifecycle evidence has {len(matches)} contracts for build {requested}')
    return len(matches) == 1

def load_ssl_lifecycle_contract(device_build: str, *, verify_command_tree_receipts: bool=True) -> dict[str, Any]:
    requested = _build_suffix(device_build)
    if not requested:
        raise SSLLifecycleContractError('device build is not bound')
    payload, raw = _load_source_payload()
    matches = [item for item in payload.get('contracts', []) if isinstance(item, dict) and _build_suffix(str(item.get('device_build') or '')) == requested]
    if len(matches) != 1:
        raise SSLLifecycleContractError(f'SSL lifecycle evidence has {len(matches)} contracts for build {requested}')
    contract = dict(matches[0])
    required = contract.get('required_virtual_heads')
    create_head = str(contract.get('ssl_host_create_head') or '').strip()
    start_head = str(contract.get('ssl_host_start_head') or '').strip()
    cleanup_head = str(contract.get('ssl_host_cleanup_head') or '').strip()
    if not isinstance(required, list) or not required or any((not isinstance(head, str) or not head.strip() for head in required)) or (not create_head) or (not start_head) or (not cleanup_head):
        raise SSLLifecycleContractError('SSL lifecycle role map is incomplete')
    required_heads = sorted({head.strip() for head in required})
    device = contract.get('device_evidence')
    reference = contract.get('reference_evidence')
    if not isinstance(device, dict) or not isinstance(reference, dict):
        raise SSLLifecycleContractError('SSL lifecycle evidence receipts are incomplete')
    if _build_suffix(str(device.get('execution_build') or '')) != requested:
        raise SSLLifecycleContractError('device evidence build identity drift')
    for field in ('framework_result_source_sha256', 'framework_reference_source_sha256', 'last_run_sha256', 'raw_echo_sha256', 'volume_artifact_sha256'):
        _hash_field(device.get(field), label=f'device_evidence.{field}')
    clear_relative = str(reference.get('clear_source') or '')
    start_manual_relative = str(reference.get('start_manual_source') or '')
    atlas_relative = str(reference.get('teardown_atlas') or '')
    clear_path = _ROOT / clear_relative
    start_manual_path = _ROOT / start_manual_relative
    atlas_path = _ROOT / atlas_relative
    clear_raw = _read(clear_path, root=_ROOT, max_bytes=_MAX_REFERENCE_BYTES, label='reference cleanup source')
    atlas_raw = _read(atlas_path, root=_ROOT, max_bytes=128 * 1024 * 1024, label='command teardown atlas')
    start_manual_raw = _read(start_manual_path, root=_ROOT, max_bytes=_MAX_REFERENCE_BYTES, label='SSL start manual source')
    if sha256_bytes(clear_raw) != _hash_field(reference.get('clear_source_sha256'), label='reference_evidence.clear_source_sha256'):
        raise SSLLifecycleContractError('reference cleanup source identity drift')
    if sha256_bytes(start_manual_raw) != _hash_field(reference.get('start_manual_source_sha256'), label='reference_evidence.start_manual_source_sha256'):
        raise SSLLifecycleContractError('SSL start manual source identity drift')
    cleanup_line = reference.get('cleanup_line')
    lines = clear_raw.decode('utf-8').splitlines()
    if not isinstance(cleanup_line, int) or cleanup_line < 1 or cleanup_line > len(lines) or (cleanup_head not in lines[cleanup_line - 1]):
        raise SSLLifecycleContractError('reference cleanup source no longer carries the object-scoped command')
    start_manual_line = reference.get('start_manual_line')
    start_manual_lines = start_manual_raw.decode('utf-8').splitlines()
    if not isinstance(start_manual_line, int) or start_manual_line < 1 or start_manual_line > len(start_manual_lines) or (start_head not in start_manual_lines[start_manual_line - 1]):
        raise SSLLifecycleContractError('manual source no longer carries the SSL host start requirement')
    try:
        atlas = json.loads(atlas_raw.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SSLLifecycleContractError('command teardown atlas is invalid') from exc
    atlas_identity = (atlas.get('identity') or {}).get('sha256')
    if _hash_field(atlas_identity, label='command_teardown_atlas.identity.sha256') != _hash_field(reference.get('teardown_atlas_identity_sha256'), label='reference_evidence.teardown_atlas_identity_sha256'):
        raise SSLLifecycleContractError('command teardown atlas identity drift')
    if str(atlas.get('device_build') or '') != requested:
        raise SSLLifecycleContractError('command teardown atlas build identity drift')
    commands = atlas.get('commands')
    if not isinstance(commands, dict):
        raise SSLLifecycleContractError('command teardown atlas has no command map')
    create_entry = commands.get(create_head)
    if not isinstance(create_entry, dict):
        raise SSLLifecycleContractError('SSL host creation head is absent from the atlas')
    if not isinstance(commands.get(start_head), dict):
        raise SSLLifecycleContractError('SSL host start head is absent from the atlas')
    if str((create_entry.get('provenance') or {}).get('clear_rule') or '') != str(reference.get('create_clear_rule_ref') or ''):
        raise SSLLifecycleContractError('SSL host creation/cleanup reference drift')
    for head in required_heads:
        if not isinstance(commands.get(head), dict):
            raise SSLLifecycleContractError(f'certificate-required virtual head is absent from the atlas: {head!r}')
    receipts: dict[str, dict[str, str]] = {}
    if verify_command_tree_receipts:
        from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import build_command_tree_resolver
        _vendor, _inventory, resolve = build_command_tree_resolver(device_build=requested)
        for role, heads in (('required_virtual', required_heads), ('ssl_host_create', [create_head]), ('ssl_host_start', [start_head]), ('ssl_host_cleanup', [cleanup_head])):
            for head in heads:
                verdict = resolve(head)
                if verdict.get('kind') != 'hit' or str(verdict.get('head') or '') != head or str(verdict.get('device_build') or '') != requested or (str(verdict.get('origin') or '') != 'vendor_xml'):
                    raise SSLLifecycleContractError(f'{role} head does not resolve exactly in build {requested}: {head!r}')
                receipts[head] = {'role': role, 'src': str(verdict.get('src') or ''), 'origin': str(verdict.get('origin') or '')}
    else:
        for role, heads in (('required_virtual', required_heads), ('ssl_host_create', [create_head]), ('ssl_host_start', [start_head])):
            for head in heads:
                entry = commands.get(head)
                xml_sources = list((entry or {}).get('xml', {}).get('src') or [])
                if not isinstance(entry, dict) or str(entry.get('origin') or '') != 'vendor_xml' or (not xml_sources):
                    raise SSLLifecycleContractError(f'{role} head is not sealed by the verified atlas: {head!r}')
                receipts[head] = {'role': role, 'src': str(xml_sources[0]), 'origin': 'vendor_xml'}
        receipts[cleanup_head] = {'role': 'ssl_host_cleanup', 'src': f'{clear_relative}:{cleanup_line}', 'origin': 'reference_clear_source'}
    return {'schema': SCHEMA, 'device_build': requested, 'required_virtual_heads': required_heads, 'ssl_host_create_head': create_head, 'ssl_host_start_head': start_head, 'ssl_host_cleanup_head': cleanup_head, 'preflight_transition_coverage': {start_head: create_head}, 'source_sha256': sha256_bytes(raw), 'receipts': receipts, 'device_evidence': dict(device), 'reference_evidence': dict(reference)}
__all__ = ['SCHEMA', 'SSLLifecycleContractError', 'load_ssl_lifecycle_contract', 'ssl_lifecycle_contract_declares_build']
