# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/vendor_stdlib.py（sha256 424b676b61e7d7e3）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import hashlib
import functools
import ipaddress
import logging
import os
import re
import shlex
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
logger = logging.getLogger(__name__)
_ROOT = _cex_data_path('')
_DEFAULT_INV_DIR = _ROOT / 'knowledge' / 'data' / 'compile_ref'
_INV_DIR = _DEFAULT_INV_DIR
_COMMAND_TREE_STORE_ROOT = _ROOT / 'runtime' / 'command_tree'
_CACHE: dict[tuple, dict] = {}
_ENV_CAPABILITIES = _ROOT / 'knowledge' / 'data' / 'auto_env' / 'env_capabilities.json'
_CANONICAL_RE = re.compile('^vendor_stdlib_(?P<version>\\d+(?:\\.\\d+)*)_(?P<build>[A-Za-z0-9_.-]+)\\.json$')
_MAX_HEAD_TOKENS = 8
_EXECUTABLE_ARGUMENT_TYPES = frozenset({'STRING', 'XSTRING', 'U16', 'U32', 'IPADDR', 'DOTTEDIP', 'IPMASK'})
_REDACTED_ARGUMENT_TYPE = 'REDACTED_SENSITIVE'
_VALUE_DOMAIN_KINDS = frozenset({'enum', 'union', 'range', 'length', 'default'})
_VALUE_DOMAIN_SOURCES = frozenset({'xml_limit', 'xml_help', 'manual_table', 'footprint'})
_CLOSED_SET_ENUM_SOURCES = frozenset({'xml_limit', 'manual_table', 'footprint'})
XML_COMMAND_NOT_FOUND = 'command_not_found'

def _command_tree_store_root() -> Path:
    if _INV_DIR != _DEFAULT_INV_DIR:
        return _INV_DIR / 'command_tree'
    return _COMMAND_TREE_STORE_ROOT

def _build_suffix(build: str) -> str:
    value = str(build or '').strip()
    match = re.search('(?:^|[._-])(\\d+)$', value)
    return match.group(1) if match else value

def configured_device_os_build_identity() -> str:
    explicit = os.getenv('IST_DEVICE_OS_BUILD', '').strip()
    if explicit:
        return explicit
    try:
        payload = json.loads(_ENV_CAPABILITIES.read_text(encoding='utf-8'))
        return str(payload.get('build') or '').strip()
    except Exception:
        logger.debug('设备 OS build 事实源读取失败: %s', _ENV_CAPABILITIES, exc_info=True)
        return ''

def device_os_build_suffix(build: str) -> str:
    return _build_suffix(build)

def _inventory_version_from_device_build(build: str) -> str:
    value = str(build or '').strip()
    if not value:
        return ''
    try:
        from cex_core.engine.sync.command_tree_sync import inventory_version_from_build
        return inventory_version_from_build(value)
    except Exception:
        return ''

def _product_platform_from_device_build(build: str) -> tuple[str, str]:
    value = str(build or '').strip()
    if not value:
        return ('', '')
    try:
        from cex_core.engine.sync.command_tree_sync import parse_build_identity
        identity = parse_build_identity(value)
        return (identity.product, identity.platform)
    except Exception:
        return ('', '')

def configured_device_os_build() -> str:
    explicit = os.getenv('IST_DEVICE_OS_BUILD', '').strip()
    if explicit:
        return _build_suffix(explicit)
    try:
        payload = json.loads(_ENV_CAPABILITIES.read_text(encoding='utf-8'))
        return _build_suffix(str(payload.get('build') or ''))
    except Exception:
        logger.debug('设备 OS build 事实源读取失败: %s', _ENV_CAPABILITIES, exc_info=True)
        return ''

def _product_platform_from_command_tree_partition(ver: str, build: str) -> tuple[str, str]:
    if not ver or not build:
        return ('', '')
    root = _command_tree_store_root() / 'products'
    if not root.is_dir() or root.is_symlink():
        return ('', '')
    hits: list[tuple[str, str]] = []
    try:
        for product_dir in sorted(root.iterdir()):
            platforms = product_dir / 'platforms'
            if product_dir.is_symlink() or not platforms.is_dir():
                continue
            for platform_dir in sorted(platforms.iterdir()):
                if platform_dir.is_symlink():
                    continue
                partition = platform_dir / 'builds' / f'{ver}_{build}'
                if partition.is_dir() and (not partition.is_symlink()):
                    hits.append((product_dir.name, platform_dir.name))
    except OSError:
        return ('', '')
    return hits[0] if len(hits) == 1 else ('', '')

