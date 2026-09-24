# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/framework_projections.py（sha256 0de753d910df3a60）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import hashlib
import threading
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler.package_advisories import build_package_advisories, write_json_atomic
from cex_core.engine.common.file_identity import file_identity, walk_identity
from cex_core.engine.ist_core.compile_engine.verified_corpus import canonical_root, inspect_verified_corpus, provenance_path

class FrameworkDerivedProjectionError(RuntimeError):

    def __init__(self, message: str, *, reason_code: str, projection_path: str='', generator: str='', observed_file_sha256: str='', expected_content_sha256: str='', observed_content_sha256: str='', changed_inputs: tuple[dict, ...]=(), expected_identity_sha256: str='', observed_identity_sha256: str='') -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.projection_path = projection_path
        self.generator = generator
        self.observed_file_sha256 = observed_file_sha256
        self.expected_content_sha256 = expected_content_sha256
        self.observed_content_sha256 = observed_content_sha256
        self.changed_inputs = changed_inputs
        self.expected_identity_sha256 = expected_identity_sha256
        self.observed_identity_sha256 = observed_identity_sha256

    def disclosure(self) -> dict:
        return {key: value for key, value in vars(self).items() if value}

def _paths(project_root: Path) -> dict[str, Path]:
    compile_ref = Path(project_root) / 'knowledge/data/compile_ref'
    return {'usage': compile_ref / 'capability_usage_index.json', 'package': compile_ref / 'package_advisories_10.5.json', 'behavior': compile_ref / 'device_behavior_examples.json', 'language': compile_ref / 'language_docs_index.json'}

