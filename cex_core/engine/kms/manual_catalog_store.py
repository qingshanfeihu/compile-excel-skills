# 生成：tools/extract_engine.py ← InfoTest main/kms/manual_catalog_store.py（sha256 96444bf13421dc6a）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import re
import threading
from pathlib import Path
from cex_core.engine import knowledge_paths
CATALOG_SCHEMA = 'ist.manual-command-catalog'
CATALOG_STATUS_SCHEMA = 'ist.manual-catalog-status'
CATALOG_STATUSES = frozenset({'ok', 'catalog_missing', 'catalog_unreadable', 'schema_unknown', 'identity_uncoupled', 'md_missing'})
_MAX_CATALOG_BYTES = 16 * 1024 * 1024
_SHA256_RE = re.compile('^[0-9a-f]{64}$')

def manual_root() -> Path:
    return Path(knowledge_paths.KNOWLEDGE_MANUAL)

def md_path(version: str, family: str, *, root: Path | None=None) -> Path:
    return (root or manual_root()) / str(version) / f'{family}_cn.md'

def catalog_path(version: str, family: str, *, root: Path | None=None) -> Path:
    return (root or manual_root()) / str(version) / f'{family}_cn.catalog.json'

def _status(version: str, family: str, status: str, detail: str, *, catalog_sha256: str='', md_sha256: str='') -> dict:
    assert status in CATALOG_STATUSES, status
    return {'schema': CATALOG_STATUS_SCHEMA, 'version': str(version), 'family': str(family), 'status': status, 'detail': detail, 'catalog_sha256': catalog_sha256, 'md_sha256': md_sha256}

def _sealed_read(path: Path, *, max_bytes: int) -> bytes | None:
    from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
    try:
        raw = read_regular_nofollow(path, error_type=ValueError, invalid_message='manual catalog 路径无效', directory_message='manual catalog 目录不可安全读取', open_message='manual catalog 文件不可读', bounds_message='manual catalog 文件大小越界', changed_message='manual catalog 文件读取期间发生变化', max_bytes=max_bytes, min_bytes=1)
    except (ValueError, OSError):
        return None
    assert isinstance(raw, bytes)
    return raw

def _real_directory(path: Path) -> bool:
    import stat as _stat
    try:
        return _stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return True

def catalog_schema_valid(catalog: object) -> bool:
    from cex_core.engine.common.schema_identity import accepts_schema
    if not isinstance(catalog, dict) or not accepts_schema(catalog.get('schema'), CATALOG_SCHEMA):
        return False
    identity = catalog.get('identity')
    if not isinstance(identity, dict):
        return False
    adoc_map = identity.get('adoc_sha256')
    if not isinstance(adoc_map, dict) or not adoc_map or any((not isinstance(name, str) or not name or Path(name).name != name or (not isinstance(digest, str)) or (not _SHA256_RE.match(digest)) for name, digest in adoc_map.items())):
        return False
    md_digest = identity.get('md_sha256')
    if not isinstance(md_digest, str) or not _SHA256_RE.match(md_digest):
        return False
    for key in ('signatures', 'value_domains', 'worked_examples'):
        if not isinstance(catalog.get(key), list):
            return False
    return True
_CATALOG_STATUS_CACHE: dict[tuple[str, str, str], tuple[tuple, dict]] = {}
_COUPLED_CATALOG_CACHE: dict[tuple[str, str, str], tuple[tuple, dict | None, dict]] = {}
_IDENTITY_CACHE_MAX = 32
_COUPLED_CACHE_MAX = 8

def _path_identity(path: Path) -> tuple[int, ...]:
    try:
        info = path.lstat()
    except OSError:
        return ()
    return (int(info.st_mode), int(info.st_dev), int(info.st_ino), int(info.st_size), int(info.st_mtime_ns), int(info.st_ctime_ns))

