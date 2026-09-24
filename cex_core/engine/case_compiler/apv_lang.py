# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/apv_lang.py（sha256 cae4536b6bf4dca2）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import re
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from cex_core.engine.case_compiler.ir_coverage import all_capability_names, classify_capability
from cex_core.engine.case_compiler.ir_coverage import load_atlas as _load_atlas
from cex_core.engine.common.schema_identity import accepts_schema
__all__ = ['SHELL_EXIT_CHANNEL_ON_DEVICE_CLI', 'observe_exit_channel_error', 'mirror_src', 'public_methods', 'host_slot_es', 'LIFECYCLE_FS', 'valid_es', 'APV_CMD_PRIMITIVE_FS', 'SEG_CMD_PRIMITIVE_FS', 'CMD_PRIMITIVE_FS', 'apv_full_fs', 'valid_fs_by_e', 'norm_action', 'execute_action_registry', 'execute_action_registry_by_dispatch', 'execute_dispatcher_for_e', 'execute_action_spec', 'execute_action_names', 'nearest_candidates', 'classify_capability', 'all_capability_names', 'APV_ACTION_SRC', 'CLIENT_ACTION_SRC', 'QueryUnavailable', 'atlas_available', 'capability_signature', 'dispatch_kind_of', 'dispatch_domain_orientation', 'capability_usage_of', 'dispatch_kind_cross_check', 'usage_index_corpus_meta', 'usage_index_empty_bucket_notes', 'apv_full_domains', 'host_observation', 'confirmation_prompt_of', 'language_document_catalog', 'param_contract_of', 'manual_param_excerpt', 'NOT_DIRECTLY_HIT', 'MANUAL_SOURCE_UNAVAILABLE', 'PARAM_CONTRACT_UNAVAILABLE']
_LANGUAGE_DOCS_INDEX_PATH = _cex_data_path('') / 'knowledge/data/compile_ref/language_docs_index.json'

def language_document_catalog(query: str='') -> dict:
    try:
        payload = json.loads(_LANGUAGE_DOCS_INDEX_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise QueryUnavailable(f'language_docs_index.json 不可达或损坏（{type(exc).__name__}）') from exc
    if not isinstance(payload, dict) or not accepts_schema(payload.get('schema'), 'ist.ide.language-docs') or (not isinstance(payload.get('entries'), list)):
        raise QueryUnavailable('language_docs_index.json schema mismatch')
    terms = [term.lower() for term in str(query or '').split() if term.strip()]
    matches = []
    for entry in payload['entries']:
        if not isinstance(entry, dict):
            continue
        searchable = json.dumps(entry, ensure_ascii=False, sort_keys=True).lower()
        if not terms or all((term in searchable for term in terms)):
            matches.append(entry)
    return {'schema': payload['schema'], 'query': str(query or ''), 'matches': matches}
NOT_DIRECTLY_HIT = '未在文档直接命中'
MANUAL_SOURCE_UNAVAILABLE = 'command_tree_unavailable'
PARAM_CONTRACT_UNAVAILABLE = 'projection_unavailable'

def _param_contract_unavailable(reason: str) -> dict:
    return {'status': PARAM_CONTRACT_UNAVAILABLE, 'reason': reason, 'head': '', 'version': None, 'device_os_build': None, 'args': [], 'selected': None}

def param_contract_of(command: str, position: int | None=None) -> dict | None:
    from cex_core.engine.case_compiler.vendor_stdlib import _head_candidate, load_vendor_stdlib
    tokens = str(command or '').split()
    if not tokens:
        return None
    inventory = load_vendor_stdlib()
    if inventory is None:
        return _param_contract_unavailable('command-tree projection could not be loaded')
    headers = inventory.get('headers')
    if not isinstance(headers, dict):
        return _param_contract_unavailable('command-tree projection has no usable XML headers map')
    candidate = _head_candidate(tokens, headers)
    if candidate is None:
        return None
    head, entry, _remainder = candidate
    args = [dict(item) for item in entry.get('args') or [] if isinstance(item, dict)]
    selected = None
    if position is not None:
        selected = next((item for item in args if item.get('position') == position), None)
    return {'head': head, 'version': inventory.get('version'), 'device_os_build': inventory.get('device_os_build'), 'args': args, 'selected': selected}

def manual_param_excerpt(command_head: str, *, max_lines: int=80) -> dict:
    from cex_core.engine.case_compiler.vendor_stdlib import manual_source_dir
    head = ' '.join(str(command_head or '').split())
    out: dict = {'hit': False, 'command': head, 'sections': [], 'note': ''}
    if not head:
        out['note'] = 'empty command head'
        return out
    root = manual_source_dir()
    if root is None:
        out['note'] = MANUAL_SOURCE_UNAVAILABLE
        return out
    src = root.relative_to(_cex_data_path('')).as_posix()
    syntax_prefix = f'**{head}**'
    for path in sorted(root.glob('*.md')):
        try:
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines):
            if not line.strip().startswith(syntax_prefix):
                continue
            end = min(len(lines), index + 1 + max_lines)
            for j in range(index + 1, end):
                if lines[j].strip().startswith('**'):
                    end = j
                    break
            window = lines[index:end]
            out['sections'].append({'file': f'{src}/{path.name}', 'line': index + 1, 'has_parameter_table': any((ln.strip().startswith('|') and '参数' in ln or '<table' in ln for ln in window)), 'text': '\n'.join(window)})
    if out['sections']:
        out['hit'] = True
    else:
        out['note'] = NOT_DIRECTLY_HIT
    return out
