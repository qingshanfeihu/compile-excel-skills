# 生成：tools/extract_engine.py ← InfoTest main/ist_core/memory/footprint/index.py（sha256 8a5a4f58b2ef3900）。不在这里手改。
from __future__ import annotations
import difflib
import json
import logging
import re
from pathlib import Path
logger = logging.getLogger(__name__)
_TOKEN_SPLIT_RE = re.compile('[^\\w一-鿿]+')
_BUG_RE = re.compile('BUG-\\d+', re.IGNORECASE)
_OP_PREFIXES = ('no', 'show', 'clear')

def _command_pattern_matches(pattern: str, concrete: str) -> bool:
    ptoks = pattern.lower().split()
    ctoks = concrete.lower().split()
    if not ptoks or not ctoks or len(ctoks) > len(ptoks):
        return False
    for p, c in zip(ptoks, ctoks):
        if p.startswith('{') and p.endswith('}'):
            if c not in [a.strip() for a in p[1:-1].split('|')]:
                return False
        elif p != c:
            return False
    return True

def _format_footprint(data: dict) -> str:
    lines: list[str] = []
    fid = data.get('feature_id', '?')
    level = data.get('level', '?')
    meta = data.get('footprint_meta', {})
    lines.append(f"[{fid}] ({level}, verified {meta.get('verified_count', 0)}x)")
    cli = data.get('cli', {}).get('commands', [])
    for cmd in cli[:5]:
        if isinstance(cmd, dict) and (cmd.get('catalog_head') or '').strip():
            from cex_core.engine.ist_core.memory.footprint.catalog_join import join_catalog_entry, join_miss_label, join_miss_reason
            joined = join_catalog_entry(cmd)
            if joined is not None:
                ident = joined['identity']
                lines.append(f"  cmd: {joined['verbatim'] or joined['head']}  [catalog {ident['family']}@{ident['version']}]")
            else:
                label = join_miss_label(join_miss_reason(cmd))
                lines.append(f"  cmd: {str(cmd['catalog_head']).strip()}  [{label}]")
            continue
        lines.append(f"  cmd: {cmd.get('command', '')}")

    def _obs_tag(e: dict) -> str:
        v = e.get('validity', '')
        ou = e.get('observed_under', '')
        tag = '|'.join((x for x in (v, ou and f'语境:{ou[:60]}') if x))
        return f'[{tag}] ' if tag else ''
    for r in data.get('decision_rules', [])[:4]:
        cond = r.get('condition', '')[:120]
        dec = r.get('decision', '')
        if dec:
            lines.append(f'  rule: {_obs_tag(r)}{cond} → {dec}')
        else:
            lines.append(f'  rule: {_obs_tag(r)}{cond}')
    for b in data.get('behaviors', [])[:3]:
        lines.append(f"  behavior: {_obs_tag(b)}{b.get('content', '')[:120]}")
    for iss in data.get('known_issues', [])[:4]:
        lines.append(f"  issue: {iss.get('issue_id', '')} {iss.get('title', '')[:80]}")
    vs = data.get('version_scope', {})
    if vs.get('product_versions'):
        lines.append(f"  versions: {', '.join(vs['product_versions'][:5])}")
    return '\n'.join(lines)

