# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/package_advisories.py（sha256 16f162e8ff82d11c）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path, _cex_identity_set
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
HISTORICAL_TARGET_COUNT = 325
POISON_RULE_ID = 'PKG-POISON-001'
USER_DENY_RULE_ID = 'PKG-RULING-DENY-001'
_DENY_RULINGS_RELATIVE = 'scripts/data/package_deny_rulings.json'
_POISON_RULINGS_RELATIVE = 'scripts/data/package_poison_rulings.json'
PACKAGE_REFERENCE_ERROR = 'E_PACKAGE_REFERENCE_DENIED'
DENIED_668_AUTOIDS = _cex_identity_set('main/case_compiler/package_advisories.py:DENIED_668_AUTOIDS')
_GRADE_ORDER = {'A': 0, 'B': 1, 'C': 2}
PACKAGE_ADVISORIES_PATH = _cex_data_path('') / 'knowledge/data/compile_ref/package_advisories_10.5.json'

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _autoids(path: Path) -> list[str]:
    from cex_core.engine.ist_core.tools.device.structural_gate import steps_from_xlsx
    aid, _ = steps_from_xlsx(path)
    return [aid] if aid else []

def package_asset_autoid(asset_id: str | Path) -> str:
    """按注册资产文件名取案号，供分类与引用入口共用。"""
    stem = Path(asset_id).stem
    return stem.removeprefix('verified_') if stem.startswith('verified_') else ''

def classify_package(path: Path, provenance: dict[str, Any], *, poison_confirmed: bool=False, retro_grade: str='') -> dict[str, Any]:
    from cex_core.engine.ist_core.tools.device.structural_gate import lint_xlsx_case
    digest = _sha256(path)
    entry = provenance.get(path.name)
    reasons: list[str] = []
    from cex_core.engine.case_compiler.claim_coverage import coverage_reason_code
    lint = lint_xlsx_case(path)
    if not lint.ok:
        reasons.append('structural_lint_failed')
    certification = entry.get('certification') if isinstance(entry, dict) else None
    coverage_reason = coverage_reason_code(certification)
    if isinstance(certification, dict) and certification:
        if coverage_reason:
            reasons.append(coverage_reason)
    elif lint.advisories:
        reasons.append('lint_advisory_present')
    if not isinstance(entry, dict) or 'result' not in entry:
        reasons.append('structured_delivery_receipt_missing')
        entry = {}
    else:
        if entry.get('ctx') != 'delivery' or entry.get('result') != 'pass':
            reasons.append('delivery_pass_missing')
        if not entry.get('build'):
            reasons.append('device_build_missing')
        artifact = str(entry.get('artifact') or '')
        if not artifact:
            reasons.append('artifact_fingerprint_missing')
        elif artifact.rsplit(':', 1)[-1].lower() != digest:
            reasons.append('artifact_fingerprint_mismatch')
    autoids = _autoids(path)
    filename_autoid = package_asset_autoid(path)
    if filename_autoid and filename_autoid not in autoids:
        autoids.append(filename_autoid)
    identity_denied = poison_confirmed or bool(DENIED_668_AUTOIDS.intersection(autoids))
    if retro_grade == 'A':
        status = 'certified'
        certification_basis = 'retro_replay_clean'
        certification_reasons: list[str] = []
    elif retro_grade in {'B', 'C'}:
        status = 'unverified'
        certification_basis = 'retro_replay'
        certification_reasons = [f'retro_replay_grade_{retro_grade.lower()}']
    else:
        status = 'certified' if not reasons else 'unverified'
        certification_basis = 'artifact_receipt_replay'
        certification_reasons = reasons
    flags: list[str] = []
    if poison_confirmed:
        flags.append('poison_confirmed')
    if retro_grade in _GRADE_ORDER:
        flags.append(f'retro_grade_{retro_grade.lower()}')
    return {'status': status, 'certification_basis': certification_basis, 'asset_id': path.name, 'sha256': digest, 'sha256_aliases': [digest], 'autoids': autoids, 'reason_codes': certification_reasons, 'flags': flags, 'deny_rules': [POISON_RULE_ID] if identity_denied else [], 'lint': {'violations': [v.code for v in lint.violations], 'advisories': [v.code for v in lint.advisories], 'disabled': [v.code for v in lint.disabled]}, 'claim_coverage': {'status': str(certification.get('status') or ''), 'fidelity': str(certification.get('fidelity') or ''), 'uncovered_expectation_ids': [str(v) for v in certification.get('uncovered_expectation_ids') or []]} if isinstance(certification, dict) and certification else None, 'receipt': {key: entry[key] for key in ('ctx', 'result', 'build', 'artifact', 'run_id') if entry.get(key)}}

