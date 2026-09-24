# 生成：tools/extract_engine.py ← InfoTest main/knowledge_paths.py（sha256 fb8e21f79a6434da）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import contextvars
import hashlib
import json
import os
import re
import stat
import time
from dataclasses import dataclass
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow, validate_json_budget
from cex_core.engine.common.schema_identity import accepts_schema
_current_username_ctx: contextvars.ContextVar[str] = contextvars.ContextVar('current_username', default='')
MAIN_DIR = _cex_data_path('main')
PROJECT_ROOT = MAIN_DIR.parent
KNOWLEDGE_ROOT = PROJECT_ROOT / 'knowledge'
KNOWLEDGE_DATA_ROOT = KNOWLEDGE_ROOT / 'data'
KNOWLEDGE_INTERMEDIATE = KNOWLEDGE_ROOT / '.intermediate'
KNOWLEDGE_ORGIN = KNOWLEDGE_DATA_ROOT / 'orgin'
ORGIN_WORKDIR_NAME = '_pdf_splits'

def _is_skipped_dir(name: str) -> bool:
    return name.startswith('.') or name == ORGIN_WORKDIR_NAME

def iter_orgin_files(orgin_dir: Path | str | None=None) -> Iterator[Path]:
    root = Path(orgin_dir) if orgin_dir is not None else KNOWLEDGE_ORGIN
    if not root.exists():
        return

    def _walk(d: Path) -> Iterator[Path]:
        for child in sorted(d.iterdir(), key=lambda p: p.name):
            if child.is_dir():
                if _is_skipped_dir(child.name):
                    continue
                yield from _walk(child)
            elif child.is_file():
                if child.name.startswith('.'):
                    continue
                yield child
    yield from _walk(root)

def orgin_rel_key(path: Path | str, orgin_dir: Path | str | None=None) -> str:
    root = Path(orgin_dir) if orgin_dir is not None else KNOWLEDGE_ORGIN
    p = Path(path)
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.name
KNOWLEDGE_MARKDOWN = KNOWLEDGE_DATA_ROOT / 'markdown'
KNOWLEDGE_MARKDOWN_PRODUCT = KNOWLEDGE_MARKDOWN / 'product'
KNOWLEDGE_MARKDOWN_QA = KNOWLEDGE_MARKDOWN / 'qa'
KNOWLEDGE_MANUAL = KNOWLEDGE_DATA_ROOT / 'manual'
KNOWLEDGE_SPEC = KNOWLEDGE_DATA_ROOT / 'spec'
KNOWLEDGE_SPEC_GENERATIONS = KNOWLEDGE_SPEC / 'generations'
KNOWLEDGE_SPEC_ACTIVE = KNOWLEDGE_SPEC / 'active.json'
SPEC_GENERATION_SCHEMA = 'ist.spec.generation'
SPEC_ACTIVE_SCHEMA = 'ist.spec.active'
_SPEC_POINTER_MAX_BYTES = 64 * 1024
_SPEC_MANIFEST_MAX_BYTES = 16 * 1024 * 1024
_SPEC_ARTIFACT_MAX_BYTES = 16 * 1024 * 1024
_SPEC_DOC_MAX_BYTES = 16 * 1024 * 1024
_GENERATION_ID_RE = re.compile('[0-9]{20}-[0-9a-f]{16}')
_SHA256_RE = re.compile('[0-9a-f]{64}')

class SpecGenerationUnavailable(RuntimeError):
    pass

def spec_generation_age_seconds(generation_id: str, *, now_ns: int | None=None) -> tuple[bool, int | None]:
    gid = str(generation_id or '')
    if _GENERATION_ID_RE.fullmatch(gid) is None:
        return (False, None)
    try:
        built_ns = int(gid[:20])
    except ValueError:
        return (False, None)
    clock = time.time_ns() if now_ns is None else int(now_ns)
    age_s = (clock - built_ns) // 1000000000
    if age_s < 0:
        age_s = 0
    return (True, int(age_s))