def vendor_stdlib_path(version: str, device_build: str='') -> Path:
    raw_build = device_build or configured_device_os_build()
    build = _build_suffix(raw_build)
    ver = str(version or '').strip() or _inventory_version_from_device_build(raw_build)
    product, platform = _product_platform_from_device_build(raw_build)
    if not (product and platform):
        product, platform = _product_platform_from_command_tree_partition(ver, build)
    if product and platform and ver and build:
        try:
            from cex_core.engine.sync.command_tree_sync import resolve_active_command_tree
            active = resolve_active_command_tree(product=product, platform=platform, version=ver, device_build=build, store_root=_command_tree_store_root())
            if active is not None:
                return active.projection_path
        except Exception:
            pass
    return _INV_DIR / f'vendor_stdlib_{ver or version}_{build}.json'

def available_vendor_builds(version: str='', *, product: str='', platform: str='') -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in _INV_DIR.glob('vendor_stdlib_*.json'):
        match = _CANONICAL_RE.match(path.name)
        if not match:
            continue
        pair = (match.group('version'), match.group('build'))
        if not version or pair[0] == version:
            found.append(pair)
    products_root = _command_tree_store_root() / 'products'
    if str(product or '') and str(platform or ''):
        scan_dirs: list[tuple[str, str]] = [(str(product), str(platform))]
    elif products_root.is_dir() and (not products_root.is_symlink()):
        scan_dirs = []
        try:
            for product_dir in sorted(products_root.iterdir()):
                if product_dir.is_symlink():
                    continue
                if product and product_dir.name != str(product):
                    continue
                platforms_dir = product_dir / 'platforms'
                if not platforms_dir.is_dir() or platforms_dir.is_symlink():
                    continue
                for platform_dir in sorted(platforms_dir.iterdir()):
                    if platform_dir.is_symlink():
                        continue
                    if platform and platform_dir.name != str(platform):
                        continue
                    scan_dirs.append((product_dir.name, platform_dir.name))
        except OSError:
            scan_dirs = []
    else:
        scan_dirs = []
    for scan_product, scan_platform in scan_dirs:
        command_tree_builds = products_root / scan_product / 'platforms' / scan_platform / 'builds'
        if not command_tree_builds.is_dir() or command_tree_builds.is_symlink():
            continue
        for partition in sorted(command_tree_builds.iterdir()):
            match = re.fullmatch('(?P<version>\\d+(?:\\.\\d+)*)_(?P<build>\\d+)', partition.name)
            if match is None or partition.is_symlink():
                continue
            pair = (match.group('version'), match.group('build'))
            if version and pair[0] != version:
                continue
            try:
                from cex_core.engine.sync.command_tree_sync import resolve_active_command_tree
                if resolve_active_command_tree(product=scan_product, platform=scan_platform, version=pair[0], device_build=pair[1], store_root=_command_tree_store_root()) is not None:
                    found.append(pair)
            except Exception:
                continue
    return sorted(set(found))

def available_versions() -> list[str]:
    return sorted({version for version, _build in available_vendor_builds()})

def clear_vendor_stdlib_cache(version: str='', device_build: str='') -> None:
    ver = str(version or '').strip()
    build = _build_suffix(device_build)
    for key in list(_CACHE):
        key_ver = str(key[0]) if len(key) > 0 else ''
        key_build = str(key[1]) if len(key) > 1 else ''
        if (not ver or key_ver == ver) and (not build or key_build == build):
            _CACHE.pop(key, None)
_SCOPE_NO_CLUE = '本机还没有可用的命令树代际：compile_ref 下没有平面 vendor_stdlib 投影，runtime/command_tree 里也没有对应分区，而设备 build 只是个裸号、不带产品与平台身份，无参推导除了那份平面副本没有第二处线索。先开一次批（入口会按真机 build 收敛命令树投影），或显式给出版本与 build。'

def _scope_ambiguous(candidates: list[tuple[str, str]]) -> str:
    listed = '、'.join((f'{ver}_{build}' for ver, build in candidates))
    return f'本机有 {len(candidates)} 个命令树代际候选（{listed}），无参推导不替人择一：显式给出版本与 build。'