def _repo_relative(path: Path) -> str:
    from cex_core.engine.knowledge_paths import PROJECT_ROOT
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()

class PackageAdvisorySourceMissing(FileNotFoundError):
    pass

def _deny_rulings(path: Path | None, *, require_sha_scope: bool=False) -> list[dict[str, Any]]:
    if path is None:
        return []
    if not path.is_file():
        raise PackageAdvisorySourceMissing(f'先例包封禁裁决来源不在：{path}。缺它重算会让用户按 sha 封禁的卷静默放行；要么把文件恢复到位，要么显式传 deny_rulings_path=None。')
    payload = json.loads(path.read_text(encoding='utf-8'))
    rows = payload.get('rulings') if isinstance(payload, dict) else None
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        digest = str(row.get('sha256') or '').strip().lower()
        asset_id = str(row.get('asset_id') or '').strip()
        if len(digest) != 64 or not asset_id.endswith('.xlsx') or (require_sha_scope and row.get('scope') != 'sha256'):
            raise PackageAdvisorySourceMissing(f"先例包封禁裁决条目不闭合：{row.get('ruling_id')!r}")
        out.append({'ruling_id': str(row.get('ruling_id') or ''), 'ruled_at': str(row.get('ruled_at') or ''), 'asset_id': asset_id, 'autoid': str(row.get('autoid') or ''), 'sha256': digest, 'reason_code': str(row.get('reason_code') or '')})
    return out

def _apply_deny_rulings(records: dict[str, Any], rulings: list[dict[str, Any]], *, rule_id: str=USER_DENY_RULE_ID) -> None:
    sha_field = 'poison_sha256s' if rule_id == POISON_RULE_ID else 'denied_sha256s'
    flag = 'poison_confirmed' if rule_id == POISON_RULE_ID else 'user_ruling_denied'
    for ruling in rulings:
        name = ruling['asset_id']
        record = records.get(name)
        if not isinstance(record, dict):
            record = {'status': 'unverified', 'certification_basis': 'user_ruling_deny', 'asset_id': name, 'asset_state': 'quarantined', 'sha256': '', 'sha256_aliases': [], 'autoids': [ruling['autoid']] if ruling['autoid'] else [], 'reason_codes': ['user_ruling_deny'], 'flags': [flag], 'deny_rules': [], 'lint': {'violations': [], 'advisories': [], 'disabled': []}, 'claim_coverage': None, 'receipt': {}}
            records[name] = record
        record['deny_rules'] = sorted(set(record.get('deny_rules') or []) | {rule_id})
        record['flags'] = sorted(set(record.get('flags') or []) | {flag})
        record[sha_field] = sorted(set(record.get(sha_field) or []) | {ruling['sha256']})
        record.setdefault('deny_rulings', [])
        record['deny_rulings'] = sorted({*record['deny_rulings'], ruling['ruling_id']})
        if str(record.get('sha256') or '').lower() == ruling['sha256']:
            record['status'] = 'unverified'
            if 'user_ruling_deny' not in record.get('reason_codes', []):
                record['reason_codes'] = [*record.get('reason_codes', []), 'user_ruling_deny']