_MIRROR_ROOT = _cex_data_path('') / 'knowledge' / 'framework' / 'mirror'
_SOURCE_OVERLAY: dict | None = None

def _source_cached_functions() -> tuple:
    return tuple((value for value in list(globals().values()) if callable(getattr(value, 'cache_clear', None)) and getattr(value, '__module__', '') == __name__))

def _clear_source_caches() -> None:
    for fn in _source_cached_functions():
        fn.cache_clear()

@contextmanager
def source_overlay(sources):
    global _SOURCE_OVERLAY
    previous = _SOURCE_OVERLAY
    _SOURCE_OVERLAY = dict(sources) if sources else None
    _clear_source_caches()
    try:
        yield
    finally:
        _SOURCE_OVERLAY = previous
        _clear_source_caches()

def mirror_src(rel: str) -> str:
    if _SOURCE_OVERLAY is not None and rel in _SOURCE_OVERLAY:
        raw = _SOURCE_OVERLAY[rel]
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw).decode('utf-8', errors='replace')
        return str(raw)
    try:
        return (_MIRROR_ROOT / rel).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''

@lru_cache(maxsize=1)
def _devices_keys() -> frozenset:
    src = mirror_src('lib/test_xlsx.py')
    m = re.search('devices\\s*=\\s*\\{(.*?)\\}', src, re.S)
    return frozenset(re.findall("'([^']+)'\\s*:", m.group(1))) if m else frozenset()

@lru_cache(maxsize=1)
def host_slot_es() -> frozenset:
    conftest = mirror_src('smoke_test/conftest.py')
    slots = set()
    for m in re.finditer('def (\\w+)\\([^)]*\\):(.*?)(?=\\n@|\\ndef |\\Z)', conftest, re.S):
        if 'ssh_server(' in m.group(2) and 'class ' not in m.group(2):
            slots.add(m.group(1))
    return frozenset(slots & _devices_keys())

def public_methods(rel: str, cls: str) -> frozenset:
    src = mirror_src(rel)
    match = re.search(f'(?m)^(?P<indent>[ \\t]*)class[ \\t]+{re.escape(cls)}\\b[^\\n]*:\\s*$', src)
    if match is None:
        return frozenset()
    indent = match.group('indent')
    tail = src[match.end():]
    boundary = re.search(f'(?m)^{re.escape(indent)}(?:class[ \\t]|def[ \\t]|@)', tail)
    body = tail[:boundary.start()] if boundary is not None else tail
    method_indent = re.escape(indent + '    ')
    return frozenset(re.findall(f'(?m)^{method_indent}def[ \\t]+(\\w+)\\(', body))