def _command_tree_scope(version: str='', device_build: str='', *, gap: dict[str, str] | None=None) -> tuple[str, str, str, str] | None:
    raw_build = device_build or configured_device_os_build()
    product, platform = _product_platform_from_device_build(raw_build)
    ver = (version or os.getenv('IST_COMMAND_INVENTORY_VERSION', '') or _inventory_version_from_device_build(raw_build)).strip()
    build = _build_suffix(raw_build)
    if not ver:
        candidates = available_vendor_builds(product=product, platform=platform)
        if build:
            candidates = [pair for pair in candidates if pair[1] == build]
        if len(candidates) != 1:
            if gap is not None:
                gap['reason'] = _SCOPE_NO_CLUE if not candidates else _scope_ambiguous(candidates)
            return None
        ver, build = candidates[0]
    if not build:
        candidates = available_vendor_builds(ver, product=product, platform=platform)
        if len(candidates) != 1:
            if gap is not None:
                gap['reason'] = _SCOPE_NO_CLUE if not candidates else _scope_ambiguous(candidates)
            return None
        _version, build = candidates[0]
    if not (product and platform) and ver and build:
        product, platform = _product_platform_from_command_tree_partition(ver, build)
    return (product, platform, ver, build)

def diagnose_active_command_tree(version: str='', device_build: str='', *, store_root: Path | None=None) -> tuple[str, str]:
    gap: dict[str, str] = {}
    scope = _command_tree_scope(version, device_build, gap=gap)
    if scope is None:
        return ('absent', gap.get('reason') or '推不出唯一的命令树作用域（版本 / build 有多个候选或缺席）')
    product, platform, ver, build = scope
    if not (product and platform):
        return ('absent', '命令树分区缺产品 / 平台身份')
    from cex_core.engine.sync.command_tree_sync import CommandTreeProjectionPolicyStale, CommandTreeSyncError, resolve_active_command_tree
    try:
        active = resolve_active_command_tree(product=product, platform=platform, version=ver, device_build=build, store_root=store_root or _command_tree_store_root())
    except CommandTreeProjectionPolicyStale as exc:
        return ('stale_policy', str(exc) or type(exc).__name__)
    except CommandTreeSyncError as exc:
        return ('corrupt', str(exc) or type(exc).__name__)
    except Exception as exc:
        return ('corrupt', f'{type(exc).__name__}')
    if active is None:
        builds_dir = Path(store_root or _command_tree_store_root()) / 'products' / product / 'platforms' / platform / 'builds'
        present: list[str] = []
        if builds_dir.is_dir() and (not builds_dir.is_symlink()):
            try:
                present = sorted((entry.name for entry in builds_dir.iterdir() if entry.is_dir() and (not entry.is_symlink())))
            except OSError:
                present = []
        listed = '、'.join(present) or '无'
        return ('absent', f'本地没有该 build 的活动代际（查询钥匙 {ver}_{build}；本机 {product}/{platform} 在册分区：{listed}）')
    return ('ok', '')

def load_vendor_stdlib(version: str='', device_build: str='') -> dict | None:
    scope = _command_tree_scope(version, device_build)
    if scope is None:
        return None
    product, platform, ver, build = scope
    active = None
    try:
        from cex_core.engine.sync.command_tree_sync import resolve_active_command_tree
        if product and platform:
            active = resolve_active_command_tree(product=product, platform=platform, version=ver, device_build=build, store_root=_command_tree_store_root())
    except Exception:
        logger.error('vendor 命令树活动代际损坏: version=%s build=%s', ver, build, exc_info=True)
        return None
    p = active.projection_path if active is not None else _INV_DIR / f'vendor_stdlib_{ver}_{build}.json'
    asset_dir = active.generation_root if active is not None else _INV_DIR
    cache_key = (ver, build, str(p))
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    legacy_cache_key = (ver, build)
    if active is None and legacy_cache_key in _CACHE:
        return _CACHE[legacy_cache_key]
    return _load_vendor_stdlib_asset(version=ver, build=build, projection_path=p, asset_dir=asset_dir, cache_key=cache_key, expected_projection_sha=active.projection_sha256 if active is not None else '', expected_source_sha=active.source_sha256 if active is not None else '')

def derive_inverse_pairs(version: str='', device_build: str='') -> dict[str, dict]:
    inventory = load_vendor_stdlib(version, device_build)
    if not inventory:
        return {}
    heads = inventory.get('heads') or inventory.get('headers') or {}
    if not isinstance(heads, dict) or not heads:
        return {}
    source_sha = str((inventory.get('source') or {}).get('sha256') or '')
    ver = str(inventory.get('version') or version or '')
    build = str(inventory.get('device_os_build') or device_build or '')
    return _derive_inverse_pairs_cached(ver, build, source_sha, tuple(sorted(heads)))

