# 生成：tools/extract_engine.py ← InfoTest main/kms/manual_chapter_locator.py（sha256 5bdd1b2a586d7c5d）。不在这里手改。
"""手册锚 → 所在小节的内容指纹（判据规则复用钉）。

判据引擎规则台账按「锚所在小节的内容有没有变」失效。这个粒度是量出来的，不是
拍的：整章（一级标题）在 cli 里中位 22,471 字符、最大 41 万，改这章任何一句都会
把引它的规则全废；`##` 子节中位 3,770 字符，细约 6 倍，且两本手册里都密集可靠
（`###` 在 cli 只有 76 个、比 `##` 还少，深浅不均，不能当统一层）。

两条纪律，都是实证逼出来的：

**定位按内容，不按冻结偏移。** 锚里记的 ``source_span`` 是绝对字符偏移，手册前面
插一句话，后面全部平移。实证：台账里那条 cli 锚记的 1135317 切出来是完全无关的
文字，而它的引文原封不动、唯一地待在 1135756——整体后移了 439 字符。按偏移定位
会把锚定到**错误的小节**上，然后钉错小节的哈希，不响还给出错误的「没变」。所以
先试冻结偏移（快路径），不中就拿引文全文搜，**唯一命中**才认，0 处或多处即判失效。

**哈希含所属章标题行。** 只哈希 `##` 子节文本的话，上一级 `#` 章标题改了发现不了
（子节文本里没有它）。所以指纹材料 = 所属 `#` 标题行 + 本小节全文：章标题改了能
发现，而该章别处改动不会误伤。

不做的事：不按 adoc 文件名猜「哪一章对应哪个标题」。那条路不成立——cli 的主文档壳
`cli_cn.adoc` 会产一个标题（`# {product}命令行手册{show_version}`）而 app 的不产，
按位置序对齐会整族错位一格；实测 cli 因此 30 对 31 直接失配。锚身份（anchor_id）
也不在本模块算，由调用方随锚带进来——同一段哈希逻辑存两份就是又一处同值双生分叉。
"""
from __future__ import annotations
import bisect
import hashlib
import re
from pathlib import Path
from typing import Mapping, Sequence
from cex_core.engine.kms import manual_catalog_store
_MANUAL_PATH_RE = re.compile('(?:^|/)manual/(?P<version>[^/]+)/(?P<family>cli|app)_cn\\.md$')

class ManualChapterLocatorError(ValueError):
    pass

def _heading_starts(md_text: str, prefix: str) -> list[int]:
    starts: list[int] = []
    offset = 0
    for line in md_text.splitlines(keepends=True):
        if line.startswith(prefix):
            starts.append(offset)
        offset += len(line)
    return starts

def _line_at(md_text: str, start: int) -> str:
    end = md_text.find('\n', start)
    return md_text[start:end if end >= 0 else len(md_text)].strip()

def section_boundaries(md_text: str) -> tuple[list[int], list[int]]:
    chapters = _heading_starts(md_text, '# ')
    subsections = _heading_starts(md_text, '## ')
    return (sorted(set(chapters) | set(subsections)), chapters)

def locate_quote(md_text: str, anchor: Mapping[str, object]) -> int:
    quote = str(anchor.get('quote') or '')
    if not quote:
        raise ManualChapterLocatorError('anchor has no quote')
    span = anchor.get('source_span')
    if isinstance(span, Mapping):
        try:
            start = int(span.get('start') or 0)
            end = int(span.get('end') or 0)
        except (TypeError, ValueError):
            start = end = -1
        if 0 <= start < end <= len(md_text) and md_text[start:end] == quote:
            return start
    hits = md_text.count(quote)
    if hits == 1:
        return md_text.find(quote)
    raise ManualChapterLocatorError(f'anchor quote is not uniquely locatable in the current manual (matches={hits})')

def section_pin(md_text: str, pos: int) -> dict[str, str]:
    boundaries, chapters = section_boundaries(md_text)
    if not boundaries:
        raise ManualChapterLocatorError('manual has no level-1/2 headings')
    index = bisect.bisect_right(boundaries, pos) - 1
    if index < 0:
        sec_start, sec_end, chapter_line = (0, boundaries[0], '')
    else:
        sec_start = boundaries[index]
        sec_end = boundaries[index + 1] if index + 1 < len(boundaries) else len(md_text)
        chapter_index = bisect.bisect_right(chapters, pos) - 1
        chapter_line = _line_at(md_text, chapters[chapter_index]) if chapter_index >= 0 else ''
    material = chapter_line + '\n' + md_text[sec_start:sec_end]
    return {'chapter': chapter_line, 'section': _line_at(md_text, sec_start) if index >= 0 else '', 'section_sha256': hashlib.sha256(material.encode('utf-8')).hexdigest()}

def _family_version_from_source_path(source_path: str) -> tuple[str, str]:
    normalized = str(source_path or '').replace('\\', '/')
    match = _MANUAL_PATH_RE.search(normalized)
    if not match:
        return ('', '')
    return (str(match.group('version') or ''), str(match.group('family') or ''))
_MANUAL_TEXT_CACHE: dict[tuple[str, str, str], tuple[tuple, str]] = {}
_PINS_CACHE: dict[tuple, tuple[dict[str, dict[str, str]], list[dict[str, str]]]] = {}
_MANUAL_TEXT_CACHE_MAX = 8
_PINS_CACHE_MAX = 256

