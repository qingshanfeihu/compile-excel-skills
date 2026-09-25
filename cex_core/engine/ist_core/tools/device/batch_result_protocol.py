# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/batch_result_protocol.py（sha256 fe306d5203f9f421）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import re
from typing import Any
SCHEMA = 'ist.device-batch-result'
PREREQUISITE_RECEIPT_SCHEMA = 'ist.device-prerequisite-receipt'
FAILURE_EVIDENCE_SCHEMA = 'ist.device-batch-failure-evidence'
STATUSES = frozenset({'completed', 'device_busy', 'env_pool_exhausted', 'failed'})
REASON_CODES = frozenset({'completed', 'device_busy', 'env_pool_exhausted', 'invalid_request', 'environment_unavailable', 'device_unreachable', 'device_prerequisite_unmet', 'bed_identity_mismatch', 'artifact_identity_mismatch', 'delivery_failed', 'execution_failed', 'session_desync', 'result_channel_unavailable', 'producer_protocol_error'})
VERDICTS = frozenset({'pass', 'fail', 'broken', 'unknown'})
ATTRIBUTIONS = frozenset({'grammar_rejected', 'unattributed'})
_AUTOID_RE = re.compile('\\d{18}')
_SHA256_RE = re.compile('[0-9a-f]{64}')
_TASK_ID_RE = re.compile('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
_MAX_BYTES = 2 * 1024 * 1024
MAX_ERROR_TEXT_CHARS = 1200
_TOP_KEYS = {'schema', 'status', 'reason_code', 'reason_zh', 'error_text', 'bed_host', 'last_run_path', 'counts', 'alerts', 'run_identity', 'runtime_reverification', 'cross_run', 'crash_analysis', 'verdicts', 'guidance', 'prerequisite_receipts', 'failure_evidence'}
_COUNT_KEYS = {'total', 'pass', 'fail', 'broken', 'unknown', 'grammar_rejected', 'unattributed'}
_ALERT_KEYS = {'verified_runs_write_failed', 'frozen_write_failed_autoids'}
_IDENTITY_KEYS = {'run_id', 'artifact_sha256', 'bed_lease_id', 'build', 'module'}
_REVERIFY_KEYS = {'autoid', 'raw_device_verdict', 'effective_verdict', 'status', 'reason', 'completion_state'}
_CROSS_RUN_KEYS = {'repeat_autoids', 'transient_recur_autoids'}
_VERDICT_KEYS = {'autoid', 'verdict', 'attribution', 'reflow', 'note'}
_PREREQUISITE_RECEIPT_KEYS = {'schema', 'autoid', 'artifact_sha256', 'bed_host', 'run_id', 'reason_code'}
_FAILURE_EVIDENCE_KEYS = {'schema', 'autoid', 'task_id', 'layer', 'state', 'source', 'settle_attempts', 'error_type', 'evidence_file', 'evidence_sha256'}

def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'duplicate JSON key: {key}')
        out[key] = value
    return out

def _reject_constant(value: str) -> None:
    raise ValueError(f'non-finite JSON constant: {value}')

def _exact_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unknown = sorted(set(value) - expected)
        raise ValueError(f'{label} keys mismatch; missing={missing}, unknown={unknown}')

