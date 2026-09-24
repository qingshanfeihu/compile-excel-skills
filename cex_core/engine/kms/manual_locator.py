# 生成：tools/extract_engine.py ← InfoTest main/kms/manual_locator.py（sha256 e5405f327e813db9）。不在这里手改。
from __future__ import annotations
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from cex_core.engine.kms import manual_catalog_store
_ADOC_SRC_RE = re.compile('^(?:manual:)?(?P<src>(?:Chapter|Appendix)[^/\\s:]+\\.adoc:\\d+)\\s*$', re.IGNORECASE)
_CACHE_CAP = 8
_CACHE: dict[tuple[str, str, str], dict[str, object]] = {}
_CACHE_ORDER: list[tuple[str, str, str]] = []
_CACHE_LOCK = threading.Lock()

@dataclass(frozen=True)
class ManualLocatorResolution:
    ok: bool
    display: str
    adoc_src: str = ''
    version: str = ''
    family: str = ''
    md_line: int = 0
    reason: str = ''

def parse_adoc_style_src(locator: str) -> str | None:
    text = str(locator or '').strip()
    if not text:
        return None
    match = _ADOC_SRC_RE.match(text)
    if not match:
        return None
    return match.group('src')

def _line_at(md_text: str, pos: int) -> int:
    return md_text.count('\n', 0, pos) + 1

def _build_forward_index(catalog: dict, md_text: str) -> dict[str, object]:
    by_src: dict[str, int] = {}
    by_src_verbatim: dict[tuple[str, str], int] = {}
    by_head: dict[str, int] = {}
    cursor = 0
    for sig in catalog.get('signatures') or []:
        if not isinstance(sig, dict):
            continue
        verbatim = str(sig.get('signature_verbatim') or '')
        src = str(sig.get('src') or '').strip()
        head = ' '.join((str(t) for t in sig.get('head_tokens') or [])).strip()
        if not verbatim:
            continue
        pos = md_text.find(verbatim, cursor)
        if pos < 0:
            continue
        line = _line_at(md_text, pos)
        cursor = pos + len(verbatim)
        if src:
            by_src_verbatim.setdefault((src, verbatim), line)
            by_src.setdefault(src, line)
        if head and head not in by_head:
            by_head[head] = line
    head_by_vd_src: dict[str, str] = {}
    for vd in catalog.get('value_domains') or []:
        if not isinstance(vd, dict):
            continue
        src = str(vd.get('src') or '').strip()
        head = str(vd.get('head') or '').strip()
        if src and head and (src not in by_src) and (src not in head_by_vd_src):
            head_by_vd_src[src] = head
    return {'by_src': by_src, 'by_src_verbatim': by_src_verbatim, 'by_head': by_head, 'head_by_vd_src': head_by_vd_src}

def _cached_index(version: str, family: str, *, root: Path | None) -> dict | None:
    try:
        catalog, verdict = manual_catalog_store.load_coupled_catalog(version, family, root=root)
    except Exception:
        return None
    if catalog is None or verdict.get('status') != 'ok':
        return None
    sha = str(verdict.get('catalog_sha256') or '')
    key = (str(version), str(family), sha)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached
    md = manual_catalog_store.md_path(version, family, root=root or manual_catalog_store.manual_root())
    try:
        md_text = md.read_text(encoding='utf-8')
    except OSError:
        return None
    index = _build_forward_index(catalog, md_text)
    index['identity'] = {'version': str(version), 'family': str(family), 'sha256': sha}
    with _CACHE_LOCK:
        if key not in _CACHE:
            _CACHE[key] = index
            _CACHE_ORDER.append(key)
            while len(_CACHE_ORDER) > _CACHE_CAP:
                _CACHE.pop(_CACHE_ORDER.pop(0), None)
    return index

def _lookup_line(index: dict, adoc_src: str, *, verbatim: str | None) -> tuple[int, str] | None:
    by_src: dict = index['by_src']
    by_src_verbatim: dict = index['by_src_verbatim']
    by_head: dict = index['by_head']
    head_by_vd_src: dict = index['head_by_vd_src']
    if verbatim:
        key = (adoc_src, str(verbatim))
        if key in by_src_verbatim:
            return (int(by_src_verbatim[key]), 'signature_verbatim')
    if adoc_src in by_src:
        return (int(by_src[adoc_src]), 'signature_src')
    head = head_by_vd_src.get(adoc_src)
    if head and head in by_head:
        return (int(by_head[head]), 'same_head_signature')
    return None

def _fail(adoc_src: str, reason: str, *, locator: str='') -> ManualLocatorResolution:
    shown = adoc_src or str(locator or '').strip() or '(empty)'
    display = f'{shown} (unresolved — adoc source is not on disk locally; could not map to a manual md line: {reason})'
    return ManualLocatorResolution(ok=False, display=display, adoc_src=adoc_src, reason=reason)

def resolve_manual_locator(locator: str, *, version: str, family: str | None=None, verbatim: str | None=None, root: Path | None=None) -> ManualLocatorResolution:
    raw = str(locator or '').strip()
    adoc_src = parse_adoc_style_src(raw)
    if adoc_src is None:
        if not raw:
            return _fail('', 'empty locator')
        return ManualLocatorResolution(ok=True, display=raw, reason='passthrough')
    ver = str(version or '').strip()
    if not ver:
        return _fail(adoc_src, 'manual version unknown')
    families = [str(family)] if family else ['cli', 'app']
    last_reason = 'coupled catalog not in effect'
    for fam in families:
        fam = str(fam or '').strip()
        if fam not in ('cli', 'app'):
            continue
        index = _cached_index(ver, fam, root=root)
        if index is None:
            last_reason = f'coupled catalog not in effect for {ver}/{fam}'
            continue
        hit = _lookup_line(index, adoc_src, verbatim=verbatim)
        if hit is None:
            last_reason = f'src {adoc_src!r} not mapped in {ver}/{fam} catalog cursor'
            continue
        line, _via = hit
        display = f'manual:{ver}/{fam}_cn.md:{line}'
        return ManualLocatorResolution(ok=True, display=display, adoc_src=adoc_src, version=ver, family=fam, md_line=line, reason=_via)
    return _fail(adoc_src, last_reason)

def display_manual_locator(locator: str, *, version: str, family: str | None=None, verbatim: str | None=None, root: Path | None=None) -> str:
    return resolve_manual_locator(locator, version=version, family=family, verbatim=verbatim, root=root).display

def clear_manual_locator_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
        _CACHE_ORDER.clear()