def manual_identity(version: str, family: str, *, root: Path | None=None) -> tuple:
    base = root or manual_root()
    md = md_path(version, family, root=base)
    return (_path_identity(md.parent), _path_identity(md), _path_identity(catalog_path(version, family, root=base)))
_CACHE_LOCK = threading.Lock()

def remember_bounded(cache: dict, key: object, value: object, *, limit: int) -> None:
    """按插入序封顶写入；**全仓按身份记忆的淘汰动作只此一份**。

    加锁的理由是实的：`next(iter(cache))` 与 `pop` 是两条独立字节码，另一线程在
    其间插入或弹出会抛 `RuntimeError: dictionary changed size during iteration`，
    两线程算出同一个待淘汰键则第二个 `pop` 抛 `KeyError`。而这三份记忆都被 fork
    线程触达——`submit_mechanical_case` 的交卷复核走 `normalize_contract` →
    `load_author_rules`，`lang_query` 走 `manual_locator` → `load_coupled_catalog`，
    两条都在 author 的线程池里并行。抛出去的后果不是「多算一次」：异常落进
    `_rule_reusable` 的 `except Exception: return False`，会把一条本可复用的规则
    记成不可复用并黏住，接着 `persist_engine_adjudications` 用自己新算的判定复核
    对不上，整批死在 `reusable criterion rule was not returned as active`。
    本仓既有做法就是加锁（`manual_locator._CACHE_LOCK` / `catalog_join._CACHE_LOCK`），
    不另开第三种写法。
    """
    with _CACHE_LOCK:
        if key not in cache and len(cache) >= limit:
            cache.pop(next(iter(cache)), None)
        cache[key] = value

def clear_bounded(*caches: dict) -> None:
    with _CACHE_LOCK:
        for cache in caches:
            cache.clear()

def clear_catalog_cache() -> None:
    clear_bounded(_CATALOG_STATUS_CACHE, _COUPLED_CATALOG_CACHE, _CLAIMS_CACHE)

def load_catalog_status(version: str, family: str, *, root: Path | None=None) -> dict:
    base = root or manual_root()
    key = (str(base), str(version), str(family))
    identity = manual_identity(version, family, root=base)
    cached = _CATALOG_STATUS_CACHE.get(key)
    if cached is not None and cached[0] == identity:
        return dict(cached[1])
    verdict = _verify_catalog_status(version, family, base)
    if manual_identity(version, family, root=base) == identity:
        remember_bounded(_CATALOG_STATUS_CACHE, key, (identity, verdict), limit=_IDENTITY_CACHE_MAX)
    return dict(verdict)

def _verify_catalog_status(version: str, family: str, base: Path) -> dict:
    md = md_path(version, family, root=base)
    cat = catalog_path(version, family, root=base)
    if not _real_directory(md.parent):
        return _status(version, family, 'catalog_unreadable', f'manual 版本目录不是真实目录（拒绝链接根）: {md.parent}')
    md_raw = _sealed_read(md, max_bytes=_MAX_CATALOG_BYTES)
    if md_raw is None:
        return _status(version, family, 'md_missing', f'manual md 缺席或不可读: {md}')
    md_sha = hashlib.sha256(md_raw).hexdigest()
    if not cat.is_file():
        return _status(version, family, 'catalog_missing', f'catalog 缺失但 md 在（裁决：拒绝生效，保留旧代际并披露）: {cat}', md_sha256=md_sha)
    raw = _sealed_read(cat, max_bytes=_MAX_CATALOG_BYTES)
    if raw is None:
        return _status(version, family, 'catalog_unreadable', f'catalog 不可安全读取（链接/越界/读间变化）: {cat}', md_sha256=md_sha)
    catalog_sha = hashlib.sha256(raw).hexdigest()
    try:
        catalog = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return _status(version, family, 'catalog_unreadable', f'catalog 不是合法 JSON: {cat}', catalog_sha256=catalog_sha, md_sha256=md_sha)
    if not catalog_schema_valid(catalog):
        return _status(version, family, 'schema_unknown', f'catalog 不是合法 {CATALOG_SCHEMA} 形态: {cat}', catalog_sha256=catalog_sha, md_sha256=md_sha)
    if str(catalog['identity']['md_sha256']).lower() != md_sha:
        return _status(version, family, 'identity_uncoupled', 'catalog 内嵌 md sha256 与同目录 md 字节不符（非同池出生，拒绝生效）', catalog_sha256=catalog_sha, md_sha256=md_sha)
    return _status(version, family, 'ok', '', catalog_sha256=catalog_sha, md_sha256=md_sha)