def _retro_grades(retro_scan_path: Path | None) -> dict[str, str]:
    if retro_scan_path is None:
        return {}
    if not retro_scan_path.is_file():
        raise PackageAdvisorySourceMissing(f'retro 分级来源不在：{retro_scan_path}。缺它重算会让 133 卷的 retro_grade_* 标记整体消失、并改变认证判定；要么把来源恢复到位，要么显式传 retro_scan_path=None 并在 source 块如实标注未合入。')
    payload = json.loads(retro_scan_path.read_text(encoding='utf-8'))
    grades: dict[str, str] = {}
    for row in payload.get('library', []) if isinstance(payload, dict) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get('file') or '')
        grade = str(row.get('grade') or '')
        if not name or grade not in _GRADE_ORDER:
            continue
        previous = grades.get(name, 'A')
        grades[name] = grade if _GRADE_ORDER[grade] >= _GRADE_ORDER[previous] else previous
    return grades
_DENY_RULINGS_DEFAULT = object()

def _default_deny_rulings_path() -> Path:
    from cex_core.engine.knowledge_paths import PROJECT_ROOT
    return Path(PROJECT_ROOT) / _DENY_RULINGS_RELATIVE

def build_package_advisories(mirror_root: Path, provenance_path: Path, *, poison_root: Path | None=None, retro_scan_path: Path | None=None, historical_target_count: int=HISTORICAL_TARGET_COUNT, deny_rulings_path: Path | None | object=_DENY_RULINGS_DEFAULT) -> dict[str, Any]:
    provenance: dict[str, Any] = {}
    if provenance_path.is_file():
        loaded = json.loads(provenance_path.read_text(encoding='utf-8'))
        if isinstance(loaded, dict):
            provenance = loaded
    files = sorted(mirror_root.glob('verified_*.xlsx'))
    grades = _retro_grades(retro_scan_path)
    records = {p.name: classify_package(p, provenance, retro_grade=grades.get(p.name, '')) for p in files}
    if poison_root is not None and (not poison_root.is_dir()):
        raise PackageAdvisorySourceMissing(f'隔离资产目录不在：{poison_root}。缺它重算会把确认中毒的先例包静默放行；要么把目录恢复到位，要么显式传 poison_root=None。')
    rulings_path = _default_deny_rulings_path() if deny_rulings_path is _DENY_RULINGS_DEFAULT else deny_rulings_path
    rulings = _deny_rulings(rulings_path) if rulings_path is not None else []
    from cex_core.engine.knowledge_paths import PROJECT_ROOT
    poison_rulings = _deny_rulings(Path(PROJECT_ROOT) / _POISON_RULINGS_RELATIVE, require_sha_scope=True)
    quarantine_files = sorted(poison_root.glob('verified_*.xlsx')) if poison_root is not None else []
    for path in quarantine_files:
        quarantined = classify_package(path, provenance, poison_confirmed=True, retro_grade=grades.get(path.name, ''))
        existing = records.get(path.name)
        quarantined['poison_sha256s'] = [quarantined['sha256']]
        if existing is None:
            quarantined['asset_state'] = 'quarantined'
            records[path.name] = quarantined
            continue
        existing['flags'] = sorted(set(existing['flags']) | {'poison_confirmed'})
        existing['deny_rules'] = sorted(set(existing['deny_rules']) | {POISON_RULE_ID})
        existing['sha256_aliases'] = sorted(set(existing['sha256_aliases']) | {quarantined['sha256']})
        existing['poison_sha256s'] = sorted(set(existing.get('poison_sha256s') or []) | {quarantined['sha256']})
    _apply_deny_rulings(records, poison_rulings, rule_id=POISON_RULE_ID)
    _apply_deny_rulings(records, rulings)
    for autoid in sorted(DENIED_668_AUTOIDS):
        name = f'verified_{autoid}.xlsx'
        if name in records:
            continue
        records[name] = {'status': 'unverified', 'certification_basis': 'mandatory_deny_identity', 'asset_id': name, 'asset_state': 'quarantined', 'sha256': '', 'sha256_aliases': [], 'autoids': [autoid], 'reason_codes': ['mandatory_deny_identity'], 'flags': ['identity_deny_tombstone'], 'deny_rules': [POISON_RULE_ID], 'lint': {'violations': [], 'advisories': [], 'disabled': []}, 'receipt': {}}
    active_names = {path.name for path in files}
    certified = sum((records[name]['status'] == 'certified' for name in active_names))
    active_unverified = sum((records[name]['status'] != 'certified' for name in active_names))
    current = len(files)
    target = int(historical_target_count)
    return {'schema_version': 3, 'classification': 'certified|unverified', 'source': {'kind': 'package_registry_projection', 'path': 'knowledge/framework/verified/verified_*.xlsx', 'quarantine_path': f'{_repo_relative(poison_root)}/verified_*.xlsx' if poison_root is not None and quarantine_files else '', 'current_manifest_count': current, 'quarantined_manifest_count': len(quarantine_files), 'record_count': len(records), 'historical_target_count': target, 'historical_manifest_available': current == target, 'population_complete': current == target, 'population_note': 'current manifest equals the historical target' if current == target else 'the historical 325-volume member manifest is not present; current files were fully replayed, but they must not be reported as all 325'}, 'baseline': {'certified': certified, 'unverified': active_unverified, 'current_population_coverage': certified / current if current else 0.0, 'historical_target_lower_bound': certified / target if target else 0.0}, 'records': records}