class FootprintIndex:
    _MAX_LOAD_RETRY = 3

    def __init__(self, footprint_dir: Path):
        self._dir = footprint_dir
        self._nodes: dict[str, dict] = {}
        self._bug_index: dict[str, str] = {}
        self._token_index: dict[str, set[str]] = {}
        self._loaded = False
        self._load_attempts = 0

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self._dir.exists():
            self._loaded = True
            return
        self._load_attempts += 1
        transient_skipped = 0
        for f in self._dir.rglob('*.json'):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                logger.warning('footprint 节点 JSON 损坏(永久跳过)%s: %s', f, exc)
                continue
            except OSError as exc:
                transient_skipped += 1
                logger.debug('footprint 读失败(瞬态)%s: %s', f, exc)
                continue
            fid = data.get('feature_id')
            if not fid:
                continue
            self._nodes[fid] = data
            for issue in data.get('known_issues', []):
                bug = issue.get('issue_id')
                if bug:
                    self._bug_index[bug.upper()] = fid
            tokens_to_index: set[str] = set()
            for tok in fid.split('.'):
                if tok:
                    tokens_to_index.add(tok.lower())
            content_str = json.dumps(data, ensure_ascii=False).lower()
            for tok in _TOKEN_SPLIT_RE.split(content_str):
                if len(tok) >= 2:
                    tokens_to_index.add(tok)
            for tok in tokens_to_index:
                self._token_index.setdefault(tok, set()).add(fid)
        if transient_skipped and self._load_attempts < self._MAX_LOAD_RETRY:
            logger.warning('FootprintIndex 偏载:%d 节点、%d 个瞬态读失败跳过——不缓存,第 %d 次重试', len(self._nodes), transient_skipped, self._load_attempts)
            self._nodes.clear()
            self._bug_index.clear()
            self._token_index.clear()
            return
        self._loaded = True
        if transient_skipped:
            logger.warning('FootprintIndex 载入 %d 节点、%d 个瞬态读失败仍跳过(重试达上限 %d)', len(self._nodes), transient_skipped, self._MAX_LOAD_RETRY)
        else:
            logger.info('FootprintIndex loaded: %d nodes, %d BUG, %d tokens', len(self._nodes), len(self._bug_index), len(self._token_index))

    def lookup(self, command: str) -> dict | None:
        self._ensure_loaded()
        if not command:
            return None
        result = self._lookup_key(command)
        if result is not None:
            return result
        completed = self._complete_token_prefixes(command)
        if completed is not None:
            result = self._lookup_key(completed)
            if result is not None:
                return result
        toks = command.lower().split()
        j = 0
        while j < len(toks) and toks[j] in _OP_PREFIXES:
            j += 1
        if 0 < j < len(toks):
            bare = ' '.join(toks[j:])
            result = self._lookup_key(bare)
            if result is not None:
                return result
            completed = self._complete_token_prefixes(bare)
            if completed is not None:
                return self._lookup_key(completed)
        return None

    def _complete_token_prefixes(self, command: str) -> str | None:
        toks = command.lower().split()
        if len(toks) < 2:
            return None
        prefix = ''
        out: list[str] = []
        changed = False
        for t in toks:
            base = prefix + '.' if prefix else ''
            segs = {k[len(base):].split('.', 1)[0] for k in self._nodes if k.startswith(base)}
            if t in segs:
                out.append(t)
            else:
                cands = [s for s in segs if s.startswith(t)]
                if len(cands) != 1:
                    return None
                out.append(cands[0])
                changed = True
            prefix = '.'.join(out)
        return ' '.join(out) if changed else None

    def _lookup_key(self, command: str) -> dict | None:
        key = '.'.join(command.lower().split())
        if key in self._nodes:
            result = dict(self._nodes[key])
            if not result.get('children'):
                prefix_matches = sorted((m['feature_id'] for k, m in self._nodes.items() if k.startswith(key + '.')))
                if prefix_matches:
                    result['children'] = prefix_matches
            return result
        prefix_matches = sorted((m['feature_id'] for k, m in self._nodes.items() if k.startswith(key + '.')))
        if prefix_matches:
            return {'feature_id': key, 'level': 'branch', 'children': prefix_matches, 'summary': f'找到 {len(prefix_matches)} 个子节点'}
        return self._alternation_lookup(command)

    def _alternation_lookup(self, command: str) -> dict | None:
        toks = command.lower().split()
        for i in range(len(toks) - 1, 0, -1):
            parent_key = '.'.join(toks[:i])
            node = self._nodes.get(parent_key)
            if not node:
                continue
            for cmd in (node.get('cli', {}) or {}).get('commands', []):
                if _command_pattern_matches(cmd.get('command', ''), command):
                    return self.lookup(parent_key)
        return None

    def search(self, query: str, *, top_k: int=3) -> list[tuple[str, str]]:
        self._ensure_loaded()
        if not query or not self._nodes:
            return []
        scores: dict[str, int] = {}
        for bug in _BUG_RE.findall(query):
            fid = self._bug_index.get(bug.upper())
            if fid:
                scores[fid] = scores.get(fid, 0) + 100
        query_tokens = [t for t in _TOKEN_SPLIT_RE.split(query.lower()) if t]
        for tok in query_tokens:
            for fid in self._token_index.get(tok, ()):
                scores[fid] = scores.get(fid, 0) + 5
        if not scores:
            for fid, data in self._nodes.items():
                content_str = json.dumps(data, ensure_ascii=False).lower()
                hits = sum((1 for tok in query_tokens if tok in content_str))
                if hits > 0:
                    scores[fid] = hits
        q_low = query.lower()
        q_compact = q_low.replace(' ', '')

        def _subseq_depth(node_compact: str) -> int:
            it = iter(enumerate(q_compact))
            depth = -1
            for c in node_compact:
                for i, qc in it:
                    if qc == c:
                        depth = i
                        break
                else:
                    return -1
            return depth

        def _tiebreak(fid: str) -> tuple:
            node = fid.replace('.', ' ').lower()
            depth = _subseq_depth(node.replace(' ', ''))
            if depth >= 0:
                return (1, depth, -len(node))
            return (0, difflib.SequenceMatcher(None, q_low, node).ratio(), 0)
        ranked = sorted(scores.items(), key=lambda kv: (kv[1], _tiebreak(kv[0])), reverse=True)[:top_k]
        return [(fid, _format_footprint(self._nodes[fid])) for fid, _ in ranked]

    def stats(self) -> dict:
        self._ensure_loaded()
        by_level: dict[str, int] = {}
        total_facts = 0
        most_verified: list[tuple[str, int, int]] = []
        for fid, data in self._nodes.items():
            level = data.get('level', '?')
            by_level[level] = by_level.get(level, 0) + 1
            facts = len(data.get('cli', {}).get('commands', [])) + len(data.get('decision_rules', [])) + len(data.get('behaviors', [])) + len(data.get('known_issues', []))
            total_facts += facts
            verified = data.get('footprint_meta', {}).get('verified_count', 0)
            most_verified.append((fid, verified, facts))
        most_verified.sort(key=lambda x: -x[1])
        return {'total_nodes': len(self._nodes), 'by_level': by_level, 'total_facts': total_facts, 'total_bugs': len(self._bug_index), 'top_nodes': most_verified[:5]}

    def list_nodes(self, level: str | None=None) -> list[str]:
        self._ensure_loaded()
        if level is None:
            return sorted(self._nodes.keys())
        return sorted((fid for fid, data in self._nodes.items() if data.get('level') == level))

    def invalidate(self) -> None:
        self._loaded = False
        self._nodes.clear()
        self._bug_index.clear()
        self._token_index.clear()