def _text(value: Any, *, label: str, nullable: bool=False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text{(' or null' if nullable else '')}")

def _autoid_array(value: Any, *, label: str) -> None:
    if not isinstance(value, list) or any((not isinstance(item, str) or not _AUTOID_RE.fullmatch(item) for item in value)):
        raise ValueError(f'{label} must be an array of 18-digit autoids')

def validate_device_prerequisite_receipts(receipts: Any, *, expected_autoids: set[str] | frozenset[str] | None=None, artifact_sha256: str='', bed_host: str='', run_id: str='', require_nonempty: bool=True) -> list[dict[str, str]]:
    if not isinstance(receipts, list):
        raise ValueError('device prerequisite receipts must be an array')
    if require_nonempty and (not receipts):
        raise ValueError('device prerequisite receipt is required')
    normalized: list[dict[str, str]] = []
    seen_autoids: set[str] = set()
    for index, receipt in enumerate(receipts):
        label = f'prerequisite_receipts[{index}]'
        if not isinstance(receipt, dict):
            raise ValueError(f'{label} must be an object')
        _exact_keys(receipt, _PREREQUISITE_RECEIPT_KEYS, label=label)
        if receipt.get('schema') != PREREQUISITE_RECEIPT_SCHEMA:
            raise ValueError('invalid device prerequisite receipt schema')
        autoid = receipt.get('autoid')
        if not isinstance(autoid, str) or not _AUTOID_RE.fullmatch(autoid):
            raise ValueError('device prerequisite receipt autoid is invalid')
        if autoid in seen_autoids:
            raise ValueError('device prerequisite receipt autoids must be unique')
        seen_autoids.add(autoid)
        artifact = receipt.get('artifact_sha256')
        if not isinstance(artifact, str) or not _SHA256_RE.fullmatch(artifact):
            raise ValueError('device prerequisite receipt artifact is invalid')
        for key in ('bed_host', 'run_id'):
            value = receipt.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"device prerequisite receipt {key.removesuffix('_host')} is invalid")
        if receipt.get('reason_code') != 'device_prerequisite_unmet':
            raise ValueError('invalid device prerequisite receipt reason_code')
        if expected_autoids is not None and autoid not in expected_autoids:
            raise ValueError('device prerequisite receipt autoid binding mismatch')
        if artifact_sha256 and artifact != artifact_sha256:
            raise ValueError('device prerequisite receipt artifact binding mismatch')
        if bed_host and receipt.get('bed_host') != bed_host:
            raise ValueError('device prerequisite receipt bed binding mismatch')
        if run_id and receipt.get('run_id') != run_id:
            raise ValueError('device prerequisite receipt run binding mismatch')
        normalized.append({key: str(receipt[key]) for key in sorted(receipt)})
    return normalized

def device_prerequisite_receipt_sha256(receipt: dict[str, Any]) -> str:
    normalized = validate_device_prerequisite_receipts([receipt])[0]
    canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()

def validate_device_failure_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError('device failure evidence must be an array')
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        label = f'failure_evidence[{index}]'
        if not isinstance(item, dict):
            raise ValueError(f'{label} must be an object')
        _exact_keys(item, _FAILURE_EVIDENCE_KEYS, label=label)
        if item.get('schema') != FAILURE_EVIDENCE_SCHEMA:
            raise ValueError('invalid device failure evidence schema')
        autoid = item.get('autoid')
        if not isinstance(autoid, str) or not _AUTOID_RE.fullmatch(autoid):
            raise ValueError('device failure evidence autoid is invalid')
        if autoid in seen:
            raise ValueError('device failure evidence autoids must be unique')
        seen.add(autoid)
        task_id = item.get('task_id')
        if not isinstance(task_id, str) or _TASK_ID_RE.fullmatch(task_id) is None or '..' in task_id:
            raise ValueError('device failure evidence task_id is invalid')
        if item.get('layer') != 'framework_result_channel' or item.get('state') not in {'query_error', 'missing_after_done'} or item.get('source') != 'mysql':
            raise ValueError('device failure evidence channel identity is invalid')
        attempts = item.get('settle_attempts')
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
            raise ValueError('device failure evidence settle_attempts is invalid')
        error_type = item.get('error_type')
        if not isinstance(error_type, str) or len(error_type) > 120:
            raise ValueError('device failure evidence error_type is invalid')
        evidence_file = item.get('evidence_file')
        evidence_sha256 = item.get('evidence_sha256')
        if not isinstance(evidence_file, str) or evidence_file not in {'', 'device_echo.raw.txt'} or (not isinstance(evidence_sha256, str)) or (evidence_sha256 != '' and (not _SHA256_RE.fullmatch(evidence_sha256))) or (bool(evidence_file) != bool(evidence_sha256)):
            raise ValueError('device failure evidence artifact identity is invalid')
        normalized.append(dict(item))
    return normalized

