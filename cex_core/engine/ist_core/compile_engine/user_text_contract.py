# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/user_text_contract.py（sha256 eddea5c18e79fc83）。不在这里手改。
from __future__ import annotations
import re
from typing import Literal, Mapping, TypedDict
USER_TEXT_VALIDATION_SCHEMA = 'ist.user-text-validation'

class InternalTermViolation(TypedDict):
    code: Literal['internal_term_in_user_text']
    field: str
    terms: list[str]

class UserTextValidationResult(TypedDict):
    schema: Literal['ist.user-text-validation']
    accepted: bool
    violations: list[InternalTermViolation]

def _internal_user_text_terms() -> frozenset[str]:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as taxonomy
    from cex_core.engine.ist_core.compile_engine import render
    from cex_core.engine.ist_core.compile_engine import views
    state_names = {name for name in dir(views) if name.startswith('S_')}
    words = {str(getattr(views, name) or '') for name in state_names}
    words |= state_names
    words |= set(taxonomy.BLOCKING_CLASSES) | set(taxonomy.ABANDON_CLASSES) | {taxonomy.B_UNCLASSIFIED, taxonomy.NOT_OBJECTIVE}
    for translations in (render.STATUS_CN, render.DISP_CN, render.SHAPE_CN, render.ACTION_CN, render.CTX_CN):
        words.update((str(term) for term in translations))
    words |= {'ask_panel', 'adopted', 'not_run', 'gate_disabled', 'writeback_failed', 'rollback_failed', 'emit_invalid', 'report_mismatch', 'delivery_incomplete', 'needs_decision', 'needs_decision.json', 'manifest.json', 'mechanical_case.json', 'authoring_failure', 'authoring_exhausted'}
    return frozenset((word for word in words if word))
_INTERNAL_USER_TEXT_TERMS = _internal_user_text_terms()

def internal_term_hits(text: str) -> list[str]:
    source = str(text or '')
    hits = []
    for term in _INTERNAL_USER_TEXT_TERMS:
        pattern = f'(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])'
        if re.search(pattern, source):
            hits.append(term)
    return sorted(hits, key=lambda value: (value.casefold(), value))

def validate_user_facing_text(fields: Mapping[str, object]) -> UserTextValidationResult:
    violations: list[InternalTermViolation] = []
    for field, value in fields.items():
        terms = internal_term_hits(str(value or ''))
        if terms:
            violations.append({'code': 'internal_term_in_user_text', 'field': str(field), 'terms': terms})
    return {'schema': USER_TEXT_VALIDATION_SCHEMA, 'accepted': not violations, 'violations': violations}
__all__ = ['USER_TEXT_VALIDATION_SCHEMA', 'InternalTermViolation', 'UserTextValidationResult', 'internal_term_hits', 'validate_user_facing_text']