_FOOTPRINT_INDEX_SINGLETONS: dict[str, FootprintIndex] = {}

def get_footprint_index(nodes_subdir: str='nodes') -> FootprintIndex:
    idx = _FOOTPRINT_INDEX_SINGLETONS.get(nodes_subdir)
    if idx is None:
        from cex_core.engine import knowledge_paths as kp
        fp_dir = kp.KNOWLEDGE_FOOTPRINTS / nodes_subdir
        if nodes_subdir != 'nodes' and (not fp_dir.is_dir()):
            logger.info('footprint 版本分区 %s 不存在，回退默认 nodes/（优雅降级）', nodes_subdir)
            return get_footprint_index('nodes')
        idx = FootprintIndex(fp_dir)
        _FOOTPRINT_INDEX_SINGLETONS[nodes_subdir] = idx
    return idx

def invalidate_footprint_index(nodes_subdir: str | None=None) -> None:
    if nodes_subdir is not None:
        idx = _FOOTPRINT_INDEX_SINGLETONS.pop(nodes_subdir, None)
        if idx is not None:
            idx.invalidate()
    else:
        for idx in _FOOTPRINT_INDEX_SINGLETONS.values():
            idx.invalidate()
        _FOOTPRINT_INDEX_SINGLETONS.clear()