@functools.lru_cache(maxsize=8)
def _derive_inverse_pairs_cached(version: str, device_build: str, source_sha: str, head_names: tuple[str, ...]) -> dict[str, dict]:
    hset = set(head_names)

    def anc(prefix: str, h: str) -> str | None:
        ws = h.split()
        for k in range(len(ws), 0, -1):
            if k == 1 and len(ws) > 1:
                continue
            cand = f"{prefix} {' '.join(ws[:k])}"
            if cand in hset:
                return cand
        return None
    pairs: dict[str, dict] = {}
    for h in head_names:
        if h.startswith(('show ', 'no ', 'clear ')):
            continue
        inv_no = anc('no', h)
        inv_clear = anc('clear', h)
        if inv_no or inv_clear:
            pairs[h] = {'no': inv_no, 'clear': inv_clear, 'src': f'vendor_heads:{source_sha[:12]}'}
    return pairs

def manual_source_dir(version: str='', device_build: str='') -> Path | None:
    inventory = load_vendor_stdlib(version, device_build)
    if inventory is None:
        return None
    rel = str(inventory.get('source_dir') or '')
    if not rel:
        return None
    root = _cex_data_path('') / rel
    return root if root.is_dir() else None

def load_vendor_stdlib_generation(*, product: str, platform: str, version: str, device_build: str, generation_id: str, manifest_sha256: str, store_root: Path | None=None) -> dict | None:
    ver = str(version or '').strip()
    build = _build_suffix(device_build)
    prod = str(product or '').strip()
    plat = str(platform or '').strip()
    if not prod or not plat or (not ver) or (not build) or (not generation_id) or (not manifest_sha256):
        return None
    try:
        from cex_core.engine.sync.command_tree_sync import resolve_command_tree_generation
        generation = resolve_command_tree_generation(product=prod, platform=plat, version=ver, device_build=build, generation_id=str(generation_id).strip(), manifest_sha256=str(manifest_sha256).strip().lower(), store_root=store_root or _command_tree_store_root())
    except Exception:
        logger.error('vendor 命令树指定代际不可密封: version=%s build=%s generation=%s', ver, build, str(generation_id)[:60], exc_info=True)
        return None
    return _load_vendor_stdlib_asset(version=ver, build=build, projection_path=generation.projection_path, asset_dir=generation.generation_root, cache_key=(ver, build, generation.generation_id, generation.manifest_sha256), expected_projection_sha=generation.projection_sha256, expected_source_sha=generation.source_sha256)

def _load_vendor_stdlib_asset(*, version: str, build: str, projection_path: Path, asset_dir: Path, cache_key: tuple, expected_projection_sha: str='', expected_source_sha: str='') -> dict | None:
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    try:
        from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
        raw = read_regular_nofollow(projection_path, error_type=ValueError, invalid_message='vendor projection path is invalid', directory_message='vendor projection directory is unavailable', open_message='vendor projection is unavailable', bounds_message='vendor projection exceeds size budget', changed_message='vendor projection changed while reading', max_bytes=16 * 1024 * 1024, min_bytes=1)
        assert isinstance(raw, bytes)
        if expected_projection_sha and hashlib.sha256(raw).hexdigest() != expected_projection_sha:
            return None
        data = json.loads(raw.decode('utf-8'))
    except Exception:
        logger.debug('vendor 标准库读取失败: %s', projection_path, exc_info=True)
        return None
    from cex_core.engine.common.schema_identity import accepts_schema
    if not accepts_schema(data.get('schema'), 'ist.vendor_stdlib') or str(data.get('version') or '') != version or _build_suffix(str(data.get('device_os_build') or '')) != build or (not isinstance(data.get('headers'), dict)) or (not isinstance(data.get('manual_declarations'), dict)):
        return None
    if not _projection_xml_identity_valid(data, build, asset_dir=asset_dir, expected_source_sha=expected_source_sha):
        return None
    if not _projection_contract_valid(data):
        return None
    headers = data['headers']
    manual_declarations = data['manual_declarations']
    overlap = sorted(set(headers).intersection(manual_declarations))
    if overlap:
        logger.error('vendor 标准库含未对账的同名声明，拒绝构造 heads: %s', overlap[:20])
        return None
    data['heads'] = dict(headers)
    data['heads'].update(manual_declarations)
    _CACHE[cache_key] = data
    return data

