# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/verified_corpus.py（sha256 6a3fe406d3c2709a）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler.package_advisories import DENIED_668_AUTOIDS, POISON_RULE_ID, classify_package, package_rejection
_FILENAME_RE = re.compile('verified_(\\d{18})\\.xlsx')
_MAX_WORKBOOK_BYTES = 128 * 1024 * 1024

class VerifiedCorpusError(RuntimeError):

    def __init__(self, message: str, *, reason_code: str='verified_corpus_io_unsafe') -> None:
        super().__init__(message)
        self.reason_code = reason_code

@dataclass(frozen=True)
class Candidate:
    path: Path
    source: str
    autoid: str = ''
    sha256: str = ''
    eligible: bool = False
    reason: str = ''

@dataclass(frozen=True)
class CorpusInspection:
    active_count: int
    legacy_count: int
    incompatible_count: int
    issues: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.issues:
            return 'incompatible'
        return 'ready' if self.active_count else 'unavailable'

def canonical_root(project_root: Path) -> Path:
    return Path(project_root) / 'knowledge/framework/verified'

def legacy_root(project_root: Path) -> Path:
    return Path(project_root) / 'knowledge/framework/mirror'

def provenance_path(project_root: Path) -> Path:
    return Path(project_root) / 'knowledge/framework/mirror_precedent_provenance.json'

def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}

def _deny_projection(project_root: Path) -> dict[str, Any]:
    projection = _load_object(Path(project_root) / 'knowledge/data/compile_ref/package_advisories_10.5.json')
    records = projection.get('records')
    if not isinstance(records, dict):
        return {'records': {}}
    return projection

def _regular_digest(path: Path) -> str:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or int(info.st_size) <= 0 or (int(info.st_size) > _MAX_WORKBOOK_BYTES):
        raise ValueError('unsafe_file_identity')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while (chunk := stream.read(1024 * 1024)):
            digest.update(chunk)
    after = path.lstat()
    if int(after.st_dev) != int(info.st_dev) or int(after.st_ino) != int(info.st_ino) or int(after.st_size) != int(info.st_size) or (int(after.st_mtime_ns) != int(info.st_mtime_ns)) or (not stat.S_ISREG(after.st_mode)) or (int(after.st_nlink) != 1):
        raise ValueError('file_changed_while_reading')
    return digest.hexdigest()

