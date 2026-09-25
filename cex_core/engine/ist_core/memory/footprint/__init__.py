# 生成：tools/extract_engine.py ← InfoTest main/ist_core/memory/footprint/__init__.py（sha256 12c23f8787361285）。不在这里手改。
from __future__ import annotations
from cex_core.engine.ist_core.memory.footprint.schema import MergeResult, RawFact, RoutedFact
from cex_core.engine.ist_core.memory.footprint.extractor import extract_facts
from cex_core.engine.ist_core.memory.footprint.router import route_facts
from cex_core.engine.ist_core.memory.footprint.merger import merge_fact
from cex_core.engine.ist_core.memory.footprint.reconcile import reconcile
from cex_core.engine.ist_core.memory.footprint.index import FootprintIndex, get_footprint_index, invalidate_footprint_index
__all__ = ['RawFact', 'RoutedFact', 'MergeResult', 'extract_facts', 'route_facts', 'merge_fact', 'reconcile', 'FootprintIndex', 'get_footprint_index', 'invalidate_footprint_index']