def _projection_xml_identity_valid(data: dict, build: str, *, asset_dir: Path | None=None, expected_source_sha: str='') -> bool:
    source = data.get('source')
    if not isinstance(source, dict):
        return False
    filename = str(source.get('filename') or '').strip()
    expected_sha = str(source.get('sha256') or '').strip().lower()
    if source.get('kind') != 'vendor_command_tree_xml' or _build_suffix(str(source.get('device_os_build') or '')) != build or (not filename) or (Path(filename).name != filename) or (_build_suffix(Path(filename).stem) != build) or (not re.fullmatch('[0-9a-f]{64}', expected_sha)):
        return False
    xml_path = (asset_dir or _INV_DIR) / filename
    try:
        from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
        raw = read_regular_nofollow(xml_path, error_type=ValueError, invalid_message='vendor XML path is invalid', directory_message='vendor XML directory is unavailable', open_message='vendor XML is unavailable', bounds_message='vendor XML exceeds size budget', changed_message='vendor XML changed while reading', max_bytes=16 * 1024 * 1024, min_bytes=1)
        from cex_core.engine.sync.command_tree_sync import preflight_command_tree_xml
        preflight_command_tree_xml(raw, max_bytes=16 * 1024 * 1024, error_type=ValueError)
        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != expected_sha:
            logger.error('vendor XML SHA 与投影不一致: %s', xml_path)
            return False
        if expected_source_sha and actual_sha != expected_source_sha:
            logger.error('vendor XML SHA 与代际 manifest 不一致: %s', xml_path)
            return False
        root = ET.fromstring(raw)
    except (OSError, ValueError, ET.ParseError):
        logger.error('vendor XML 不可读取或不可解析: %s', xml_path, exc_info=True)
        return False
    if root.tag != 'commands' or root.find('scope') is None:
        logger.error('vendor XML 根结构不符合 commands/scope 契约: %s', xml_path)
        return False
    xml_nodes: set[str] = set()
    node_count = 0
    stack: list[tuple[ET.Element, tuple[str, ...], int]] = [(root, (), 1)]
    while stack:
        node, prefix, depth = stack.pop()
        node_count += 1
        if node_count > 250000 or depth > 96:
            logger.error('vendor XML 结构预算超限: %s', xml_path)
            return False
        children = list(node)
        for child in reversed(children):
            if child.tag == 'scope':
                part = str(child.get('type') or '').strip()
            elif child.tag in {'menu', 'item'}:
                part = str(child.get('name') or '').strip()
            else:
                stack.append((child, prefix, depth + 1))
                continue
            next_prefix = prefix + ((part,) if part else ())
            if child.tag == 'item' and next_prefix:
                xml_nodes.add('/'.join(next_prefix).casefold())
            stack.append((child, next_prefix, depth + 1))
    for entry in (data.get('headers') or {}).values():
        src = str((entry or {}).get('src') or '')
        prefix = f'vendor_xml:{build}:'
        if not src.startswith(prefix) or src[len(prefix):].casefold() not in xml_nodes:
            logger.error('vendor 投影节点不在绑定 XML 内: %s', src)
            return False
    return True

def _projection_contract_valid(data: dict) -> bool:
    headers = data.get('headers') or {}
    stats = data.get('stats') or {}
    if not isinstance(stats, dict):
        return False
    declared_count = stats.get('vendor_header_count')
    if declared_count is not None:
        try:
            if int(declared_count) != len(headers):
                return False
        except (TypeError, ValueError):
            return False
    for head, entry in headers.items():
        if not isinstance(head, str) or not head.strip() or (not isinstance(entry, dict)):
            return False
        try:
            pmax = int(entry.get('pmax'))
        except (TypeError, ValueError):
            return False
        args = entry.get('args')
        if pmax < 0 or not isinstance(args, list):
            return False
        if 'enums' in entry:
            return False
        if len(args) > pmax:
            return False
        for schema in [args, *(entry.get('arg_variants') or [])]:
            if not isinstance(schema, list):
                return False
            for pos, arg in enumerate(schema, start=1):
                try:
                    position = int(arg.get('position') or 0) if isinstance(arg, dict) else 0
                except (TypeError, ValueError):
                    return False
                if not isinstance(arg, dict):
                    return False
                arg_type = str(arg.get('type') or '')
                if position != pos or arg_type not in _EXECUTABLE_ARGUMENT_TYPES | {_REDACTED_ARGUMENT_TYPE} or (not isinstance(arg.get('optional'), bool)):
                    return False
                if arg_type == _REDACTED_ARGUMENT_TYPE:
                    if set(arg) != {'position', 'type', 'optional', 'executable'} or arg.get('executable') is not False:
                        return False
                elif 'executable' in arg:
                    return False
                if 'value_domain' in arg and (not _value_domain_valid(arg['value_domain'])):
                    return False
    return True