@dataclass(frozen=True)
class ActiveSpecGeneration:
    generation_id: str
    root: Path
    docs: Path
    state: Path
    index: Path
    manifest: Path
    manifest_sha256: str
    document_entries: dict[str, dict[str, int | str]]

def spec_store_root(project_root: Path | str | None=None) -> Path:
    if project_root is None:
        return KNOWLEDGE_SPEC
    return Path(project_root) / 'knowledge' / 'data' / 'spec'

def _read_spec_json(path: Path, *, label: str, max_bytes: int) -> tuple[bytes, dict]:
    try:
        raw = read_regular_nofollow(path, error_type=SpecGenerationUnavailable, invalid_message=f'{label}路径无效', directory_message=f'{label}目录不可安全读取', open_message=f'{label}不可读', bounds_message=f'{label}超出大小限制', changed_message=f'{label}读取期间发生变化', max_bytes=max_bytes, min_bytes=2)
        assert isinstance(raw, bytes)
        validate_json_budget(raw, error_type=SpecGenerationUnavailable, message=f'{label}结构超出限制')
        value = json.loads(raw.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SpecGenerationUnavailable(f'{label}不是有效 JSON') from exc
    if not isinstance(value, dict):
        raise SpecGenerationUnavailable(f'{label}结构无效')
    return (raw, value)

def _validate_manifest_entry(value: object, *, label: str, max_bytes: int) -> tuple[int, str]:
    if not isinstance(value, dict):
        raise SpecGenerationUnavailable(f'{label}清单项无效')
    size = value.get('size')
    digest = str(value.get('sha256') or '')
    if not isinstance(size, int) or isinstance(size, bool) or size < 1 or (size > max_bytes) or (_SHA256_RE.fullmatch(digest) is None):
        raise SpecGenerationUnavailable(f'{label}清单项无效')
    return (size, digest)

def _verify_generation_file(path: Path, *, label: str, expected: object, max_bytes: int) -> None:
    size, digest = _validate_manifest_entry(expected, label=label, max_bytes=max_bytes)
    payload = read_regular_nofollow(path, error_type=SpecGenerationUnavailable, invalid_message=f'{label}路径无效', directory_message=f'{label}目录不可安全读取', open_message=f'{label}不可读', bounds_message=f'{label}超出大小限制', changed_message=f'{label}读取期间发生变化', max_bytes=max_bytes, min_bytes=1)
    assert isinstance(payload, bytes)
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
        raise SpecGenerationUnavailable(f'{label}与活动代际清单不一致')

def _sealed_directory_entries(path: Path, *, label: str) -> dict[str, os.stat_result]:
    from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow
    descriptor = open_directory_nofollow(path, error_type=SpecGenerationUnavailable, invalid_message=f'{label}路径无效', unavailable_message=f'{label}不可安全读取')
    try:
        return {name: os.stat(name, dir_fd=descriptor, follow_symlinks=False) for name in os.listdir(descriptor)}
    finally:
        os.close(descriptor)

def resolve_active_spec_generation(project_root: Path | str | None=None, *, store_root: Path | str | None=None, verify_documents: bool=True) -> ActiveSpecGeneration:
    store = Path(store_root) if store_root is not None else spec_store_root(project_root)
    pointer_path = store / 'active.json'
    _pointer_raw, pointer = _read_spec_json(pointer_path, label='规格书活动指针', max_bytes=_SPEC_POINTER_MAX_BYTES)
    generation_id = str(pointer.get('generation_id') or '')
    expected_manifest_sha = str(pointer.get('manifest_sha256') or '')
    if not accepts_schema(pointer.get('schema'), SPEC_ACTIVE_SCHEMA) or _GENERATION_ID_RE.fullmatch(generation_id) is None or _SHA256_RE.fullmatch(expected_manifest_sha) is None or (set(pointer) != {'schema', 'generation_id', 'manifest_sha256'}):
        raise SpecGenerationUnavailable('规格书活动指针结构无效')
    generation_root = store / 'generations' / generation_id
    manifest_path = generation_root / 'manifest.json'
    manifest_raw, manifest = _read_spec_json(manifest_path, label='规格书代际清单', max_bytes=_SPEC_MANIFEST_MAX_BYTES)
    if hashlib.sha256(manifest_raw).hexdigest() != expected_manifest_sha:
        raise SpecGenerationUnavailable('规格书活动指针与代际清单不一致')
    if not accepts_schema(manifest.get('schema'), SPEC_GENERATION_SCHEMA) or manifest.get('generation_id') != generation_id or (not isinstance(manifest.get('created_at'), str)) or (not manifest.get('created_at')) or (set(manifest) != {'schema', 'generation_id', 'created_at', 'artifacts', 'documents'}):
        raise SpecGenerationUnavailable('规格书代际清单结构无效')
    artifacts = manifest.get('artifacts')
    documents = manifest.get('documents')
    if not isinstance(artifacts, dict) or set(artifacts) != {'state.tsv', 'index.json'} or (not isinstance(documents, dict)):
        raise SpecGenerationUnavailable('规格书代际清单结构无效')
    state_path = generation_root / 'state.tsv'
    index_path = generation_root / 'index.json'
    docs_path = generation_root / 'docs'
    _verify_generation_file(state_path, label='规格书同步台账', expected=artifacts['state.tsv'], max_bytes=_SPEC_ARTIFACT_MAX_BYTES)
    _verify_generation_file(index_path, label='规格书索引', expected=artifacts['index.json'], max_bytes=_SPEC_ARTIFACT_MAX_BYTES)
    normalized_docs: dict[str, dict[str, int | str]] = {}
    casefold_names: set[str] = set()
    for name, entry in documents.items():
        if not isinstance(name, str) or not name.endswith('.md') or Path(name).name != name or (name.casefold() in casefold_names):
            raise SpecGenerationUnavailable('规格书代际文档名无效')
        size, digest = _validate_manifest_entry(entry, label='规格书文档', max_bytes=_SPEC_DOC_MAX_BYTES)
        normalized_docs[name] = {'size': size, 'sha256': digest}
        casefold_names.add(name.casefold())
        if verify_documents:
            _verify_generation_file(docs_path / name, label='规格书文档', expected=entry, max_bytes=_SPEC_DOC_MAX_BYTES)
    root_entries = _sealed_directory_entries(generation_root, label='规格书代际目录')
    if set(root_entries) != {'docs', 'state.tsv', 'index.json', 'manifest.json'}:
        raise SpecGenerationUnavailable('规格书代际目录与清单不闭合')
    if not stat.S_ISDIR(root_entries['docs'].st_mode):
        raise SpecGenerationUnavailable('规格书代际 docs 不是普通目录')
    docs_entries = _sealed_directory_entries(docs_path, label='规格书代际 docs')
    if set(docs_entries) != set(normalized_docs) or any((not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 for info in docs_entries.values())):
        raise SpecGenerationUnavailable('规格书代际 docs 与清单不闭合')
    return ActiveSpecGeneration(generation_id=generation_id, root=generation_root, docs=docs_path, state=state_path, index=index_path, manifest=manifest_path, manifest_sha256=expected_manifest_sha, document_entries=normalized_docs)
WORKSPACE_DIR_NAME = 'workspace'
WORKSPACE_ROOT = PROJECT_ROOT / WORKSPACE_DIR_NAME
WORKSPACE_INPUTS = WORKSPACE_ROOT / 'inputs'
WORKSPACE_OUTPUTS = WORKSPACE_ROOT / 'outputs'
WORKSPACE_DEFECTS = WORKSPACE_ROOT / 'defects'
WORKSPACE_BUCKETS: tuple[str, ...] = ('inputs', 'outputs')

def set_current_username(name: str) -> None:
    _current_username_ctx.set(name)

def current_username() -> str:
    return _current_username_ctx.get().strip() or os.environ.get('IST_SSH_USER', '').strip() or 'tui'
_SCOPE_RE = re.compile('^[a-z0-9][a-z0-9_.@+-]{0,63}$')
_WINDOWS_RESERVED_SCOPE_BASENAMES = frozenset({'aux', 'con', 'nul', 'prn', *(f'com{index}' for index in range(1, 10)), *(f'lpt{index}' for index in range(1, 10))})

class ScopeUnavailable(PermissionError):
    pass

def validate_output_scope(name: str) -> str:
    scope = str(name or '').strip()
    device_basename = scope.split('.', 1)[0]
    if not _SCOPE_RE.fullmatch(scope) or scope.endswith('.') or device_basename in _WINDOWS_RESERVED_SCOPE_BASENAMES:
        raise ScopeUnavailable(f'unsafe output scope: {scope!r}')
    return scope

def multi_tenant() -> bool:
    return os.environ.get('IST_MULTI_TENANT', '').strip().lower() in {'1', 'true', 'yes'}

def process_tenant_from_env() -> bool:
    return os.environ.get('IST_PROCESS_TENANT_FROM_ENV', '').strip().lower() in {'1', 'true', 'yes'}

def output_scope() -> str:
    if not multi_tenant():
        return ''
    scope = _current_username_ctx.get().strip()
    if not scope and process_tenant_from_env():
        scope = os.environ.get('IST_SSH_USER', '').strip()
    if not scope:
        raise ScopeUnavailable('request identity is unavailable in multi-tenant mode')
    return validate_output_scope(scope)

def workspace_bucket_root(bucket: str, *, project_root: Path | None=None, workspace_root: Path | None=None) -> Path:
    """``…/workspace/<bucket>``——两个桶名字面量的唯一出处。

    根从哪来由调用方给：引擎侧传自己那份可注入的 ``_shared.project_root()``，
    沙箱侧传已 ``resolve()`` 过的 workspace 根，归档回放传归档根。两个参数都不给
    时用本模块的 ``WORKSPACE_ROOT``。
    """
    if bucket not in WORKSPACE_BUCKETS:
        raise ValueError(f'unknown workspace bucket: {bucket!r}')
    if project_root is not None and workspace_root is not None:
        raise TypeError('pass at most one of project_root / workspace_root')
    if workspace_root is not None:
        base = Path(workspace_root)
    elif project_root is not None:
        base = Path(project_root) / WORKSPACE_DIR_NAME
    else:
        base = WORKSPACE_ROOT
    return base / bucket

def scope_bucket(root: Path, *, scope: str | None=None) -> Path:
    """把当前用户段拼到桶根上；单租户（``output_scope()`` 为空）原样返回。

    ``root`` 由调用方给，是为了让「桶根是调用方模块的可替换全局」这一类读法
    （`provenance_ir` 的 ``WORKSPACE_OUTPUTS`` / ``WORKSPACE_INPUTS``）能用同一份
    拼法：那些名字被替换时，拼出来的路径必须跟着换。``scope`` 显式给出时不再问
    ``output_scope()``——调用方已经取过一次的场景省一次调用，且两次取值必然一致。
    """
    resolved = output_scope() if scope is None else scope
    return root / resolved if resolved else root

def scoped_bucket_root(bucket: str, *, project_root: Path | None=None, workspace_root: Path | None=None, scope: str | None=None) -> Path:
    """``…/workspace/<bucket>[/<用户段>]``——作用域化桶根的唯一解析器。"""
    return scope_bucket(workspace_bucket_root(bucket, project_root=project_root, workspace_root=workspace_root), scope=scope)

def scoped_outputs_root() -> Path:
    return scope_bucket(WORKSPACE_OUTPUTS)

def scoped_inputs_root() -> Path:
    return scope_bucket(WORKSPACE_INPUTS)

def user_output_dir() -> Path:
    d = scoped_outputs_root()
    d.mkdir(parents=True, exist_ok=True)
    return d

def compile_out_name() -> str:
    return os.environ.get('IST_COMPILE_OUT_NAME', '').strip()

def autoid_output_path(autoid: str, *parts: str) -> Path:
    base = user_output_dir()
    name = compile_out_name()
    if name:
        base = base / name
    base = base / autoid
    return base / parts[0] if parts else base
KNOWLEDGE_MINERU = KNOWLEDGE_INTERMEDIATE / 'mineru'
CACHE_JSON = KNOWLEDGE_INTERMEDIATE / '.cache.json'
KNOWLEDGE_FOOTPRINTS = KNOWLEDGE_ROOT / 'footprints'
KNOWLEDGE_FOOTPRINTS_NODES = KNOWLEDGE_FOOTPRINTS / 'nodes'

def footprint_nodes_dir(version: str | None=None) -> Path:
    if not version:
        return KNOWLEDGE_FOOTPRINTS_NODES
    return KNOWLEDGE_FOOTPRINTS / f'nodes_{version}'
KNOWLEDGE_FRAMEWORK_MIRROR = KNOWLEDGE_ROOT / 'framework' / 'mirror'
KNOWLEDGE_VERIFIED_PACKAGES = KNOWLEDGE_ROOT / 'framework' / 'verified'
KNOWLEDGE_AUTO_ENV = KNOWLEDGE_DATA_ROOT / 'auto_env'
KNOWLEDGE_AUTO_ENV_TOPOLOGY = KNOWLEDGE_AUTO_ENV / 'network_topology_rag.md'
KNOWLEDGE_AUTO_ENV_TOPOLOGY_JSON = KNOWLEDGE_AUTO_ENV / 'network_topology.json'
KNOWLEDGE_AUTO_ENV_ACTIONS_JSON = KNOWLEDGE_AUTO_ENV / 'execute_actions.json'
SPEC_NAME_RE = re.compile('(?<![a-z])spec(?:ification)?(?![a-z])', re.IGNORECASE)

def is_spec_document(name_or_path: str) -> bool:
    if not name_or_path:
        return False
    return bool(SPEC_NAME_RE.search(PurePosixPath(str(name_or_path).replace('\\', '/')).name))
_SOURCE_RETRIEVAL_PRIORITY_RULES: list[tuple[re.Pattern[str], int]] = [(re.compile('phaseII|phase_II', re.IGNORECASE), 35), (re.compile('^cli_', re.IGNORECASE), 100), (re.compile('^app_', re.IGNORECASE), 80), (re.compile('Design_Doc', re.IGNORECASE), 20), (re.compile('Project_Status', re.IGNORECASE), 15)]
DEFAULT_SOURCE_RETRIEVAL_PRIORITY = 50
SPEC_SOURCE_RETRIEVAL_PRIORITY = 120

def source_retrieval_priority(source_file_or_stem: str) -> int:
    if not source_file_or_stem:
        return DEFAULT_SOURCE_RETRIEVAL_PRIORITY
    key = source_file_or_stem.strip()
    if re.search('phaseII|phase_II', key, re.IGNORECASE):
        return 35
    if is_spec_document(key):
        return SPEC_SOURCE_RETRIEVAL_PRIORITY
    for pattern, score in _SOURCE_RETRIEVAL_PRIORITY_RULES:
        if pattern.search(key):
            return score
    return DEFAULT_SOURCE_RETRIEVAL_PRIORITY

def evidence_retrieval_priority(evidence: dict) -> int:
    if not isinstance(evidence, dict):
        return DEFAULT_SOURCE_RETRIEVAL_PRIORITY
    src = evidence.get('source_file') or evidence.get('stem') or ''
    return source_retrieval_priority(str(src))

def ensure_intermediate_dirs() -> None:
    for d in (KNOWLEDGE_INTERMEDIATE, KNOWLEDGE_MINERU):
        d.mkdir(parents=True, exist_ok=True)

def ensure_data_dirs() -> None:
    for d in (KNOWLEDGE_DATA_ROOT, KNOWLEDGE_ORGIN, KNOWLEDGE_MARKDOWN, KNOWLEDGE_MARKDOWN_PRODUCT, KNOWLEDGE_MARKDOWN_QA, KNOWLEDGE_MANUAL):
        d.mkdir(parents=True, exist_ok=True)

def ensure_workspace_dirs() -> None:
    for d in (WORKSPACE_ROOT, WORKSPACE_INPUTS, WORKSPACE_OUTPUTS, WORKSPACE_DEFECTS):
        d.mkdir(parents=True, exist_ok=True)