LIFECYCLE_FS = frozenset({'__init__', 'xlsx_begin', 'read_until', 'close', 'soft_close', 'clear', 'delete_ip', 'delete_route', 'load_synonyms', 'check_direct_match', 'get_same', 'get_similar_function'})

@lru_cache(maxsize=1)
def valid_es() -> frozenset:
    keys = _devices_keys()
    return keys | {'check_point', 'time'} if keys else frozenset()
APV_CMD_PRIMITIVE_FS = frozenset({'cmd', 'cmd_enable', 'cmd_config', 'cmds_config'})
SEG_CMD_PRIMITIVE_FS = APV_CMD_PRIMITIVE_FS | {'array_config'}
CMD_PRIMITIVE_FS = SEG_CMD_PRIMITIVE_FS
_SEAT_RUNTIME_CLASS = {'apv': ('lib/apv/apv.py', 'APV', APV_CMD_PRIMITIVE_FS), 'segment': ('lib/apv/apv_ssh.py', 'APV_SSH', SEG_CMD_PRIMITIVE_FS)}

def _mirror_cmd_primitives(family: str) -> frozenset[str]:
    rel, cls, closure = _SEAT_RUNTIME_CLASS[family]
    declared = public_methods(rel, cls)
    if not declared:
        raise QueryUnavailable(f'mirror 中 {rel} 的 {cls} 类体解析为空；传输原语无法现算')
    return declared & closure

@lru_cache(maxsize=1)
def _apv_cmd_primitives() -> frozenset[str]:
    return _mirror_cmd_primitives('apv')

@lru_cache(maxsize=1)
def _seg_cmd_primitives() -> frozenset[str]:
    return _mirror_cmd_primitives('segment')

@lru_cache(maxsize=1)
def _segment_es() -> frozenset[str]:
    return frozenset((key for key in _devices_keys() if re.fullmatch('Seg\\d+_tmp', key)))

@lru_cache(maxsize=1)
def _apv_full_fs_by_family() -> dict[str, frozenset]:
    return {'ssl_comm': public_methods('lib/apv/ssl_comm.py', 'ssl_comm'), 'seg_comm': public_methods('lib/apv/seg_comm.py', 'seg_comm'), 'ha_comm': public_methods('lib/apv/ha_comm.py', 'ha_comm'), 'preparation': public_methods('lib/apv/preparation.py', 'preparation')}

@lru_cache(maxsize=1)
def apv_full_fs() -> frozenset:
    by_family = _apv_full_fs_by_family()
    if not any(by_family.values()):
        return frozenset()
    mixin_union = frozenset().union(*by_family.values()) - LIFECYCLE_FS
    return mixin_union | {'execute'} | _apv_cmd_primitives()

@lru_cache(maxsize=1)
def _segment_full_fs() -> frozenset:
    ssl = public_methods('lib/apv/ssl_comm.py', 'ssl_comm') - LIFECYCLE_FS
    prep = public_methods('lib/apv/preparation.py', 'preparation') - LIFECYCLE_FS
    if not ssl and (not prep):
        return frozenset()
    return ssl | prep | {'execute'} | _seg_cmd_primitives()

@lru_cache(maxsize=1)
def valid_fs_by_e() -> dict:
    env_hosts = public_methods('lib/env.py', 'Env') - LIFECYCLE_FS
    cp = public_methods('lib/check_point.py', 'Check_Point') - LIFECYCLE_FS
    slot_fs = public_methods('lib/ssh_server.py', 'ssh_server') - LIFECYCLE_FS
    out: dict = {}
    if env_hosts:
        out['test_env'] = env_hosts
    if cp:
        out['check_point'] = cp
    out['time'] = frozenset({'sleep'})
    if slot_fs:
        for slot in host_slot_es():
            out[slot] = slot_fs
    http_fs = public_methods('smoke_test/conftest.py', 'http_server') - LIFECYCLE_FS - {'start', 'stop'}
    if http_fs and 'http_server_231' in _devices_keys():
        out['http_server_231'] = http_fs
    apv_fs = apv_full_fs()
    if apv_fs:
        for e in ('APV_0', 'APV_1', 'APV_2'):
            out[e] = apv_fs
    segment_fs = _segment_full_fs()
    if segment_fs:
        for e in _segment_es():
            out[e] = segment_fs
    return out