def clear_locator_cache() -> None:
    manual_catalog_store.clear_bounded(_MANUAL_TEXT_CACHE, _PINS_CACHE)

def _load_manual_text(version: str, family: str, root: Path | None) -> str:
    base = root or manual_catalog_store.manual_root()
    key = (str(base), str(version), str(family))
    identity = manual_catalog_store.manual_identity(version, family, root=base)
    cached = _MANUAL_TEXT_CACHE.get(key)
    if cached is not None and cached[0] == identity:
        return cached[1]
    catalog, verdict = manual_catalog_store.load_coupled_catalog(version, family, root=root)
    if catalog is None or verdict.get('status') != 'ok':
        raise ManualChapterLocatorError(f"coupled catalog not in effect for {version}/{family}: {verdict.get('status')}")
    md = manual_catalog_store.md_path(version, family, root=root)
    try:
        text = md.read_text(encoding='utf-8')
    except OSError as exc:
        raise ManualChapterLocatorError(f'manual md unreadable: {md}') from exc
    if manual_catalog_store.manual_identity(version, family, root=base) == identity:
        manual_catalog_store.remember_bounded(_MANUAL_TEXT_CACHE, key, (identity, text), limit=_MANUAL_TEXT_CACHE_MAX)
    return text

def _resolve_target(anchor: Mapping[str, object], manual_version: str) -> tuple[str, str]:
    source_path = str(anchor.get('source_path') or '')
    path_version, path_family = _family_version_from_source_path(source_path)
    version = str(manual_version or path_version or '').strip()
    family = str(path_family or '').strip()
    if not version or family not in ('cli', 'app'):
        raise ManualChapterLocatorError(f'cannot resolve manual version/family for anchor path {source_path!r}')
    return (version, family)

def _anchor_key(anchor: Mapping[str, object]) -> str:
    anchor_id = str(anchor.get('anchor_id') or '')
    if not anchor_id:
        raise ManualChapterLocatorError('anchor has no anchor_id')
    return anchor_id

def anchor_chapter_pins(anchors: Sequence[Mapping[str, object]], *, manual_version: str, root: Path | None=None) -> dict[str, dict[str, str]]:
    pins, failures = anchor_chapter_pins_partial(anchors, manual_version=manual_version, root=root)
    if failures:
        raise ManualChapterLocatorError('; '.join((f"{row['anchor_id']}: {row['reason']}" for row in failures[:3])))
    return pins

def anchor_chapter_pins_partial(anchors: Sequence[Mapping[str, object]], *, manual_version: str, root: Path | None=None) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    anchors = list(anchors)
    cache_key = _pins_cache_key(anchors, manual_version, root)
    cached = _PINS_CACHE.get(cache_key)
    if cached is not None:
        pins_hit, failures_hit = cached
        return ({key: dict(value) for key, value in pins_hit.items()}, [dict(row) for row in failures_hit])
    texts: dict[tuple[str, str], str] = {}
    pins: dict[str, dict[str, str]] = {}
    failures: list[dict[str, str]] = []
    for anchor in anchors:
        if not isinstance(anchor, Mapping):
            continue
        try:
            anchor_id = _anchor_key(anchor)
        except ManualChapterLocatorError as exc:
            failures.append({'anchor_id': '(无 anchor_id)', 'reason': str(exc)})
            continue
        try:
            version, family = _resolve_target(anchor, manual_version)
            key = (version, family)
            if key not in texts:
                texts[key] = _load_manual_text(version, family, root)
            md_text = texts[key]
            pins[anchor_id] = section_pin(md_text, locate_quote(md_text, anchor))
        except ManualChapterLocatorError as exc:
            failures.append({'anchor_id': anchor_id, 'reason': str(exc)})
    manual_catalog_store.remember_bounded(_PINS_CACHE, cache_key, (pins, failures), limit=_PINS_CACHE_MAX)
    return ({key: dict(value) for key, value in pins.items()}, [dict(row) for row in failures])

def _pins_cache_key(anchors: Sequence[Mapping[str, object]], manual_version: str, root: Path | None) -> tuple:
    base = root or manual_catalog_store.manual_root()
    signature: list[tuple] = []
    targets: set[tuple[str, str]] = set()
    for anchor in anchors:
        if not isinstance(anchor, Mapping):
            signature.append(('not-a-mapping',))
            continue
        span = anchor.get('source_span')
        signature.append((str(anchor.get('anchor_id') or ''), str(anchor.get('source_path') or ''), str(anchor.get('source_sha256') or ''), str(span.get('start')) if isinstance(span, Mapping) else '', str(span.get('end')) if isinstance(span, Mapping) else '', hashlib.sha256(str(anchor.get('quote') or '').encode('utf-8')).hexdigest()))
        try:
            targets.add(_resolve_target(anchor, manual_version))
        except ManualChapterLocatorError:
            continue
    identities = tuple(((version, family, manual_catalog_store.manual_identity(version, family, root=base)) for version, family in sorted(targets)))
    return (str(base), str(manual_version or ''), tuple(signature), identities)
__all__ = ['ManualChapterLocatorError', 'anchor_chapter_pins', 'anchor_chapter_pins_partial', 'clear_locator_cache', 'locate_quote', 'section_boundaries', 'section_pin']