def package_rejection(*, autoid: str='', sha256: str='', asset_id: str='', projection: dict[str, Any]) -> str:
    aid = str(autoid or '').strip()
    digest = str(sha256 or '').strip().lower()
    asset = str(asset_id or '').strip()
    if aid in DENIED_668_AUTOIDS:
        return f'{PACKAGE_REFERENCE_ERROR} asset_id={asset or aid} rule_id={POISON_RULE_ID}'
    records = projection.get('records') if isinstance(projection, dict) else {}
    for name, record in records.items() if isinstance(records, dict) else ():
        if not isinstance(record, dict):
            continue
        rules = record.get('deny_rules', [])
        if POISON_RULE_ID in rules:
            aliases = {str(value).lower() for value in record.get('poison_sha256s', record.get('sha256_aliases', []))}
            identities = {str(value) for value in record.get('autoids', [])}
            identity_denied = bool(DENIED_668_AUTOIDS.intersection(identities))
            if identity_denied:
                aliases |= {str(value).lower() for value in record.get('sha256_aliases', [])}
                matched = asset == name or bool(aid and aid in identities) or bool(digest and digest in aliases)
            else:
                matched = bool(digest and digest in aliases)
            if matched:
                return f'{PACKAGE_REFERENCE_ERROR} asset_id={name} rule_id={POISON_RULE_ID}'
        if USER_DENY_RULE_ID in rules:
            denied = {str(value).lower() for value in record.get('denied_sha256s', [])}
            if digest and digest in denied:
                return f'{PACKAGE_REFERENCE_ERROR} asset_id={name} rule_id={USER_DENY_RULE_ID}'
    return ''

def read_package_projection(path: Path | None=None) -> dict[str, Any]:
    source = path or PACKAGE_ADVISORIES_PATH
    payload = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or not isinstance(payload.get('records'), dict):
        raise ValueError('package advisory projection has no records object')
    return payload

def validate_package_expect_reference(asset_id: str, expect_source: str) -> str:
    if str(expect_source or '').strip() != 'poison_confirmed':
        return ''
    return f"{PACKAGE_REFERENCE_ERROR} asset_id={str(asset_id or '-').strip() or '-'} rule_id={POISON_RULE_ID}"

def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