def load_coupled_catalog(version: str, family: str, *, root: Path | None=None) -> tuple[dict | None, dict]:
    base = root or manual_root()
    key = (str(base), str(version), str(family))
    identity = manual_identity(version, family, root=base)
    cached = _COUPLED_CATALOG_CACHE.get(key)
    if cached is not None and cached[0] == identity:
        return (cached[1], dict(cached[2]))
    catalog, verdict = _verify_coupled_catalog(version, family, base)
    if manual_identity(version, family, root=base) == identity:
        remember_bounded(_COUPLED_CATALOG_CACHE, key, (identity, catalog, verdict), limit=_COUPLED_CACHE_MAX)
    return (catalog, dict(verdict))

def _verify_coupled_catalog(version: str, family: str, base: Path) -> tuple[dict | None, dict]:
    verdict = load_catalog_status(version, family, root=base)
    if verdict['status'] != 'ok':
        return (None, verdict)
    raw = _sealed_read(catalog_path(version, family, root=base), max_bytes=_MAX_CATALOG_BYTES)
    try:
        catalog = json.loads(raw.decode('utf-8')) if raw is not None else None
    except (UnicodeDecodeError, ValueError):
        catalog = None
    if catalog is None:
        return (None, _status(version, family, 'catalog_unreadable', 'catalog 读取竞态失败'))
    return (catalog, verdict)
_COMPOUND_KEYWORD_RE_CACHE: dict[str, object] = {}

def catalog_enum_is_closed_set(param: str, members: list[str], desc: str) -> bool:
    import re as _re
    if '|' in str(param or ''):
        return False
    text = str(desc or '')
    if '常见' in text:
        return False
    for member in members:
        token = str(member or '').strip()
        if not token:
            continue
        pattern = _COMPOUND_KEYWORD_RE_CACHE.get(token)
        if pattern is None:
            pattern = _re.compile(f'{_re.escape(token)}\\s*=')
            _COMPOUND_KEYWORD_RE_CACHE[token] = pattern
        if pattern.search(text):
            return False
    return True

def catalog_row_describes_one_parameter(param: str) -> bool:
    return '|' not in str(param or '')

def catalog_alternate_row_enum_is_closed_set(param: str, members: list[str], desc: str) -> bool:
    import re as _re
    raw = str(param or '')
    if '|' not in raw:
        return False
    branches = [part.strip() for part in raw.split('|') if part.strip()]
    cleaned = [str(item).strip() for item in members if str(item).strip()]
    if len(branches) < 2 or len(cleaned) < 2:
        return False
    if {b.casefold() for b in branches} != {m.casefold() for m in cleaned}:
        return False
    text = str(desc or '')
    if '取值必须为' not in text:
        return False
    if any(('_' in member for member in cleaned)):
        return False
    if '常见' in text:
        return False
    for member in cleaned:
        if _re.search(f'{_re.escape(member)}\\s*[：:]\\s*(?:该参数|表示)', text):
            return False
        pattern = _COMPOUND_KEYWORD_RE_CACHE.get(member)
        if pattern is None:
            pattern = _re.compile(f'{_re.escape(member)}\\s*=')
            _COMPOUND_KEYWORD_RE_CACHE[member] = pattern
        if pattern.search(text):
            return False
    return True