def parse_device_batch_result(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise ValueError('device batch result must be text')
    if not raw.strip() or len(raw.encode('utf-8')) > _MAX_BYTES:
        raise ValueError('device batch result is empty or exceeds its byte budget')
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('device batch result must be one complete JSON object') from exc
    if not isinstance(payload, dict):
        raise ValueError('device batch result must be a JSON object')
    _exact_keys(payload, _TOP_KEYS, label='device batch result')
    if payload.get('schema') != SCHEMA:
        raise ValueError('invalid device batch result schema')
    status = payload.get('status')
    reason_code = payload.get('reason_code')
    if status not in STATUSES:
        raise ValueError('invalid device batch status')
    if reason_code not in REASON_CODES:
        raise ValueError('invalid device batch reason_code')
    allowed_reasons = {'completed': {'completed'}, 'device_busy': {'device_busy'}, 'env_pool_exhausted': {'env_pool_exhausted'}, 'failed': REASON_CODES - {'completed', 'device_busy', 'env_pool_exhausted'}}
    if reason_code not in allowed_reasons[status]:
        raise ValueError('device batch status/reason_code mismatch')
    _text(payload.get('reason_zh'), label='reason_zh')
    _text(payload.get('error_text'), label='error_text')
    if len(payload['error_text']) > MAX_ERROR_TEXT_CHARS:
        raise ValueError('error_text exceeds its character budget')
    _text(payload.get('bed_host'), label='bed_host', nullable=True)
    _text(payload.get('last_run_path'), label='last_run_path', nullable=True)
    prerequisite_receipts = validate_device_prerequisite_receipts(payload.get('prerequisite_receipts'), require_nonempty=False)
    if reason_code == 'device_prerequisite_unmet':
        if not prerequisite_receipts:
            raise ValueError('device prerequisite receipt is required')
    elif prerequisite_receipts:
        raise ValueError('device prerequisite receipts require device_prerequisite_unmet')
    failure_evidence = validate_device_failure_evidence(payload.get('failure_evidence'))
    if reason_code == 'result_channel_unavailable':
        if not failure_evidence:
            raise ValueError('result channel failure evidence is required')
    elif failure_evidence:
        raise ValueError('device failure evidence requires result_channel_unavailable')
    counts = payload.get('counts')
    if not isinstance(counts, dict):
        raise ValueError('counts must be an object')
    _exact_keys(counts, _COUNT_KEYS, label='counts')
    if any((isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values())):
        raise ValueError('counts values must be non-negative integers')
    if counts['total'] != sum((counts[key] for key in ('pass', 'fail', 'broken', 'unknown'))):
        raise ValueError('counts total does not equal verdict counts')
    alerts = payload.get('alerts')
    if not isinstance(alerts, dict):
        raise ValueError('alerts must be an object')
    _exact_keys(alerts, _ALERT_KEYS, label='alerts')
    _text(alerts.get('verified_runs_write_failed'), label='alerts.verified_runs_write_failed', nullable=True)
    _autoid_array(alerts.get('frozen_write_failed_autoids'), label='alerts.frozen_write_failed_autoids')
    identity = payload.get('run_identity')
    if identity is not None:
        if not isinstance(identity, dict):
            raise ValueError('run_identity must be an object or null')
        _exact_keys(identity, _IDENTITY_KEYS, label='run_identity')
        if any((not isinstance(value, str) or not value for value in identity.values())):
            raise ValueError('run_identity fields must be non-empty text')
        if not _SHA256_RE.fullmatch(identity['artifact_sha256']):
            raise ValueError('run_identity artifact_sha256 must be lowercase sha256')
    reverification = payload.get('runtime_reverification')
    if not isinstance(reverification, list):
        raise ValueError('runtime_reverification must be an array')
    for index, item in enumerate(reverification):
        if not isinstance(item, dict):
            raise ValueError(f'runtime_reverification[{index}] must be an object')
        _exact_keys(item, _REVERIFY_KEYS, label=f'runtime_reverification[{index}]')
        if not isinstance(item.get('autoid'), str) or not _AUTOID_RE.fullmatch(item['autoid']):
            raise ValueError('runtime_reverification autoid must be exactly 18 digits')
        for key in _REVERIFY_KEYS - {'autoid', 'raw_device_verdict', 'effective_verdict'}:
            _text(item.get(key), label=f'runtime_reverification.{key}')
        for key in ('raw_device_verdict', 'effective_verdict'):
            _text(item.get(key), label=f'runtime_reverification.{key}', nullable=True)
    cross_run = payload.get('cross_run')
    if not isinstance(cross_run, dict):
        raise ValueError('cross_run must be an object')
    _exact_keys(cross_run, _CROSS_RUN_KEYS, label='cross_run')
    _autoid_array(cross_run.get('repeat_autoids'), label='cross_run.repeat_autoids')
    _autoid_array(cross_run.get('transient_recur_autoids'), label='cross_run.transient_recur_autoids')
    _text(payload.get('crash_analysis'), label='crash_analysis', nullable=True)
    verdicts = payload.get('verdicts')
    if not isinstance(verdicts, list):
        raise ValueError('verdicts must be an array')
    seen_autoids: set[str] = set()
    observed_counts = {key: 0 for key in ('pass', 'fail', 'broken', 'unknown')}
    observed_attributions = {'grammar_rejected': 0, 'unattributed': 0}
    for index, item in enumerate(verdicts):
        if not isinstance(item, dict):
            raise ValueError(f'verdicts[{index}] must be an object')
        _exact_keys(item, _VERDICT_KEYS, label=f'verdicts[{index}]')
        if not isinstance(item.get('autoid'), str) or not _AUTOID_RE.fullmatch(item['autoid']):
            raise ValueError('verdict autoid must be exactly 18 digits')
        if item['autoid'] in seen_autoids:
            raise ValueError('verdict autoids must be unique')
        seen_autoids.add(item['autoid'])
        if item.get('verdict') not in VERDICTS:
            raise ValueError('invalid verdict value')
        observed_counts[item['verdict']] += 1
        if item.get('attribution') is not None and item.get('attribution') not in ATTRIBUTIONS:
            raise ValueError('invalid verdict attribution')
        if item['verdict'] == 'fail':
            if item.get('attribution') not in ATTRIBUTIONS:
                raise ValueError('fail verdict requires a closed attribution')
            observed_attributions[item['attribution']] += 1
        elif item.get('attribution') is not None or item.get('reflow') is not None:
            raise ValueError('non-fail verdict cannot carry attribution or reflow')
        if item.get('attribution') == 'grammar_rejected' and item.get('reflow') != 'G':
            raise ValueError('grammar_rejected verdict requires reflow G')
        if item.get('attribution') == 'unattributed' and item.get('reflow') is not None:
            raise ValueError('unattributed verdict cannot carry reflow')
        _text(item.get('reflow'), label='verdict.reflow', nullable=True)
        _text(item.get('note'), label='verdict.note')
    if len(verdicts) != counts['total']:
        raise ValueError('verdict row count does not equal counts.total')
    if any((counts[key] != observed_counts[key] for key in observed_counts)):
        raise ValueError('verdict rows do not match verdict counts')
    if any((counts[key] != observed_attributions[key] for key in observed_attributions)):
        raise ValueError('verdict rows do not match attribution counts')
    guidance = payload.get('guidance')
    if not isinstance(guidance, list) or any((not isinstance(item, str) for item in guidance)):
        raise ValueError('guidance must be an array of text')
    if status == 'completed':
        if not payload.get('last_run_path'):
            raise ValueError('completed result requires last_run_path')
    elif any((counts['total'], verdicts, payload.get('last_run_path'))):
        raise ValueError('non-completed result cannot carry verdict artifacts')
    return payload

def render_device_batch_result(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    parse_device_batch_result(raw)
    return raw

def empty_device_batch_result(*, status: str, reason_code: str, reason_zh: str, error_text: str='', prerequisite_receipts: list[dict[str, Any]] | None=None, failure_evidence: list[dict[str, Any]] | None=None) -> dict[str, Any]:
    return {'schema': SCHEMA, 'status': status, 'reason_code': reason_code, 'reason_zh': reason_zh, 'error_text': error_text, 'prerequisite_receipts': list(prerequisite_receipts or []), 'failure_evidence': list(failure_evidence or []), 'bed_host': None, 'last_run_path': None, 'counts': {'total': 0, 'pass': 0, 'fail': 0, 'broken': 0, 'unknown': 0, 'grammar_rejected': 0, 'unattributed': 0}, 'alerts': {'verified_runs_write_failed': None, 'frozen_write_failed_autoids': []}, 'run_identity': None, 'runtime_reverification': [], 'cross_run': {'repeat_autoids': [], 'transient_recur_autoids': []}, 'crash_analysis': None, 'verdicts': [], 'guidance': []}