APV_ACTION_SRC = 'lib/apv/apv_action.py'
CLIENT_ACTION_SRC = 'lib/client_action.py'
_APV_SYNONYMS_SRC = 'lib/apv/apv_synonyms'
_CLIENT_SYNONYMS_SRC = 'lib/client_synonyms'

def norm_action(s: str) -> str:
    return re.sub('\\s+', '', str(s).lower())

def _synonym_values_by_canonical(src_rel: str) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for line in mirror_src(src_rel).splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '：' not in line:
            continue
        canonical, values = line.split('：', 1)
        out[norm_action(canonical)] = tuple((value.strip() for value in values.split('，') if value.strip()))
    return out

def _mapping_action_names(src_rel: str) -> dict[str, str]:
    return {norm_action(name): name.strip() for name in re.findall("'([^']+)':\\s*self\\.func_\\d+", mirror_src(src_rel))}

@lru_cache(maxsize=1)
def execute_action_registry_by_dispatch() -> dict[str, dict[str, str]]:
    specs = (('apv', APV_ACTION_SRC, _APV_SYNONYMS_SRC), ('client', CLIENT_ACTION_SRC, _CLIENT_SYNONYMS_SRC))
    out: dict[str, dict[str, str]] = {}
    for dispatcher, mapping_src, synonym_src in specs:
        canonical = _mapping_action_names(mapping_src)
        aliases = _synonym_values_by_canonical(synonym_src)
        registry = dict(canonical)
        for canonical_norm, values in aliases.items():
            if canonical_norm not in canonical:
                continue
            for value in values:
                registry.setdefault(norm_action(value), value)
        out[dispatcher] = registry
    return out

def execute_dispatcher_for_e(e: str) -> str:
    value = str(e or '').strip()
    if value in {'APV_0', 'APV_1', 'APV_2'} or value in _segment_es():
        return 'apv'
    if value in host_slot_es():
        return 'client'
    return ''

@lru_cache(maxsize=1)
def execute_action_registry() -> dict:
    reg: dict[str, str] = {}
    for registry in execute_action_registry_by_dispatch().values():
        for normalized, original in registry.items():
            reg.setdefault(normalized, original)
    return reg

def execute_action_spec(e: str, action: str) -> dict | None:
    dispatcher = execute_dispatcher_for_e(e)
    if not dispatcher:
        return None
    normalized = norm_action(action)
    try:
        atlas = _load_atlas()
        info = atlas.get('execute_actions', {}).get('capabilities', {}).get(f'{dispatcher}:{normalized}')
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    allowed_es = {str(value) for value in info.get('allowed_es') or []}
    if str(e) not in allowed_es:
        return None
    return dict(info)

def execute_action_names() -> frozenset:
    return frozenset(execute_action_registry().keys())

def nearest_candidates(target: str, candidates, *, key=None, top_n: int=5) -> list[str]:
    from difflib import SequenceMatcher
    _key = key or (lambda c: c)
    ranked = sorted(candidates, key=lambda c: (-SequenceMatcher(None, target, _key(c)).ratio(), str(c)))
    return ranked[:top_n]

class QueryUnavailable(Exception):
    pass

def atlas_available() -> bool:
    try:
        _load_atlas()
        return True
    except (OSError, ValueError):
        return False

def capability_signature(name: str) -> dict | None:
    try:
        atlas = _load_atlas()
    except (OSError, ValueError) as exc:
        raise QueryUnavailable(f'capability_atlas.json 不可达或损坏（{type(exc).__name__}）') from exc
    apv_full = atlas.get('methods', {}).get('apv_full', {})
    for fam_name, fam in apv_full.items():
        info = (fam.get('methods') or {}).get(name)
        if info is not None:
            return {'required': info.get('required', []), 'optional': info.get('optional', []), 'source': info.get('source', ''), '_family': fam_name}
    return None

