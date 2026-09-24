# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/rebind_binder.py（sha256 4a4a76da2a1d61b3）。不在这里手改。
from __future__ import annotations
from typing import Any, Mapping
REBINDABLE_VERDICT = 'rebindable'
LOAD_BEARING_VERDICT = 'load_bearing'
REBIND_VERDICTS = frozenset({REBINDABLE_VERDICT, LOAD_BEARING_VERDICT})

class RebindBinderError(ValueError):
    pass

def _validate_license_shape(license_: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(license_, dict):
        return None
    author_literal = str(license_.get('author_literal') or '').strip()
    verdict = str(license_.get('verdict') or '').strip()
    occurrences = license_.get('occurrences')
    constraints = license_.get('constraints')
    reason = str(license_.get('reason') or '').strip()
    if not author_literal or verdict not in REBIND_VERDICTS or (not isinstance(occurrences, list)) or any((not isinstance(item, str) or not item.strip() for item in occurrences)) or (not isinstance(constraints, str)) or (not reason):
        return None
    return {'author_literal': author_literal, 'verdict': verdict, 'occurrences': [str(item).strip() for item in occurrences], 'constraints': constraints, 'reason': reason, '_index': index}

def _concretization_author_text_grounded(case: Mapping[str, Any], author_text: str) -> bool:
    from cex_core.engine.case_compiler.mindmap_contract_projector import ground_source_span
    for step in case.get('steps') or ():
        if not isinstance(step, Mapping):
            continue
        if ground_source_span(author_text, str(step.get('text') or '')) is not None:
            return True
    return False

def _validate_concretization_shape(item: Any, case: Mapping[str, Any] | None=None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    slot = str(item.get('slot') or '').strip()
    author_text = str(item.get('author_text') or '').strip()
    value = str(item.get('value') or '').strip()
    source = str(item.get('source') or '').strip()
    reason = str(item.get('reason') or '').strip()
    if not slot or not author_text or (not value) or (not reason) or (source not in {'command_tree', 'manual'}):
        return None
    if case is not None and case.get('steps') and (not _concretization_author_text_grounded(case, author_text)):
        return None
    return {'slot': slot, 'author_text': author_text, 'value': value, 'source': source, 'reason': reason}

def validate_case_enhancement_fields(case: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    licenses = case.get('rebind_licenses')
    if licenses is not None:
        if not isinstance(licenses, list):
            errors.append('rebind_licenses must be an array')
        else:
            parsed: list[dict[str, Any]] = []
            for index, license_ in enumerate(licenses):
                item = _validate_license_shape(license_, index)
                if item is None:
                    errors.append(f'rebind_licenses[{index}] is invalid; expected author_literal, verdict=rebindable|load_bearing, occurrences[], string constraints, and reason')
                else:
                    parsed.append(item)
            literals = [item['author_literal'] for item in parsed]
            if len(literals) != len(set(literals)):
                errors.append('rebind_licenses author_literal values must be unique')
    concretizations = case.get('concretizations')
    if concretizations is not None:
        if not isinstance(concretizations, list):
            errors.append('concretizations must be an array')
        else:
            for index, item in enumerate(concretizations):
                author_text = str((item or {}).get('author_text') or '').strip() if isinstance(item, dict) else ''
                if _validate_concretization_shape(item, case) is None:
                    if author_text and case.get('steps'):
                        errors.append(f'concretizations[{index}] author_text does not occur in any authored step, even with whitespace runs normalized')
                    else:
                        errors.append(f'concretizations[{index}] is invalid; expected exactly slot, non-empty author_text grounded in the authored steps, value, source=command_tree|manual, reason')
    proposal = case.get('proposal')
    if proposal is not None and (not isinstance(proposal, list) or any((not isinstance(item, str) or not item.strip() for item in proposal))):
        errors.append('proposal must be an array of non-empty strings')
    return errors
