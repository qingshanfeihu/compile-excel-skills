# 生成：tools/extract_engine.py ← InfoTest main/kms/spec_index.py（sha256 4b4b4ecc171e5a1f）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from cex_core.engine.knowledge_paths import SpecGenerationUnavailable, is_spec_document, resolve_active_spec_generation
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, read_regular_nofollow, validate_json_budget
from cex_core.engine.common.schema_identity import accepts_schema
logger = logging.getLogger(__name__)
SCHEMA = 'ist.spec_index'
_BUG_NUM_RE = re.compile('(?<!\\d)(\\d{5,6})(?!\\d)')
_ASCII_TOKEN_RE = re.compile('[a-z0-9]{2,}')
_CJK_RE = re.compile('[一-鿿]')
_BODY_SCAN_LIMIT_BYTES = 512 * 1024
_SPEC_MAX_BYTES = 16 * 1024 * 1024
_INDEX_MAX_BYTES = 16 * 1024 * 1024
_KEYWORD_TOP = 24
_KEYWORD_MIN_TF = 3
_KEYWORD_DF_CAP = 0.2

def _read_bounded(path: Path, *, label: str, max_bytes: int) -> bytes:
    result = read_regular_nofollow(path, error_type=ValueError, invalid_message=f'{label} path is invalid', directory_message=f'{label} parent is unavailable', open_message=f'{label} is unavailable', bounds_message=f'{label} exceeds its sealed size boundary', changed_message=f'{label} changed while being read', max_bytes=max_bytes, min_bytes=1)
    assert isinstance(result, bytes)
    return result

def _top_terms(body: str) -> list[str]:
    tf: dict[str, int] = {}
    t = body.lower()
    for w in _ASCII_TOKEN_RE.findall(t):
        tf[w] = tf.get(w, 0) + 1
    cjk = ''.join(_CJK_RE.findall(body))
    for i in range(len(cjk) - 1):
        bg = cjk[i:i + 2]
        tf[bg] = tf.get(bg, 0) + 1
    ranked = sorted(((n, w) for w, n in tf.items() if n >= _KEYWORD_MIN_TF), key=lambda x: (-x[0], x[1]))
    return [w for _, w in ranked[:_KEYWORD_TOP * 3]]

def _tokens(text: str) -> set[str]:
    t = text.lower()
    out = set(_ASCII_TOKEN_RE.findall(t))
    cjk = ''.join(_CJK_RE.findall(t))
    out.update((cjk[i:i + 2] for i in range(len(cjk) - 1)))
    return out