def dispatch_kind_of(f_name: str) -> str | None:
    by_family = _apv_full_fs_by_family()
    if not any(by_family.values()):
        raise QueryUnavailable('mirror 未读到 ssl_comm/seg_comm/ha_comm/preparation 任何内容(路径变更/离线),无法判定派发路径')
    if f_name in _apv_cmd_primitives():
        return 'cmd_primitive'
    if f_name == 'execute':
        return 'execute_registry'
    mixin_union = frozenset().union(*by_family.values()) - LIFECYCLE_FS
    if f_name in mixin_union:
        return 'direct_method_call'
    return None

def apv_full_domains() -> frozenset:
    try:
        atlas = _load_atlas()
    except (OSError, ValueError):
        return frozenset()
    return frozenset((atlas.get('methods', {}).get('apv_full', {}) or {}).keys())

def _domain_disambiguation(family: str, atlas: dict) -> str:
    if family != 'ssl_comm':
        return 'no curated disambiguation notes exist for this domain'
    parts: list[str] = []
    role_confusion = atlas.get('cert_role_confusion') or {}
    ca_family = role_confusion.get('ca_family')
    if ca_family:
        parts.append(f"role confusion: {ca_family} (source: {role_confusion.get('source', '')})")
    for name, info in (atlas.get('cert_behavior_notes') or {}).items():
        note = info.get('note')
        if note:
            parts.append(f"{name}: {note} (source: {info.get('source', '')})")
    return '\n'.join(parts) if parts else 'no curated disambiguation notes exist for this domain'

def dispatch_domain_orientation(domain: str) -> dict:
    try:
        atlas = _load_atlas()
    except (OSError, ValueError) as exc:
        raise QueryUnavailable(f'capability_atlas.json 不可达或损坏（{type(exc).__name__}）') from exc
    apv_full = atlas.get('methods', {}).get('apv_full', {}) or {}
    if domain not in apv_full:
        raise ValueError(f'unknown domain {domain!r} — must be one of {sorted(apv_full)}')
    methods = (apv_full.get(domain, {}) or {}).get('methods') or {}
    names = sorted(methods.keys())
    if not names:
        raise QueryUnavailable(f'atlas 里 {domain!r} family 是空的(生成异常),无法给域级 orientation')
    disabled = {n: info.get('reason', '') for n, info in methods.items() if info.get('disabled')}
    kind = dispatch_kind_of(names[0])
    return {'domain': domain, 'dispatch_kind': kind, 'n': len(names), 'names': names, 'disabled': disabled, 'disambiguation': _domain_disambiguation(domain, atlas), 'signatures_omitted': True}

def _atlas_dispatch_kind_raw(name: str) -> str | None:
    try:
        atlas = _load_atlas()
    except (OSError, ValueError):
        return None
    apv_full = atlas.get('methods', {}).get('apv_full', {})
    for fam in apv_full.values():
        info = (fam.get('methods') or {}).get(name)
        if info is not None:
            return info.get('dispatch_kind')
    return None

def dispatch_kind_cross_check(name: str) -> dict:
    live = dispatch_kind_of(name)
    atlas_value = _atlas_dispatch_kind_raw(name)
    stale = atlas_value is not None and live is not None and (atlas_value != live)
    return {'live': live, 'atlas': atlas_value, 'stale': stale}
_USAGE_INDEX_PATH = _cex_data_path('') / 'knowledge/data/compile_ref/capability_usage_index.json'
_USAGE_SAMPLE_N = 3

def _load_usage_index() -> dict:
    return json.loads(_USAGE_INDEX_PATH.read_text(encoding='utf-8'))

