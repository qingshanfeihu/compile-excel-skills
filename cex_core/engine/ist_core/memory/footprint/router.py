# 生成：tools/extract_engine.py ← InfoTest main/ist_core/memory/footprint/router.py（sha256 8a0dec1541785d9f）。不在这里手改。
from __future__ import annotations
import re
from dataclasses import replace
from cex_core.engine.ist_core.memory.footprint.schema import RawFact, RoutedFact, anchor_paths
NODES_DIR = 'nodes'
_SAFE_FEATURE_SEG = re.compile('[A-Za-z0-9_\\-]+')
_OP_PREFIXES = ('no', 'show', 'clear')
_MD_ESCAPE_RE = re.compile('\\\\([_*~\\[\\]{}<>|])')
_CLEAN_TOKEN_RE = re.compile('[a-z0-9][a-z0-9_\\-]*')

def catalog_head_tokens_clean(head_tokens, *, strip_verbs: bool=False) -> list[str]:
    toks = []
    for raw in head_tokens or []:
        tok = _MD_ESCAPE_RE.sub('\\1', str(raw)).strip().lower()
        if _CLEAN_TOKEN_RE.fullmatch(tok):
            toks.append(tok)
    if strip_verbs:
        while toks and toks[0] in _OP_PREFIXES:
            toks = toks[1:]
    return toks

def catalog_feature_path(head_tokens) -> list[str]:
    return catalog_head_tokens_clean(head_tokens, strip_verbs=True)

def _feature_id_safe(feature_id: str) -> bool:
    if not feature_id or feature_id.startswith('.') or '..' in feature_id:
        return False
    return all((_SAFE_FEATURE_SEG.fullmatch(seg) for seg in feature_id.split('.')))

def route_facts(facts: list[RawFact], footprint_dir=None, nodes_subdir: str='nodes') -> list[RoutedFact]:
    results: list[RoutedFact] = []
    for fact in facts:
        targets = anchor_paths(fact.cli_commands, fallback=fact.feature_path)
        for path in targets:
            feature_id = '.'.join(path)
            if not feature_id:
                continue
            if not _feature_id_safe(feature_id):
                continue
            bound = fact if list(path) == list(fact.feature_path) else replace(fact, feature_path=list(path))
            results.append(RoutedFact(fact=bound, level='leaf', target_file=f'{nodes_subdir}/{feature_id}.json'))
    return results