def _first_title_line(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith('#'):
            return s.lstrip('#').strip()[:200]
        return s[:200]
    return ''

def _load_lastmod_map(state_tsv: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not state_tsv.is_file():
        return out
    for line in state_tsv.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) != 2:
            continue
        href, ms = parts
        try:
            out[(Path(href).stem + '.md').lower()] = int(ms)
        except ValueError:
            continue
    return out

def build_spec_index(spec_dir: Path, *, state_path: Path | None=None) -> dict[str, Any]:
    spec_dir = Path(spec_dir)
    lastmod = _load_lastmod_map(Path(state_path) if state_path is not None else spec_dir / '.sync_state.tsv')
    entries: dict[str, Any] = {}
    n_body_num = n_title = 0
    n_not_spec = 0
    lower_seen: dict[str, str] = {}
    collisions: list[str] = []
    per_doc_terms: dict[str, list[str]] = {}
    for p in sorted(spec_dir.glob('*.md')):
        if not is_spec_document(p.name):
            n_not_spec += 1
            continue
        raw = _read_bounded(p, label='spec document', max_bytes=_SPEC_MAX_BYTES)
        body = raw[:_BODY_SCAN_LIMIT_BYTES].decode('utf-8', errors='replace')
        title = _first_title_line(body)
        fname_nums = sorted(set(_BUG_NUM_RE.findall(p.name)))
        anchored: set[str] = set()
        plain: set[str] = set()
        for line in body.splitlines():
            nums = _BUG_NUM_RE.findall(line)
            if not nums:
                continue
            bucket = anchored if re.search('bug|#', line, re.IGNORECASE) else plain
            bucket.update(nums)
        plain -= anchored
        entry = {'title': title, 'bug_numbers_filename': fname_nums, 'bug_numbers_anchored': sorted(anchored), 'bug_numbers_body': sorted(plain), 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'lastmod_ms': lastmod.get(p.name.lower()) or int(p.stat().st_mtime * 1000)}
        per_doc_terms[p.name] = _top_terms(body)
        if p.name.lower() in lower_seen:
            collisions.append(p.name)
        lower_seen[p.name.lower()] = p.name
        entries[p.name] = entry
        n_body_num += bool(anchored or plain or fname_nums)
        n_title += bool(title)
    df: dict[str, int] = {}
    for terms in per_doc_terms.values():
        for t in set(terms):
            df[t] = df.get(t, 0) + 1
    cap = max(2, int(len(per_doc_terms) * _KEYWORD_DF_CAP))
    for name, terms in per_doc_terms.items():
        entries[name]['body_keywords'] = [t for t in terms if df.get(t, 0) <= cap][:_KEYWORD_TOP]
    return {'schema': SCHEMA, 'generated_from': str(spec_dir), 'policy': {'rule': 'addressing yields candidates with evidence, never silent authority binding; no hit must surface as no_governing_spec'}, 'coverage': {'total_files': len(entries), 'with_any_bug_number': n_body_num, 'with_title': n_title, 'skipped_not_spec_named': n_not_spec, 'case_insensitive_collisions': collisions}, 'entries': entries}

def write_index_atomic(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    atomic_write_bytes_nofollow(path, encoded, error_type=ValueError, invalid_message='spec index path is invalid', unavailable_message='spec index directory is unavailable')
_SEMANTIC_FLOOR = 3
_SEMANTIC_TOP = 3
_JEV_RERANK_TOP = 5

def _project_root() -> Path:
    return _cex_data_path('')

def _jev_rerank_semantic(scored: list[tuple[int, str, Any, list[str]]], query_title: str) -> tuple[list[tuple[int, str, Any, list[str]]], dict[str, float]]:
    """Jev 精排 top-K 语义候选（issue 内部工单）；helper 返回 None 时原序直通。

    正文头部经 resolve_indexed_spec 现读（sha256/size 验证），验证不过的候选
    不参与评分、保留原位。只动候选顺序——状态归属恒 candidates、证据字段的
    语义通道前缀不动。
    """
    from cex_core.engine.common import jev_spec_rerank
    if not jev_spec_rerank.enabled():
        return (scored, {})
    top = scored[:_JEV_RERANK_TOP]
    if len(top) < 2:
        return (scored, {})
    try:
        candidates = []
        for _score, name, entry, _overlap in top:
            head = None
            resolved = resolve_indexed_spec(_project_root(), name)
            if resolved is not None:
                head = jev_spec_rerank.spec_head_slice(resolved.content.decode('utf-8', errors='replace'))
            candidates.append({'filename': name, 'title': str(entry.get('title') or ''), 'head': head})
        outcome = jev_spec_rerank.rerank(query_title, candidates)
    except Exception as exc:
        logger.warning('spec_index: Jev 精排意外失败，退回原确定性排序: %s', type(exc).__name__)
        return (scored, {})
    if outcome is None:
        return (scored, {})
    order, nouls = outcome
    reordered = [top[i] for i in order] + scored[len(top):]
    return (reordered, {top[i][1]: noul for i, noul in nouls.items()})
_VERSION_TAIL_RE = re.compile('(?:[-_ ]v?\\d+(?:\\.\\d+)*|\\d+\\.\\d+(?:\\.\\d+)*)+$')
_VERSION_NUM_RE = re.compile('\\d+')

def _version_family(name: str) -> tuple[str, tuple[int, ...]]:
    stem = name[:-3] if name.lower().endswith('.md') else name
    m = _VERSION_TAIL_RE.search(stem)
    if not m:
        return (stem, ())
    version = tuple((int(x) for x in _VERSION_NUM_RE.findall(m.group(0))))
    return (stem[:m.start()], version)

def _collapse_version_families(entries: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    families: dict[str, list[str]] = {}
    for name in entries:
        root, _version = _version_family(name)
        families.setdefault(root, []).append(name)
    canonical: dict[str, Any] = {}
    report: list[dict[str, Any]] = []
    for names in families.values():
        if len(names) == 1:
            canonical[names[0]] = entries[names[0]]
            continue
        kept = max(((_version_family(n)[1], int(entries[n].get('lastmod_ms') or 0), n) for n in names))[2]
        canonical[kept] = entries[kept]
        report.append({'kept': kept, 'dropped': sorted((n for n in names if n != kept))})
    return (canonical, report)

def _title_numbers(entry: dict[str, Any]) -> list[str]:
    return _BUG_NUM_RE.findall(str(entry.get('title') or ''))

def locate_spec(index: dict[str, Any], query_title: str, bug_numbers: list[str] | None=None, *, rerank: bool=True) -> dict[str, Any]:
    """定位管辖 SPEC；``rerank=False`` 关闭 Jev 精排（回放确定性谓词专用）。

    回放路径（authority_decision_reentry）把本函数当确定性谓词复核历史绑定，
    必须显式传 ``rerank=False``，保证同一索引同一标题永远同一结论。
    """
    raw_entries: dict[str, Any] = index.get('entries') or {}
    entries, version_dedup = _collapse_version_families(raw_entries)
    nums = list(bug_numbers or []) or _BUG_NUM_RE.findall(str(query_title))

    def _result(status: str, channel: str | None, matches: list[dict]) -> dict:
        return {'status': status, 'channel': channel, 'matches': matches, 'version_dedup': version_dedup}
    for field, channel, can_match in (('bug_numbers_filename', 'bug_filename', True), ('__title__', 'bug_title', True), ('bug_numbers_anchored', 'bug_anchored', True), ('bug_numbers_body', 'bug_body', False)):
        hits = []
        for name, e in entries.items():
            pool = _title_numbers(e) if field == '__title__' else e.get(field) or []
            matched_nums = [n for n in nums if n in pool]
            if matched_nums:
                hits.append({'file': name, 'title': e.get('title') or '', 'evidence': f"{channel}:{','.join(matched_nums)}"})
        if len(hits) == 1 and can_match:
            return _result('matched', channel, hits)
        if hits:
            return _result('candidates', channel, hits)
    qt = _tokens(str(query_title))
    scored = []
    if qt:
        for name, e in entries.items():
            claimed_nums = set(e.get('bug_numbers_filename') or []) | set(_title_numbers(e)) | set(e.get('bug_numbers_anchored') or [])
            if nums and claimed_nums and claimed_nums.isdisjoint(nums):
                continue
            face = _tokens(name + ' ' + str(e.get('title') or ''))
            face.update(e.get('body_keywords') or [])
            overlap = qt & face
            if len(overlap) >= _SEMANTIC_FLOOR:
                scored.append((len(overlap), name, e, sorted(overlap)))
        scored.sort(key=lambda t: (-t[0], t[1]))
    if scored:
        jev_nouls: dict[str, float] = {}
        if rerank:
            scored, jev_nouls = _jev_rerank_semantic(scored, str(query_title))
        matches = [{'file': name, 'title': e.get('title') or '', 'score': score, 'evidence': 'semantic:' + '/'.join(ov[:6]) + (f';jev:noul={jev_nouls[name]:.2f}' if name in jev_nouls else '')} for score, name, e, ov in scored[:_SEMANTIC_TOP]]
        return _result('candidates', 'semantic', matches)
    return _result('no_governing_spec', None, [])

def load_index(path: Path) -> dict[str, Any] | None:
    try:
        raw = _read_bounded(Path(path), label='spec index', max_bytes=_INDEX_MAX_BYTES)
        validate_json_budget(raw, error_type=ValueError, message='spec index exceeds the JSON structure budget')
        data = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or not accepts_schema(data.get('schema'), 'ist.spec_index'):
        return None
    return data

@dataclass(frozen=True)
class ResolvedIndexedSpec:
    path: Path
    content: bytes
    sha256: str
    size: int
    generation_id: str
    manifest_sha256: str

def resolve_indexed_spec(project_root: Path, name: str) -> ResolvedIndexedSpec | None:
    root = Path(project_root)
    text = str(name or '').strip()
    relative = Path(text)
    if not text or relative.is_absolute() or len(relative.parts) != 1 or (relative.name != text):
        return None
    try:
        generation = resolve_active_spec_generation(root)
    except SpecGenerationUnavailable:
        return None
    index = load_index(generation.index)
    if not isinstance(index, dict) or text not in (index.get('entries') or {}):
        return None
    candidate = generation.docs / text
    entry = index['entries'][text]
    if not isinstance(entry, dict) or not isinstance(entry.get('size'), int) or entry['size'] < 1 or (entry['size'] > _SPEC_MAX_BYTES) or (not re.fullmatch('[0-9a-f]{64}', str(entry.get('sha256') or ''))):
        return None
    try:
        content = _read_bounded(candidate, label='indexed spec document', max_bytes=_SPEC_MAX_BYTES)
    except (OSError, ValueError):
        return None
    if len(content) != entry['size'] or hashlib.sha256(content).hexdigest() != entry['sha256']:
        return None
    return ResolvedIndexedSpec(path=candidate.absolute(), content=content, sha256=entry['sha256'], size=entry['size'], generation_id=generation.generation_id, manifest_sha256=generation.manifest_sha256)