def _candidate(path: Path, *, source: str, provenance: dict[str, Any], deny_projection: dict[str, Any]) -> Candidate:
    match = _FILENAME_RE.fullmatch(path.name)
    if match is None:
        return Candidate(path, source, reason='invalid_filename')
    autoid = match.group(1)
    try:
        digest = _regular_digest(path)
        from cex_core.engine.ist_core.tools.device.structural_gate import steps_from_xlsx
        workbook_autoid, steps = steps_from_xlsx(path)
        if str(workbook_autoid or '') != autoid or not steps:
            raise ValueError('workbook_identity_mismatch')
    except Exception as exc:
        return Candidate(path, source, autoid=autoid, reason=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    denied = package_rejection(autoid=autoid, sha256=digest, asset_id=path.name, projection=deny_projection)
    if denied or autoid in DENIED_668_AUTOIDS:
        rule_match = re.search('rule_id=(\\S+)', str(denied or ''))
        return Candidate(path, source, autoid=autoid, sha256=digest, reason=rule_match.group(1) if rule_match else POISON_RULE_ID)
    try:
        live = classify_package(path, provenance)
    except Exception:
        live = {}
    prior = (deny_projection.get('records') or {}).get(path.name)
    prior_certified = bool(isinstance(prior, dict) and prior.get('status') == 'certified' and (POISON_RULE_ID not in (prior.get('deny_rules') or [])) and (digest in {str(value).lower() for value in prior.get('sha256_aliases') or []}) and (autoid in {str(value) for value in prior.get('autoids') or []}))
    if live.get('status') != 'certified' and (not prior_certified):
        return Candidate(path, source, autoid=autoid, sha256=digest, reason='certified_delivery_identity_missing')
    return Candidate(path, source, autoid=autoid, sha256=digest, eligible=True)

def _paths(root: Path, *, include_unexpected: bool) -> list[Path]:
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise VerifiedCorpusError('verified corpus root is unsafe', reason_code='verified_corpus_root_unsafe')
    if include_unexpected:
        return sorted(root.iterdir(), key=lambda item: item.name)
    return sorted(root.glob('verified_*.xlsx'), key=lambda item: item.name)

def inspect_verified_corpus(project_root: Path) -> CorpusInspection:
    project_root = Path(project_root)
    provenance = _load_object(provenance_path(project_root))
    projection = _deny_projection(project_root)
    active_paths = _paths(canonical_root(project_root), include_unexpected=True)
    legacy_paths = _paths(legacy_root(project_root), include_unexpected=False)
    issues: list[str] = []
    active = 0
    incompatible = 0
    for path in active_paths:
        item = _candidate(path, source='active', provenance=provenance, deny_projection=projection)
        if item.eligible:
            active += 1
        else:
            incompatible += 1
            issues.append(f'active:{path.name}:{item.reason}')
    if legacy_paths:
        issues.append(f'legacy:{len(legacy_paths)}')
    return CorpusInspection(active_count=active, legacy_count=len(legacy_paths), incompatible_count=incompatible, issues=tuple(issues))

def _quarantine_target(quarantine: Path, item: Candidate, *, reason: str) -> Path:
    digest = item.sha256[:16] if item.sha256 else 'unsafe'
    safe_reason = re.sub('[^a-zA-Z0-9_-]+', '_', reason)[:48] or 'invalid'
    base = f'{item.path.name}.{item.source}.{safe_reason}.{digest}'
    target = quarantine / base
    counter = 1
    while target.exists() or target.is_symlink():
        target = quarantine / f'{base}.{counter}'
        counter += 1
    return target

def _move_to_quarantine(item: Candidate, quarantine: Path, *, reason: str) -> str:
    target = _quarantine_target(quarantine, item, reason=reason)
    os.replace(item.path, target)
    return target.name

def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode() + b'\n'
    atomic_write_bytes_nofollow(path, raw, error_type=VerifiedCorpusError, invalid_message='verified corpus receipt path is invalid', unavailable_message='verified corpus receipt cannot be published', create_parents=True, mode=384)

def converge_verified_corpus(project_root: Path) -> dict[str, Any]:
    project_root = Path(project_root)
    active_root = canonical_root(project_root)
    legacy = legacy_root(project_root)
    if active_root.exists() and (active_root.is_symlink() or not active_root.is_dir()):
        raise VerifiedCorpusError('verified corpus root is unsafe', reason_code='verified_corpus_root_unsafe')
    active_root.mkdir(parents=True, exist_ok=True, mode=448)
    quarantine = project_root / 'runtime/quarantine/verified_packages'
    if quarantine.exists() and (quarantine.is_symlink() or not quarantine.is_dir()):
        raise VerifiedCorpusError('verified corpus quarantine root is unsafe', reason_code='verified_corpus_quarantine_unsafe')
    quarantine.mkdir(parents=True, exist_ok=True, mode=448)
    provenance = _load_object(provenance_path(project_root))
    projection = _deny_projection(project_root)
    active_items = {path.name: _candidate(path, source='active', provenance=provenance, deny_projection=projection) for path in _paths(active_root, include_unexpected=True)}
    legacy_items = {path.name: _candidate(path, source='legacy', provenance=provenance, deny_projection=projection) for path in _paths(legacy, include_unexpected=False)}
    events: list[dict[str, str]] = []
    for name in sorted(set(active_items) | set(legacy_items)):
        current = active_items.get(name)
        old = legacy_items.get(name)
        if current is not None and old is not None:
            if current.eligible and old.eligible and (current.sha256 == old.sha256):
                old.path.unlink()
                events.append({'file': name, 'action': 'deduplicated', 'reason': 'same_bytes'})
                continue
            if current.eligible and (not old.eligible):
                target = _move_to_quarantine(old, quarantine, reason=old.reason)
                events.append({'file': name, 'action': 'quarantined_legacy', 'reason': old.reason, 'target': target})
                continue
            if old.eligible and (not current.eligible):
                target = _move_to_quarantine(current, quarantine, reason=current.reason)
                os.replace(old.path, active_root / name)
                events.extend([{'file': name, 'action': 'quarantined_active', 'reason': current.reason, 'target': target}, {'file': name, 'action': 'migrated', 'reason': 'certified_legacy'}])
                continue
            for item in (current, old):
                reason = 'identity_collision' if item.eligible else item.reason
                target = _move_to_quarantine(item, quarantine, reason=reason)
                events.append({'file': name, 'action': f'quarantined_{item.source}', 'reason': reason, 'target': target})
            continue
        item = current or old
        assert item is not None
        if not item.eligible:
            target = _move_to_quarantine(item, quarantine, reason=item.reason)
            events.append({'file': name, 'action': f'quarantined_{item.source}', 'reason': item.reason, 'target': target})
        elif item.source == 'legacy':
            os.replace(item.path, active_root / name)
            events.append({'file': name, 'action': 'migrated', 'reason': 'certified_legacy'})
    inspection = inspect_verified_corpus(project_root)
    if inspection.issues:
        raise VerifiedCorpusError('verified corpus remained incompatible after convergence', reason_code='verified_corpus_not_converged')
    receipt = {'schema': 'ist.verified-corpus-convergence', 'active_root': 'knowledge/framework/verified', 'legacy_root': 'knowledge/framework/mirror', 'status': inspection.status, 'active_count': inspection.active_count, 'events': events}
    _write_receipt(quarantine / 'last_convergence.json', receipt)
    return receipt
__all__ = ['CorpusInspection', 'VerifiedCorpusError', 'canonical_root', 'converge_verified_corpus', 'inspect_verified_corpus', 'legacy_root', 'provenance_path']
