# 生成：tools/extract_engine.py ← InfoTest main/ist_core/memory/footprint/reconcile.py（sha256 8841b5d4b163a6ce）。不在这里手改。
from __future__ import annotations
import json
import logging
from pathlib import Path
from cex_core.engine.ist_core.memory.footprint.schema import node_template
logger = logging.getLogger(__name__)
NODES_DIR = 'nodes'

def _height_to_level(height: int) -> str:
    if height == 0:
        return 'leaf'
    if height == 1:
        return 'trunk'
    return 'branch'

def _parent_id(feature_id: str) -> str | None:
    if '.' not in feature_id:
        return None
    return feature_id.rsplit('.', 1)[0]

def reconcile(footprint_dir: Path, nodes_subdir: str='nodes') -> dict:
    nodes_dir = footprint_dir / nodes_subdir
    if not nodes_dir.exists():
        return {'total': 0, 'created': 0, 'by_level': {}}
    nodes: dict[str, dict] = {}
    for f in nodes_dir.glob('*.json'):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning('reconcile 读取失败 %s: %s', f, exc)
            continue
        fid = d.get('feature_id')
        if fid:
            nodes[fid] = d
    if not nodes:
        return {'total': 0, 'created': 0, 'by_level': {}}
    created = 0
    for fid in list(nodes.keys()):
        parent = _parent_id(fid)
        while parent is not None:
            if parent not in nodes:
                nodes[parent] = node_template(parent)
                created += 1
            parent = _parent_id(parent)
    children: dict[str, list[str]] = {fid: [] for fid in nodes}
    for fid in nodes:
        parent = _parent_id(fid)
        if parent is not None and parent in children:
            children[parent].append(fid)
    height_cache: dict[str, int] = {}

    def height(fid: str) -> int:
        if fid in height_cache:
            return height_cache[fid]
        kids = children.get(fid, [])
        h = 0 if not kids else max((height(k) for k in kids)) + 1
        height_cache[fid] = h
        return h
    by_level: dict[str, int] = {}
    for fid, node in nodes.items():
        lvl = _height_to_level(height(fid))
        node['level'] = lvl
        node['children'] = sorted(children.get(fid, []))
        by_level[lvl] = by_level.get(lvl, 0) + 1
        path = nodes_dir / f'{fid}.json'
        path.write_text(json.dumps(node, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'total': len(nodes), 'created': created, 'by_level': by_level}