_CLAIMS_CACHE: dict[tuple[str, str, str], dict[str, dict]] = {}
_CLAIMS_CACHE_MAX = 8

def catalog_manual_claims(catalog: dict) -> dict[str, dict]:
    claims: dict[str, dict] = {}
    for signature in catalog.get('signatures') or []:
        tokens = signature.get('head_tokens') or []
        head = ' '.join((str(token) for token in tokens if str(token))).strip()
        if not head:
            continue
        params = signature.get('params') or []
        entry = {'src': str(signature.get('src') or ''), 'pmax': len(params), 'args': [], 'results': [], 'origin': 'manual_declaration'}
        claims.setdefault(head, entry)
        for variant in signature.get('head_variants') or []:
            variant_head = ' '.join((str(token) for token in variant or [] if str(token))).strip()
            if variant_head:
                claims.setdefault(variant_head, dict(entry))
    return claims

def manual_claims_view(version: str, family: str, *, root: Path | None=None) -> tuple[dict[str, dict], dict]:
    catalog, verdict = load_coupled_catalog(version, family, root=root)
    if catalog is None:
        return ({}, verdict)
    key = (verdict['version'], verdict['family'], verdict['catalog_sha256'])
    view = _CLAIMS_CACHE.get(key)
    if view is None:
        view = catalog_manual_claims(catalog)
        remember_bounded(_CLAIMS_CACHE, key, view, limit=_CLAIMS_CACHE_MAX)
    return (view, verdict)
PROJECTION_FRESHNESS_SCHEMA = 'ist.projection-catalog-freshness'
PROJECTION_FRESHNESS_STATUSES = frozenset({'current', 'stale', 'identity_absent', 'catalog_unavailable'})

def projection_catalog_freshness(projection: object, *, root: Path | None=None) -> dict:

    def _verdict(status: str, version: str, families: dict, detail: str) -> dict:
        assert status in PROJECTION_FRESHNESS_STATUSES, status
        return {'schema': PROJECTION_FRESHNESS_SCHEMA, 'status': status, 'version': str(version), 'families': families, 'detail': detail}
    if not isinstance(projection, dict):
        return _verdict('identity_absent', '', {}, '投影不是对象')
    stats = projection.get('stats')
    block = (stats or {}).get('value_domain') if isinstance(stats, dict) else None
    catalog_block = (block or {}).get('manual_catalog') if isinstance(block, dict) else None
    if not isinstance(catalog_block, dict):
        return _verdict('identity_absent', '', {}, '投影未记录 manual_catalog 段')
    version = str(catalog_block.get('version') or '')
    recorded = catalog_block.get('identity')
    if not isinstance(recorded, dict) or not recorded:
        return _verdict('identity_absent', version, {}, '投影未记录分族 catalog sha256（本判据落地前生成的投影）')
    families: dict[str, str] = {}
    stale: list[str] = []
    unavailable: list[str] = []
    for family, pinned in sorted(recorded.items()):
        if not isinstance(pinned, dict):
            families[str(family)] = 'identity_absent'
            stale.append(str(family))
            continue
        verdict = load_catalog_status(version, str(family), root=root)
        if verdict.get('status') != 'ok':
            families[str(family)] = str(verdict.get('status') or 'unknown')
            unavailable.append(str(family))
            continue
        same = str(pinned.get('catalog_sha256') or '') == str(verdict.get('catalog_sha256') or '')
        families[str(family)] = 'current' if same else 'stale'
        if not same:
            stale.append(str(family))
    if stale:
        return _verdict('stale', version, families, '投影按旧 catalog 生成，分族不符: ' + ', '.join(sorted(stale)))
    if unavailable:
        return _verdict('catalog_unavailable', version, families, '本地 catalog 不生效，无从比对: ' + ', '.join(sorted(unavailable)))
    return _verdict('current', version, families, '')