def _value_domain_valid(domain: object) -> bool:
    if not isinstance(domain, dict) or not domain:
        return False
    if set(domain) - _VALUE_DOMAIN_KINDS:
        return False
    for kind, claims in domain.items():
        if not isinstance(claims, list) or not claims:
            return False
        for claim in claims:
            if not isinstance(claim, dict):
                return False
            if str(claim.get('source') or '') not in _VALUE_DOMAIN_SOURCES or not str(claim.get('locator') or ''):
                return False
            if kind == 'enum':
                values = claim.get('values')
                if set(claim) != {'values', 'source', 'locator'} or not isinstance(values, list) or len(values) < 2 or (not all((isinstance(item, str) and item for item in values))):
                    return False
            elif kind == 'union':
                separator = claim.get('separator')
                if set(claim) != {'separator', 'source', 'locator'} or not isinstance(separator, str) or len(separator) != 1 or separator.isalnum() or separator.isspace():
                    return False
            elif kind == 'default':
                if set(claim) != {'value', 'source', 'locator'} or not isinstance(claim.get('value'), str) or (not claim['value']):
                    return False
            else:
                low = claim.get('min')
                high = claim.get('max')
                if set(claim) != {'min', 'max', 'source', 'locator'} or not isinstance(low, int) or (not isinstance(high, int)) or isinstance(low, bool) or isinstance(high, bool) or (low > high):
                    return False
    return True

def norm_command_tokens(cmd: str) -> list[str]:
    return _norm_tokens(cmd)