def capability_usage_of(name: str) -> dict | None:
    try:
        idx = _load_usage_index()
    except (OSError, ValueError) as exc:
        raise QueryUnavailable(f'capability_usage_index.json 不可达或损坏（{type(exc).__name__}）') from exc
    meta = idx.get('_meta') or {}
    if meta.get('corpus_status') != 'ready':
        raise QueryUnavailable('the engine-owned device-verified corpus is unavailable; an empty authored index is not a confirmed zero-hit result')
    for bucket in ('by_f_value', 'by_execute_action'):
        entry = (idx.get(bucket) or {}).get(name)
        if entry is not None:
            usages = entry.get('usages') or []
            return {'count': entry.get('count', len(usages)), 'samples': usages[:_USAGE_SAMPLE_N], 'bucket': bucket, 'corpus_file_count': int((idx.get('_meta') or {}).get('corpus_file_count') or 0)}
    return None

def usage_index_corpus_meta() -> dict:
    try:
        idx = _load_usage_index()
    except (OSError, ValueError):
        return {}
    meta = idx.get('_meta') or {}
    return {key: meta.get(key) for key in ('corpus_file_count', 'total_rows_scanned', 'source_manifest_sha256', 'corpus_definition', 'corpus_status', 'corpus_absence_reason') if meta.get(key) is not None}

def usage_index_empty_bucket_notes() -> dict:
    try:
        idx = _load_usage_index()
    except (OSError, ValueError):
        return {}
    meta = idx.get('_meta') or {}
    return {k: v for k, v in meta.items() if k.endswith('_empty_reason')}
_HOST_CORPUS_META_KEYS = ('corpus_file_count', 'corpus_status', 'corpus_absence_reason', 'vendor_corpus_file_count', 'vendor_scanned_file_count', 'vendor_unreadable_files', 'vendor_host_rows', 'vendor_source_manifest_sha256', 'vendor_commands_cap_per_first_token', 'vendor_command_text_max_chars', 'vendor_redacted_rows', 'host_key_space_sources')

def host_observation(name: str) -> dict:
    try:
        idx = _load_usage_index()
    except (OSError, ValueError) as exc:
        raise QueryUnavailable(f'capability_usage_index.json 不可达或损坏（{type(exc).__name__}）') from exc
    meta = idx.get('_meta') or {}
    key_space = list(meta.get('host_key_space') or [])
    return {'host': name, 'host_key_space': key_space, 'is_known_host': name in key_space, 'vendor': (idx.get('vendor_host_observations') or {}).get(name), 'authored': (idx.get('authored_host_usage') or {}).get(name), 'corpus': {key: meta.get(key) for key in _HOST_CORPUS_META_KEYS if meta.get(key) is not None}}
_CONFIRMATION_PATTERNS_PATH = _cex_data_path('') / 'knowledge/data/compile_ref/confirmation_prompt_patterns.json'

def _load_confirmation_patterns() -> dict:
    return json.loads(_CONFIRMATION_PATTERNS_PATH.read_text(encoding='utf-8'))

def confirmation_prompt_of(name: str) -> dict | None:
    try:
        data = _load_confirmation_patterns()
    except (OSError, ValueError) as exc:
        raise QueryUnavailable(f'confirmation_prompt_patterns.json 不可达或损坏（{type(exc).__name__}）') from exc
    for entry in data.get('lib_patterns', []):
        if (entry.get('provenance') or {}).get('function') == name:
            return entry
    return None
PARAM_SPLIT_RE = re.compile('((?:(?:"(?:\\\\.|[^\\\\"])*"|\\\'(?:\\\\.|[^\\\\\\\'])*\\\'|[^,])+))')
_PARAM_SPLIT_RE = PARAM_SPLIT_RE
SHELL_EXIT_CHANNEL_ON_DEVICE_CLI = False

def observe_exit_channel_error(host: str) -> str:
    name = str(host or '').strip() or 'the device under test'
    return f"OBSERVE_EXIT on {name!r} is not supported: {name} is an APV CLI host and the framework sends the G cell verbatim to the product CLI (cmd_config), so the shell exit-status wrapper `( cmd ); ist_case_exit_code=$?; …` has no channel there and would be rejected as a non-CLI command. Observe the product command's outcome with OBSERVE_ASSERT (found / abs_found on its output), or place the configuration in CONFIG; OBSERVE_EXIT is for shell hosts reached through test_env (routera / routerb / server*)."
