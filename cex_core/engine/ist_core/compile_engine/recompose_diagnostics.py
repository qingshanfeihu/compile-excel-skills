# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/recompose_diagnostics.py（sha256 3e9a4a8cbb6359cf）。不在这里手改。
"""重封身份的只读诊断；本模块不决定是否重封。"""
from __future__ import annotations
import hashlib
import re
AXES = {'mindmap_source_sha256': '脑图源', 'governing_spec_status_sha256': '管辖SPEC', 'defect_spec_status_sha256': 'DefectSpec', 'criterion_rules_sha256': '判据规则'}

def criterion_rules_sha256() -> str | None:
    from cex_core.engine.case_compiler.criterion_author_rules import AUTHOR_RULE_PATH
    from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
    try:
        raw = read_regular_nofollow(AUTHOR_RULE_PATH, error_type=ValueError, invalid_message='criterion rule path is invalid', directory_message='criterion rule directory is unavailable', open_message='criterion rules are unavailable', bounds_message='criterion rules exceed the byte budget', changed_message='criterion rules changed while reading', max_bytes=32 * 1024 * 1024, min_bytes=0)
    except (OSError, ValueError):
        return None
    return hashlib.sha256(raw).hexdigest()

def compare_axes(previous: dict, current: dict) -> dict:
    changed, unverified = ([], [])
    for field in AXES:
        old, new = (previous.get(field), current.get(field))
        if not all((isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in (old, new))):
            unverified.append(field)
        elif old != new:
            changed.append(field)
    return {'changed_axes': changed, 'unverified_axes': unverified, 'error_text': '重封身份对照：变化轴=' + ('、'.join((AXES[x] for x in changed)) or '无已证变化轴') + '；未核轴=' + ('、'.join((AXES[x] for x in unverified)) or '无')}

def stamp_receipt(receipt: dict, facts: list[dict]) -> dict:
    current = dict(receipt)
    current['criterion_rules_sha256'] = criterion_rules_sha256()
    previous = next((row for row in reversed(facts) if row.get('ev') == 'recompose_done'), {})
    current.update(compare_axes(previous, current))
    return current
