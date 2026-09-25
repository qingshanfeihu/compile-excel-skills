# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/rule_registry.py（sha256 698c156b3589b684）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import difflib
import hashlib
import json
from functools import lru_cache
from pathlib import Path
SCHEMA = 'ist.ide.rule-registry'
_REGISTRY_PATH = _cex_data_path('') / 'knowledge' / 'data' / 'compile_ref' / 'rule_registry.json'

class RuleRegistryUnavailable(RuntimeError):
    pass

@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        payload = json.loads(_REGISTRY_PATH.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuleRegistryUnavailable(f'rule registry unreadable: {type(exc).__name__}') from exc
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA:
        raise RuleRegistryUnavailable('rule registry schema mismatch')
    body = {'schema': payload.get('schema'), 'rules': payload.get('rules')}
    recomputed = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    meta = payload.get('_meta') or {}
    if recomputed != str(meta.get('content_sha256') or ''):
        raise RuleRegistryUnavailable('rule registry content drifted from its generator output')
    return payload

def all_rule_ids() -> list[str]:
    return [str(r.get('rule_id') or '') for r in _load().get('rules') or []]

def get_rule(rule_id: str) -> dict | None:
    for rule in _load().get('rules') or []:
        if str(rule.get('rule_id') or '') == str(rule_id or ''):
            return dict(rule)
    return None

def nearest_candidates(rule_id: str, limit: int=3) -> list[str]:
    return difflib.get_close_matches(str(rule_id or ''), all_rule_ids(), n=limit, cutoff=0.4)

def applicability_error(rule_id: str, capability_family: str, verification_shape: str='') -> str:
    rule = get_rule(rule_id)
    if rule is None:
        hint = nearest_candidates(rule_id)
        return f'selected_rule_id {rule_id!r} is not in the rule registry' + (f'; nearest candidates: {hint}' if hint else '')
    applicability = rule.get('applicability') or {}
    families = list(applicability.get('capability_families') or [])
    if families and str(capability_family or '') not in families:
        return f'rule {rule_id!r} does not apply to capability family {capability_family!r}; applicable families: {families}'
    shapes = list(applicability.get('verification_shapes') or [])
    if shapes and verification_shape and (verification_shape not in shapes):
        return f'rule {rule_id!r} does not apply to verification shape {verification_shape!r}; applicable shapes: {shapes}'
    return ''

def rule_snapshot(rule_id: str, capability_family: str) -> dict:
    rule = get_rule(rule_id) or {}
    family_status = rule.get('family_status') or {}
    status = str(family_status.get(str(capability_family or '')) or rule.get('status') or '')
    return {'rule_id': str(rule.get('rule_id') or rule_id), 'name_zh': str(rule.get('name_zh') or ''), 'status': status, 'zh_template': str(rule.get('zh_template') or '')}