def strip_token_quotes(token: str) -> str:
    text = str(token or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and (text[0] in '"\''):
        return text[1:-1]
    return text

def match_command_head(tokens: list[str], heads: dict) -> tuple[str, dict] | None:
    return _try_match(tokens, heads)

def _norm_tokens(cmd: str) -> list[str]:
    value = (cmd or '').strip()
    if not value:
        return []
    try:
        return [token.lower() for token in shlex.split(value, posix=True)]
    except ValueError:
        return [strip_token_quotes(part).lower() for part in re.sub('\\s+', ' ', value.lower()).split(' ') if part]

def _head_candidate(tokens: list[str], heads: dict) -> tuple[str, dict, list[str]] | None:
    for k in range(min(len(tokens), _MAX_HEAD_TOKENS), 0, -1):
        head = ' '.join(tokens[:k])
        entry = heads.get(head)
        if isinstance(entry, dict):
            return (head, entry, tokens[k:])
    return None

def _value_matches_type(value: str, arg_type: str) -> bool:
    if arg_type == 'STRING':
        return True
    if arg_type == 'XSTRING':
        return bool(value)
    if arg_type in {'U16', 'U32'}:
        if not re.fullmatch('\\d+', value):
            return False
        number = int(value)
        return number <= (65535 if arg_type == 'U16' else 4294967295)
    if arg_type in {'IPADDR', 'DOTTEDIP'}:
        try:
            parsed = ipaddress.ip_address(value)
        except ValueError:
            return False
        return arg_type == 'IPADDR' or parsed.version == 4
    if arg_type == 'IPMASK':
        if re.fullmatch('\\d+', value):
            return 0 <= int(value) <= 128
        try:
            ipaddress.IPv4Network(f'0.0.0.0/{value}')
        except ValueError:
            return False
        return True
    return False

def _value_domain_error(value: str, arg: dict, index: int) -> dict | None:
    domain = arg.get('value_domain')
    if not isinstance(domain, dict):
        return None
    folded = value.casefold()
    for claim in domain.get('default') or []:
        if folded == str(claim.get('value') or '').casefold():
            return None
    all_enum_claims = [claim for claim in domain.get('enum') or [] if isinstance(claim, dict)]
    enum_claims = [claim for claim in all_enum_claims if str(claim.get('source')) in _CLOSED_SET_ENUM_SOURCES]
    range_claims = [claim for claim in domain.get('range') or [] if isinstance(claim, dict)]
    if not enum_claims and (not range_claims):
        return None
    all_members = {str(item).casefold() for claim in all_enum_claims for item in claim.get('values') or []}
    if folded in all_members:
        return None
    union_separators = sorted({str(claim.get('separator') or '') for claim in domain.get('union') or [] if isinstance(claim, dict) and str(claim.get('separator') or '')})
    for separator in union_separators:
        parts = folded.split(separator)
        if len(parts) >= 2 and all((part and part in all_members for part in parts)):
            return None
    number: int | None
    try:
        number = int(value)
    except ValueError:
        number = None
    if range_claims and number is None:
        if not enum_claims:
            return None
    for claim in range_claims:
        if number is not None and int(claim['min']) <= number <= int(claim['max']):
            return None
    if enum_claims:
        error = {'code': 'enum_mismatch', 'argument_index': index, 'allowed_enums': sorted({str(item) for claim in all_enum_claims for item in claim.get('values') or []}), 'value_domain_sources': sorted({str(claim.get('source')) for claim in all_enum_claims})}
        if union_separators:
            error['union_separators'] = union_separators
        return error
    return {'code': 'range_mismatch', 'argument_index': index, 'allowed_ranges': [{'min': int(claim['min']), 'max': int(claim['max'])} for claim in range_claims], 'value_domain_sources': sorted({str(claim.get('source')) for claim in range_claims})}

def _argument_variants(entry: dict) -> list[list[dict]]:
    variants: list[list[dict]] = []
    primary = entry.get('args')
    if isinstance(primary, list):
        variants.append(primary)
    for candidate in entry.get('arg_variants') or []:
        if isinstance(candidate, list) and candidate not in variants:
            variants.append(candidate)
    return variants

def _parameter_contract_error(rem: list[str], entry: dict) -> dict | None:
    variants = _argument_variants(entry)
    if not variants:
        pmax = int(entry.get('pmax') or 0)
        if len(rem) > pmax:
            return {'code': 'arity_too_many', 'actual_count': len(rem), 'pmax': pmax}
        return None
    failures: list[dict] = []
    accepted = False
    for args in variants:
        required = sum((not bool(arg.get('optional')) for arg in args))
        maximum = len(args)
        if len(rem) < required:
            failures.append({'code': 'arity_too_few', 'actual_count': len(rem), 'required_min': required, 'pmax': maximum})
            continue
        if len(rem) > maximum:
            failures.append({'code': 'arity_too_many', 'actual_count': len(rem), 'required_min': required, 'pmax': maximum})
            continue
        mismatch = None
        for index, (value, arg) in enumerate(zip(rem, args), start=1):
            arg_type = str(arg.get('type') or '')
            if arg_type == _REDACTED_ARGUMENT_TYPE and arg.get('executable') is False:
                mismatch = {'code': 'sensitive_parameter_unexecutable', 'argument_index': index}
                break
            if not _value_matches_type(value, arg_type):
                mismatch = {'code': 'type_mismatch', 'argument_index': index, 'expected_type': arg_type}
                break
            domain_error = _value_domain_error(value, arg, index)
            if domain_error is not None:
                mismatch = domain_error
                break
        if mismatch is None:
            accepted = True
        else:
            failures.append(mismatch)
    sensitive = next((item for item in failures if item['code'] == 'sensitive_parameter_unexecutable'), None)
    if sensitive is not None:
        return sensitive
    if accepted:
        return None
    for code in ('type_mismatch', 'enum_mismatch', 'range_mismatch'):
        preferred = next((item for item in failures if item['code'] == code), None)
        if preferred is not None:
            return preferred
    return failures[0]

def _try_match(tokens: list[str], heads: dict) -> tuple[str, dict] | None:
    candidate = _head_candidate(tokens, heads)
    if candidate is None:
        return None
    head, entry, rem = candidate
    if 'manual_pmax' in entry and 'vendor_pmax' in entry:
        manual_pmax = int(entry.get('manual_pmax') or 0)
        vendor_pmax = int(entry.get('vendor_pmax') or 0)
        if min(manual_pmax, vendor_pmax) < len(rem) <= max(manual_pmax, vendor_pmax):
            return (head, entry)
        return None
    return None if _parameter_contract_error(rem, entry) else (head, entry)

def resolve_vendor_command(cmd: str, version: str='', device_build: str='') -> dict:
    inv = load_vendor_stdlib(version, device_build)
    if inv is None:
        return {'decided': False, 'hit': False, 'head': '', 'src': '', 'version': '', 'device_build': '', 'origin': ''}
    heads = inv['heads']
    tokens = _norm_tokens(cmd)
    if not tokens or not re.match('^[a-z\\[]', tokens[0]):
        return {'decided': False, 'hit': False, 'head': '', 'src': '', 'version': inv.get('version', ''), 'device_build': inv.get('device_os_build', ''), 'origin': ''}
    candidate = _head_candidate(tokens, heads)
    if candidate is None:
        return {'decided': True, 'hit': False, 'head': '', 'src': '', 'version': inv.get('version', ''), 'device_build': inv.get('device_os_build', ''), 'origin': '', 'reason_code': XML_COMMAND_NOT_FOUND}
    head, entry, rem = candidate
    parameter_error = _parameter_contract_error(rem, entry)
    if parameter_error is not None:
        return {'decided': True, 'hit': False, 'head': head, 'src': str(entry.get('src', '')), 'version': inv.get('version', ''), 'device_build': inv.get('device_os_build', ''), 'origin': str(entry.get('origin') or ''), 'reason_code': 'parameter_contract_violation', 'parameter_error': parameter_error}
    return {'decided': True, 'hit': True, 'head': head, 'src': str(entry.get('src', '')), 'version': inv.get('version', ''), 'device_build': inv.get('device_os_build', ''), 'origin': str(entry.get('origin') or '')}

def _recorded_headers(inv: object) -> dict | None:
    if not isinstance(inv, dict):
        return None
    headers = inv.get('headers')
    return headers if isinstance(headers, dict) else None

def rank_vendor_command_completions(cmd: str, version: str='', device_build: str='') -> list[dict]:
    headers = _recorded_headers(load_vendor_stdlib(version, device_build))
    if headers is None:
        return []
    tokens = _norm_tokens(cmd)
    if not tokens:
        return []
    scored: list[tuple[tuple[int, int, int, str], dict]] = []
    for head in headers:
        ht = head.split(' ')
        n = 0
        while n < len(ht) and n < len(tokens) and (ht[n] == tokens[n]):
            n += 1
        continues = n < len(tokens) and n < len(ht) and ht[n].startswith(tokens[n])
        if not n and (not continues):
            continue
        scored.append(((-n, 0 if continues else 1, len(ht), head), {'head': head, 'shared_tokens': n, 'prefix_continuation': continues}))
    scored.sort(key=lambda row: row[0])
    return [payload for _, payload in scored]

def complete_vendor_command(cmd: str, k: int=3, version: str='', device_build: str='') -> list[str]:
    ranked = rank_vendor_command_completions(cmd, version, device_build)
    return [candidate['head'] for candidate in ranked[:k]]
_PERMUTATION_MIN_TOKENS = 3
_PERMUTATION_EXTRA_TOKENS = 1
_PERMUTATION_SHOWN_K = 8

def recorded_heads_with_token_permutation(cmd: str, version: str='', device_build: str='', *, extra_tokens: int=_PERMUTATION_EXTRA_TOKENS, limit: int=_PERMUTATION_SHOWN_K) -> list[str]:
    headers = _recorded_headers(load_vendor_stdlib(version, device_build))
    if headers is None:
        return []
    tokens = _norm_tokens(cmd)
    if len(tokens) < _PERMUTATION_MIN_TOKENS:
        return []
    query = Counter(tokens)
    scored: list[tuple[tuple[int, int, str], str]] = []
    for head in headers:
        ht = str(head).split(' ')
        if ht == tokens:
            continue
        extra = len(ht) - len(tokens)
        if extra < 0 or extra > extra_tokens:
            continue
        counts = Counter(ht)
        if any((counts[tok] < query[tok] for tok in query)):
            continue
        scored.append(((extra, len(ht), str(head)), str(head)))
    scored.sort(key=lambda row: row[0])
    return [head for _, head in scored[:limit]]
_NEXT_TOKEN_SHOWN_K = 32

def recorded_next_tokens_after_shared_prefix(cmd: str, version: str='', device_build: str='', *, limit: int=_NEXT_TOKEN_SHOWN_K) -> dict | None:
    headers = _recorded_headers(load_vendor_stdlib(version, device_build))
    if headers is None:
        return None
    tokens = _norm_tokens(cmd)
    if not tokens:
        return None
    max_n = 0
    nexts: dict[str, None] = {}
    for head in headers:
        ht = str(head).split(' ')
        n = 0
        while n < len(ht) and n < len(tokens) and (ht[n] == tokens[n]):
            n += 1
        if n > max_n:
            max_n = n
            nexts = {}
        if n == max_n and n > 0 and (len(ht) > n):
            nexts.setdefault(ht[n], None)
    if max_n == 0 or not nexts:
        return None
    ordered = sorted(nexts)
    return {'prefix': ' '.join(tokens[:max_n]), 'shared_tokens': max_n, 'position': max_n + 1, 'tokens': ordered[:max(1, int(limit))], 'total': len(ordered)}
_T2_ANSWER_RE = re.compile('^(?:yes|no|y|n)$', re.IGNORECASE)
_T2_PROMPT_RE = re.compile('^prompt\\s*=\\s*\\S+$', re.IGNORECASE)
_T3_EXECUTE_PREFIX_RE = re.compile('^execute\\s*[:：]{1,2}', re.IGNORECASE)

def classify_non_command(line: str) -> str | None:
    s = (line or '').strip()
    if not s:
        return None
    if _T2_ANSWER_RE.match(s) or _T2_PROMPT_RE.match(s):
        return 'confirmation_answer'
    if ord(s[0]) > 127:
        return 'chinese_action_description'
    if _T3_EXECUTE_PREFIX_RE.match(s):
        return 'chinese_action_description'
    return None