def _load_json_bytes(path: Path) -> tuple[Any, bytes]:
    if path.is_symlink() or not path.is_file():
        raise FrameworkDerivedProjectionError('framework-derived projection is missing or unsafe', reason_code='framework_derived_projection_missing')
    try:
        raw = path.read_bytes()
        return (json.loads(raw.decode('utf-8')), raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrameworkDerivedProjectionError('framework-derived projection is unreadable', reason_code='framework_derived_projection_unreadable') from exc

def _load_json(path: Path) -> Any:
    return _load_json_bytes(path)[0]

def _content_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()

def _check_projection(project_root: Path, path: Path, expected: Any, *, reason_code: str, generator: str) -> None:
    relative = path.relative_to(project_root).as_posix()
    try:
        observed, raw = _load_json_bytes(path)
    except FrameworkDerivedProjectionError as exc:
        raise FrameworkDerivedProjectionError(str(exc), reason_code=exc.reason_code, projection_path=relative, generator=generator) from exc
    if observed != expected:
        raise FrameworkDerivedProjectionError('projection content differs from the current generator output', reason_code=reason_code, projection_path=relative, generator=generator, observed_file_sha256=hashlib.sha256(raw).hexdigest(), expected_content_sha256=_content_digest(expected), observed_content_sha256=_content_digest(observed))

def _package_payload(project_root: Path) -> dict[str, Any]:
    return build_package_advisories(canonical_root(project_root), provenance_path(project_root), poison_root=Path(project_root) / 'tests/fixtures/precedents/poisoned', retro_scan_path=None)

def _behavior_payload(project_root: Path) -> dict[str, Any]:
    from cex_core.engine.scripts import gen_device_behavior_examples
    try:
        return gen_device_behavior_examples.build(Path(project_root))
    except gen_device_behavior_examples.DeviceBehaviorSourceUnavailableError as exc:
        raise FrameworkDerivedProjectionError('device behavior corpus is unavailable', reason_code='device_behavior_corpus_unavailable') from exc
_CODE_ROOT = _cex_data_path('')
_CODE_GLOBS = ('main/case_compiler/**/*.py',)
_CODE_FILES = ('main/ist_core/tools/device/structural_gate.py', 'main/ist_core/compile_engine/verified_corpus.py', 'main/ist_core/compile_engine/framework_projections.py', 'main/ist_core/worker_device_context.py', 'main/ist_core/tools/knowledge/behavior_tool.py', 'main/common/schema_identity.py', 'main/common/file_identity.py', 'scripts/gen_capability_usage_index.py', 'scripts/gen_device_behavior_examples.py', 'scripts/maintenance/build_language_docs_index.py')
_PROJECTION_NAMES = frozenset({'capability_usage_index.json', 'package_advisories_10.5.json', 'device_behavior_examples.json', 'language_docs_index.json'})

def _content(tuples: tuple[tuple[str, int, int, str], ...]) -> tuple:
    return tuple(((rel, size, sha) for rel, size, _mtime_ns, sha in tuples))

def _singleton(path: Path, rel: str) -> tuple:
    try:
        _resolved, size, _mtime_ns, sha = file_identity(path)
    except OSError:
        return (rel, '<absent>')
    return (rel, size, sha)

def _code_identity() -> tuple:
    files = {path for pattern in _CODE_GLOBS for path in _CODE_ROOT.glob(pattern)}
    files |= {_CODE_ROOT / rel for rel in _CODE_FILES}
    out = []
    for path in sorted(files):
        out.append(_singleton(path, path.relative_to(_CODE_ROOT).as_posix()))
    return tuple(out)

def _rebuild_callable_ids() -> tuple[int, ...]:
    from cex_core.engine.scripts import gen_capability_usage_index, gen_device_behavior_examples
    from cex_core.engine.scripts.maintenance import build_language_docs_index
    from cex_core.engine.ist_core.tools.device.structural_gate import steps_from_xlsx
    return (id(inspect_verified_corpus), id(gen_capability_usage_index.build), id(gen_device_behavior_examples.build), id(build_language_docs_index.build_language_docs_index), id(build_package_advisories), id(steps_from_xlsx))

def _validation_identity(project_root: Path) -> tuple:
    root = Path(project_root)
    knowledge = root / 'knowledge'
    return (str(root.resolve()), ('verified', walk_identity(knowledge / 'framework/verified')), ('mirror', _content(walk_identity(knowledge / 'framework/mirror'))), ('behavior_corpus', _content(walk_identity(knowledge / 'data/device_behavior_corpus'))), ('manual', _content(walk_identity(knowledge / 'data/manual'))), ('compile_ref', _content(walk_identity(knowledge / 'data/compile_ref'))), ('poisoned', _content(walk_identity(root / 'tests/fixtures/precedents/poisoned'))), ('singletons', (_singleton(provenance_path(root), 'knowledge/framework/mirror_precedent_provenance.json'), _singleton(knowledge / 'shadow_exec/manifest.json', 'knowledge/shadow_exec/manifest.json'), _singleton(_CODE_ROOT / 'scripts/data/package_deny_rulings.json', 'scripts/data/package_deny_rulings.json'))), ('code', _code_identity()), ('callables', _rebuild_callable_ids()))

def _mask_projections(identity: tuple) -> tuple:
    masked = []
    for component in identity:
        if isinstance(component, tuple) and len(component) == 2 and (component[0] == 'compile_ref'):
            masked.append(('compile_ref', tuple((entry for entry in component[1] if entry[0] not in _PROJECTION_NAMES))))
        else:
            masked.append(component)
    return tuple(masked)

def _require_stable_identity(before: tuple, after: tuple) -> None:
    if before == after:
        return
    old = dict((component for component in before[1:] if isinstance(component, tuple) and len(component) == 2))
    new = dict((component for component in after[1:] if isinstance(component, tuple) and len(component) == 2))
    changed = []
    for component in sorted(set(old) | set(new)):
        left, right = (old.get(component), new.get(component))
        if left == right:
            continue
        if isinstance(left, tuple) and isinstance(right, tuple) and all((isinstance(row, tuple) and row and isinstance(row[0], str) for row in left + right)):
            old_rows, new_rows = ({row[0]: row for row in left}, {row[0]: row for row in right})
            for path in sorted(set(old_rows) | set(new_rows)):
                if old_rows.get(path) != new_rows.get(path):
                    changed.append({'component': component, 'relative_path': path, 'before': old_rows.get(path), 'after': new_rows.get(path)})
        else:
            changed.append({'component': component, 'relative_path': '', 'before': left, 'after': right})
    raise FrameworkDerivedProjectionError('projection inputs changed while they were being checked', reason_code='framework_projection_inputs_changed', changed_inputs=tuple(changed), expected_identity_sha256=_content_digest(before), observed_identity_sha256=_content_digest(after))
_MEMO_LOCK = threading.Lock()
_MEMO: dict[str, Any] | None = None

def _memo_lookup(identity: tuple) -> dict[str, Any] | None:
    with _MEMO_LOCK:
        if _MEMO is not None and _MEMO['identity'] == identity:
            return _MEMO
    return None

def _memo_store(identity: tuple, *, verdict: dict[str, Any], payloads: dict[str, Any], inspection: Any) -> None:
    global _MEMO
    with _MEMO_LOCK:
        _MEMO = {'identity': identity, 'verdict': dict(verdict), 'payloads': payloads, 'inspection': inspection}

def clear_projection_validation_memo() -> None:
    global _MEMO
    with _MEMO_LOCK:
        _MEMO = None

def converge_language_docs_projection(project_root: Path) -> bool:
    project_root = Path(project_root)
    path = _paths(project_root)['language']
    from cex_core.engine.scripts.maintenance import build_language_docs_index
    language = build_language_docs_index.build_language_docs_index(project_root)
    try:
        current_language = _load_json(path)
    except FrameworkDerivedProjectionError:
        current_language = None
    if current_language == language:
        return False
    build_language_docs_index.write_language_docs_index(path, root=project_root)
    return True

def converge_framework_derived_projections(project_root: Path) -> dict[str, Any]:
    project_root = Path(project_root)
    from cex_core.engine.scripts import gen_capability_usage_index
    if gen_capability_usage_index._ROOT.resolve() != project_root.resolve():
        raise FrameworkDerivedProjectionError('capability usage generator is bound to another project root', reason_code='framework_projection_root_mismatch')
    identity = _validation_identity(project_root)
    memo = _memo_lookup(identity)
    payloads = memo['payloads'] if memo is not None else None
    inspection = memo['inspection'] if memo is not None else inspect_verified_corpus(project_root)
    if inspection.issues:
        raise FrameworkDerivedProjectionError('verified corpus must converge before projections are rebuilt', reason_code='verified_corpus_not_converged')
    paths = _paths(project_root)
    changed: list[str] = []
    usage = payloads['usage'] if payloads is not None else gen_capability_usage_index.build()
    try:
        current_usage = _load_json(paths['usage'])
    except FrameworkDerivedProjectionError:
        current_usage = None
    if current_usage != usage:
        gen_capability_usage_index.write_projection(usage, paths['usage'])
        changed.append('capability_usage_index')
    package = payloads['package'] if payloads is not None else _package_payload(project_root)
    try:
        current_package = _load_json(paths['package'])
    except FrameworkDerivedProjectionError:
        current_package = None
    if current_package != package:
        write_json_atomic(paths['package'], package)
        changed.append('package_advisories')
    from cex_core.engine.scripts import gen_device_behavior_examples
    behavior = payloads['behavior'] if payloads is not None else _behavior_payload(project_root)
    try:
        current_behavior = _load_json(paths['behavior'])
    except FrameworkDerivedProjectionError:
        current_behavior = None
    behavior_changed = current_behavior != behavior
    if behavior_changed:
        gen_device_behavior_examples.write_atomic(paths['behavior'], behavior)
        changed.append('device_behavior_examples')
    from cex_core.engine.scripts.maintenance import build_language_docs_index
    if payloads is not None and (not behavior_changed):
        language = payloads['language']
    else:
        language = build_language_docs_index.build_language_docs_index(project_root)
    try:
        current_language = _load_json(paths['language'])
    except FrameworkDerivedProjectionError:
        current_language = None
    if current_language != language:
        build_language_docs_index.write_language_docs_index(paths['language'], root=project_root)
        changed.append('language_docs_index')
    verdict = {'verified_corpus_status': inspection.status, 'verified_corpus_count': inspection.active_count, 'usage_status': str((usage.get('_meta') or {}).get('corpus_status') or ''), 'behavior_status': str(behavior.get('status') or '')}
    post_identity = _validation_identity(project_root)
    _require_stable_identity(_mask_projections(identity), _mask_projections(post_identity))
    _memo_store(post_identity, verdict=verdict, payloads={'usage': usage, 'package': package, 'behavior': behavior, 'language': language}, inspection=inspection)
    return {'changed': changed, **verdict}

def validate_framework_derived_projections(project_root: Path) -> dict[str, Any]:
    project_root = Path(project_root)
    from cex_core.engine.scripts import gen_capability_usage_index, gen_device_behavior_examples
    from cex_core.engine.scripts.maintenance import build_package_advisories as package_generator
    if gen_capability_usage_index._ROOT.resolve() != project_root.resolve():
        raise FrameworkDerivedProjectionError('capability usage generator is bound to another project root', reason_code='framework_projection_root_mismatch')
    identity = _validation_identity(project_root)
    memo = _memo_lookup(identity)
    if memo is not None:
        _require_stable_identity(identity, _validation_identity(project_root))
        return dict(memo['verdict'])
    inspection = inspect_verified_corpus(project_root)
    if inspection.issues:
        raise FrameworkDerivedProjectionError('verified corpus contains legacy or incompatible data', reason_code='verified_corpus_migration_required')
    paths = _paths(project_root)
    usage = gen_capability_usage_index.build()
    _check_projection(project_root, paths['usage'], usage, reason_code='capability_usage_projection_stale', generator=gen_capability_usage_index.__name__)
    package = _package_payload(project_root)
    _check_projection(project_root, paths['package'], package, reason_code='package_advisory_projection_stale', generator=package_generator.__name__)
    behavior = _behavior_payload(project_root)
    _check_projection(project_root, paths['behavior'], behavior, reason_code='device_behavior_projection_stale', generator=gen_device_behavior_examples.__name__)
    from cex_core.engine.scripts.maintenance import build_language_docs_index
    language = build_language_docs_index.build_language_docs_index(project_root)
    _check_projection(project_root, paths['language'], language, reason_code='language_docs_projection_stale', generator=build_language_docs_index.__name__)
    verdict = {'verified_corpus_status': inspection.status, 'verified_corpus_count': inspection.active_count, 'usage_status': str((usage.get('_meta') or {}).get('corpus_status') or ''), 'behavior_status': str(behavior.get('status') or '')}
    _require_stable_identity(identity, _validation_identity(project_root))
    _memo_store(identity, verdict=verdict, payloads={'usage': usage, 'package': package, 'behavior': behavior, 'language': language}, inspection=inspection)
    return verdict
__all__ = ['FrameworkDerivedProjectionError', 'clear_projection_validation_memo', 'converge_framework_derived_projections', 'converge_language_docs_projection', 'validate_framework_derived_projections']
