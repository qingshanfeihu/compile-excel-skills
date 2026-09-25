# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/criterion_normalization.py（sha256 5b40e7cf22f48e30）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from cex_core.engine.common.schema_identity import accepts_schema
from cex_core.engine.case_compiler.criterion_carriers import RequirementSource, carrier_contract_sha256, derive_required_carriers
from cex_core.engine.case_compiler.mindmap_contract_projector import AUTHORED_STEP_CAUSE_ORIGIN, authored_expectation_step_binding, with_authored_step_anchor
ROOT = _cex_data_path('')
PROJECTION_PATH = ROOT / 'knowledge/data/compile_ref/criterion_rules.json'
NORMALIZED_CLAIM_SCHEMA = 'ist.normalized-claim'
_CHECK_LOCATOR_RE = re.compile('\\[check[0-9]+\\]', re.IGNORECASE)
_ASCII_TOKEN_RE = re.compile('(?<![A-Za-z0-9_-])([A-Za-z][A-Za-z0-9_-]*)(?![A-Za-z0-9_-])')

class CriterionNormalizationError(ValueError):
    pass

@dataclass(frozen=True)
class NormalizationResult:
    expectations: tuple[dict[str, Any], ...]
    disclosures: tuple[dict[str, Any], ...]
    pending: tuple[dict[str, Any], ...]

def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def load_projection(path: Path=PROJECTION_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CriterionNormalizationError('criterion rule projection is unavailable') from exc
    if not isinstance(payload, dict) or not accepts_schema(payload.get('schema'), 'ist.criterion-rules'):
        raise CriterionNormalizationError('criterion rule projection schema is invalid')
    expected = str(payload.get('projection_sha256') or '')
    body = {key: value for key, value in payload.items() if key != 'projection_sha256'}
    if not re.fullmatch('[0-9a-f]{64}', expected) or _canonical_sha256(body) != expected:
        raise CriterionNormalizationError('criterion rule projection identity is invalid')
    types = payload.get('criterion_types')
    rules = payload.get('rules')
    if not isinstance(types, list) or not isinstance(rules, list):
        raise CriterionNormalizationError('criterion rule projection is incomplete')
    carrier_identity = (payload.get('identity') or {}).get('criterion_carrier_contract_sha256')
    if carrier_identity != carrier_contract_sha256():
        raise CriterionNormalizationError('criterion carrier projection identity is stale')
    return payload

def _criterion_type_ids(projection: Mapping[str, Any]) -> frozenset[str]:
    return frozenset((str(row.get('criterion_type') or '') for row in projection.get('criterion_types') or [] if isinstance(row, dict) and str(row.get('criterion_type') or '')))

def _semantic_text(text: Any) -> str:
    return ' '.join(_CHECK_LOCATOR_RE.sub('', str(text or '')).split()).strip()

def _claim_step_binding(claim: Mapping[str, Any], *, autoid: str, mindmap_text: str, source_text: str | None=None) -> tuple[int | None, str | None]:
    """这条主张说的是哪一步，以及绑不到时是哪一种绑不到。

    取的是脑图结构里作者自己的绑定（期望节点挂在哪个步骤节点下、或哪一步原文带它的
    ``[<标签>]`` 定位符）。**不取 ``semantic_key`` 的 ``:step:N`` 尾巴**——尾巴取自
    ``expectations_by_step.n``，而 ``origin=expectation:<数字>`` 的行里那个数字是期望
    自己的序号、不是步号，全语料大多数恒为 1；拿它当步指针会让「配置在前、主张在后」
    这类先后谓词恒假，规则整族在决策路径上根本到不了。绑不到就当不知道，不折叠成首步。

    成因码是三值闭集（``mindmap_contract_projector.AUTHORED_STEP_UNKNOWN_CAUSES``）：
    三种绑不到的修法各不相同，折成同一个 ``None`` 时下游看不出该动哪里。
    typed 主张与 ``author_claim`` 走同一条读法——两边都带 ``origin``。

    ``source_text`` 缺省取 claim 自己记的那一份；调用侧可以传期望行的原文，那两者对
    ``author_claim`` 逐字相同（``contract_entry`` 硬核），而 typed 记录本来不存原文。
    """
    return authored_expectation_step_binding(str(mindmap_text or ''), autoid=str(claim.get('autoid') or autoid or ''), origin=str(claim.get('origin') or ''), source_text=str((claim.get('source_text') if source_text is None else source_text) or ''))

def _claim_step(claim: Mapping[str, Any], *, autoid: str, mindmap_text: str) -> int | None:
    """只要步号、不要成因码时用这个。"""
    return _claim_step_binding(claim, autoid=autoid, mindmap_text=mindmap_text)[0]

def _step_texts(case: Mapping[str, Any]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for index, step in enumerate(case.get('steps') or [], start=1):
        if not isinstance(step, dict):
            continue
        try:
            number = int(str(step.get('n') or index))
        except ValueError:
            number = index
        text = str(step.get('text') or '')
        if text.strip():
            out.append((number, text))
    return out

def _head_pattern(head: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in str(head).split() if part]
    if not parts:
        return re.compile('(?!x)x')
    return re.compile('(?<![A-Za-z0-9_-])' + '\\s+'.join(parts) + '(?![A-Za-z0-9_-])', re.IGNORECASE)

def _object_occurrences(case: Mapping[str, Any], projection: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    classes = projection.get('object_classes')
    if not isinstance(classes, dict):
        raise CriterionNormalizationError('criterion object classes are unavailable')
    steps = _step_texts(case)
    out: dict[str, list[dict[str, Any]]] = {}
    for class_id, spec in classes.items():
        if not isinstance(spec, dict):
            continue
        patterns = [(str(head), _head_pattern(str(head))) for head in spec.get('members') or [] if str(head).strip()]
        hits: list[dict[str, Any]] = []
        for number, text in steps:
            matched = sorted({head for head, pattern in patterns if pattern.search(text)}, key=lambda value: (-len(value.split()), value))
            if matched:
                hits.append({'step': number, 'heads': matched})
        out[str(class_id)] = hits
    return out

def _data_path(path: str) -> Any:
    from cex_core.engine.case_compiler.domain_grammar import load_grammar
    value: Any = load_grammar()
    for segment in str(path or '').split('.'):
        if not segment or not isinstance(value, dict) or segment not in value:
            return None
        value = value[segment]
    return value

def _word_set(path: str) -> frozenset[str]:
    value = _data_path(path)
    words = value.get('words') if isinstance(value, dict) else None
    return frozenset((_semantic_text(item) for item in words or [] if _semantic_text(item)))

def _algorithm_classes(case: Mapping[str, Any]) -> frozenset[str]:
    from cex_core.engine.case_compiler.domain_grammar import load_grammar
    grammar = load_grammar()
    classes = grammar.get('algorithm_classes') or {}
    text = '\n'.join([str(case.get('title') or '')] + [value for _number, value in _step_texts(case)] + [str(item.get('text') or '') for item in case.get('expectations_by_step') or [] if isinstance(item, dict)])
    tokens = {match.group(1).casefold() for match in _ASCII_TOKEN_RE.finditer(text)}
    return frozenset((str(class_id) for class_id, spec in classes.items() if isinstance(spec, dict) and tokens.intersection((str(value).casefold() for value in spec.get('methods') or []))))

def _resource_profile(resource: Any) -> tuple[frozenset[str], dict[str, Any]]:
    if isinstance(resource, str):
        return (frozenset({resource.casefold()}), {})
    if isinstance(resource, list):
        return (frozenset((str(item).casefold() for item in resource if isinstance(item, str) and item)), {})
    if isinstance(resource, dict):
        markers = {str(resource.get(key) or '').casefold() for key in ('kind', 'resource', 'marker') if str(resource.get(key) or '').strip()}
        return (frozenset(markers), dict(resource))
    return (frozenset(), {})

def _operator_criterion(operator: str) -> str | None:
    return {'not_found': 'absence', 'found_times': 'count', 'found': 'content_match', 'abs_found': 'content_match'}.get(str(operator or '').strip())

def _stress_triage(*, expectation: Mapping[str, Any], resource_profile: Mapping[str, Any], prior_match: Mapping[str, Any] | None) -> tuple[str, str | None, dict[str, Any]]:
    if prior_match and prior_match.get('criterion_type'):
        return ('l_expressible', str(prior_match['criterion_type']), {'delegated_rule_id': str(prior_match.get('rule_id') or '')})
    assertion = expectation.get('assertion')
    if isinstance(assertion, dict):
        criterion_type = _operator_criterion(str(assertion.get('operator') or ''))
        if criterion_type:
            return ('l_expressible', criterion_type, {'operator': str(assertion.get('operator') or '')})
    distribution = resource_profile.get('distribution')
    if isinstance(distribution, dict):
        from cex_core.engine.case_compiler.distribution_assertion import validate_distribution
        error = validate_distribution(distribution.get('total'), distribution.get('buckets'))
        if error is None:
            return ('l_expressible', 'distribution', {'distribution': distribution})
        if '容差' in error or '上界' in error:
            return ('numeric_tolerance_out_of_range', None, {'reason': error})
    return ('manual_recommended', None, {})

def _rule_match(rule: Mapping[str, Any], *, case: Mapping[str, Any], expectation: Mapping[str, Any], object_occurrences: Mapping[str, list[dict[str, Any]]], algorithm_classes: frozenset[str], resource_markers: frozenset[str], resource_profile: Mapping[str, Any], claim_step: int | None=None) -> dict[str, Any] | None:
    predicate = rule.get('predicate')
    output = rule.get('output')
    if not isinstance(predicate, dict) or not isinstance(output, dict):
        return None
    semantic = _semantic_text(expectation.get('text'))
    patterns = predicate.get('claim_patterns')
    pattern_matched = False
    if isinstance(patterns, list) and patterns:
        try:
            pattern_matched = any((re.search(str(pattern), semantic) for pattern in patterns))
        except re.error:
            return None
        if not pattern_matched:
            return None
    if 'object_class_any' in predicate:
        required = [str(value) for value in predicate.get('object_class_any') or []]
        excluded = [str(value) for value in predicate.get('object_class_none') or []]
        if not required or not any((object_occurrences.get(name) for name in required)):
            return None
        if any((object_occurrences.get(name) for name in excluded)):
            return None
        if claim_step is None or not any((int(hit.get('step') or 0) < claim_step for name in required for hit in object_occurrences.get(name) or [])):
            return None
        words = _word_set(str(predicate.get('judgment_word_set') or ''))
        if semantic not in words:
            return None
    if predicate.get('algorithm_class'):
        if str(predicate['algorithm_class']) not in algorithm_classes:
            return None
        patterns = predicate.get('claim_patterns')
        if not isinstance(patterns, list) or not patterns:
            return None
        match = next((re.search(str(pattern), semantic) for pattern in patterns if re.search(str(pattern), semantic)), None)
        if match is None:
            return None
        groups = match.groupdict()
        n_pool = None
        request = str(groups.get('request') or '')
        member = str(groups.get('member') or '')
        if request.isdigit() and member.isdigit() and (request == member):
            n_pool = int(member)
        return {'criterion_type': str(output.get('criterion_type') or ''), 'rule_id': str(rule.get('rule_id') or ''), 'mode': str(output.get('mode') or ''), 'min_requests': n_pool, 'min_requests_formula': str(output.get('min_requests_formula') or '')}
    if predicate.get('resource_marker'):
        marker = str(predicate.get('resource_marker') or '').casefold()
        if marker not in resource_markers:
            return None
        triage, criterion_type, details = _stress_triage(expectation=expectation, resource_profile=resource_profile, prior_match=None)
        return {'criterion_type': criterion_type, 'rule_id': str(rule.get('rule_id') or ''), 'mode': str(output.get('mode') or 'triage'), 'triage': triage, 'triage_details': details}
    if not any((key in predicate for key in ('object_class_any', 'algorithm_class', 'resource_marker', 'claim_patterns'))):
        return None
    return {'criterion_type': str(output.get('criterion_type') or ''), 'rule_id': str(rule.get('rule_id') or ''), 'mode': str(output.get('mode') or 'direct'), **{str(key): value for key, value in output.items() if key not in {'criterion_type', 'mode'}}}

def _proposal_match(proposal: Mapping[str, Any], semantic: str) -> bool:
    predicate = proposal.get('predicate')
    if not isinstance(predicate, dict):
        return False
    patterns = predicate.get('claim_patterns')
    return isinstance(patterns, list) and any((re.search(str(pattern), semantic) for pattern in patterns))

def _shape_key(*, semantic: str, object_classes: list[str], algorithm_classes: frozenset[str], resource_markers: frozenset[str], version_family: str) -> str:
    return _canonical_sha256({'schema': 'ist.criterion-shape-key', 'semantic': semantic, 'object_classes': sorted(object_classes), 'algorithm_classes': sorted(algorithm_classes), 'resource_markers': sorted(resource_markers), 'version_family': str(version_family or '')})

def normalize_case_expectations(*, case: Mapping[str, Any], expectations: list[dict[str, Any]], mindmap_text: str, resource: Any=None, version_family: str='', projection: Mapping[str, Any] | None=None, author_rules: Mapping[tuple[str, str], Mapping[str, Any]] | None=None, manual_version: str | None=None, requirement_sources: Mapping[str, RequirementSource] | None=None) -> NormalizationResult:
    from cex_core.engine.case_compiler.mindmap_contract_projector import ground_source_span
    projection = dict(projection or load_projection())
    version_family = str(version_family or (projection.get('identity') or {}).get('version_family') or '')
    resolved_manual_version = str(manual_version or '')
    if not resolved_manual_version:
        from cex_core.engine.case_compiler.criterion_author_rules import resolve_compile_manual_version
        resolved_manual_version = resolve_compile_manual_version()
    type_ids = _criterion_type_ids(projection)
    type_labels = {str(row.get('criterion_type') or ''): str(row.get('label_zh') or '') for row in projection.get('criterion_types') or [] if isinstance(row, dict)}
    object_occurrences = _object_occurrences(case, projection)
    present_classes = sorted((class_id for class_id, hits in object_occurrences.items() if hits))
    algorithms = _algorithm_classes(case)
    resource_markers, resource_profile = _resource_profile(resource)
    rules = [row for row in projection.get('rules') or [] if isinstance(row, dict)]
    if author_rules is None:
        from cex_core.engine.case_compiler.criterion_author_rules import load_author_rules
        author_rules = load_author_rules(manual_version=resolved_manual_version)
    out: list[dict[str, Any]] = []
    disclosures: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for index, raw_expectation in enumerate(expectations):
        expectation = dict(raw_expectation)
        claim = expectation.get('author_claim') or expectation.get('defect_spec_claim') or expectation.get('assertion') or {}
        expectation_id = str(claim.get('expectation_id') or '') if isinstance(claim, dict) else ''
        semantic_key = str(claim.get('semantic_key') or '') if isinstance(claim, dict) else ''
        semantic = _semantic_text(expectation.get('text'))
        span = ground_source_span(str(expectation.get('text') or ''), str(mindmap_text or ''), origin=str(claim.get('origin') or '') if isinstance(claim, dict) else '')
        shape_key = _shape_key(semantic=semantic, object_classes=present_classes, algorithm_classes=algorithms, resource_markers=resource_markers, version_family=version_family)
        claim_step, claim_step_cause = _claim_step_binding(claim, autoid=str(case.get('autoid') or ''), mindmap_text=str(mindmap_text or ''), source_text=str(expectation.get('text') or '')) if isinstance(claim, dict) else (None, AUTHORED_STEP_CAUSE_ORIGIN)
        matched: dict[str, Any] | None = None
        matched_rule: dict[str, Any] | None = None
        if span is not None:
            base_match: dict[str, Any] | None = None
            base_rule: dict[str, Any] | None = None
            stress_rule: dict[str, Any] | None = None
            for rule in rules:
                predicate = rule.get('predicate') if isinstance(rule, dict) else {}
                if isinstance(predicate, dict) and predicate.get('resource_marker'):
                    marker = str(predicate.get('resource_marker') or '').casefold()
                    if marker in resource_markers:
                        stress_rule = rule
                    continue
                candidate = _rule_match(rule, case=case, expectation=expectation, object_occurrences=object_occurrences, algorithm_classes=algorithms, resource_markers=resource_markers, resource_profile=resource_profile, claim_step=claim_step)
                if candidate is not None:
                    base_match = candidate
                    base_rule = rule
                    break
            if stress_rule is not None:
                triage, stress_type, details = _stress_triage(expectation=expectation, resource_profile=resource_profile, prior_match=base_match)
                matched = {'criterion_type': stress_type, 'rule_id': str(stress_rule.get('rule_id') or ''), 'mode': 'triage', 'triage': triage, 'triage_details': details}
                matched_rule = stress_rule
            else:
                matched = base_match
                matched_rule = base_rule
        author_record = author_rules.get((shape_key, resolved_manual_version))
        veto_binding: dict[str, Any] | None = None
        if matched is None and isinstance(author_record, Mapping):
            author_output = author_record.get('output')
            author_identity = author_record.get('identity')
            author_type = str(author_output.get('criterion_type') or '') if isinstance(author_output, Mapping) else ''
            if author_type in type_ids and isinstance(author_identity, Mapping):
                matched = {'criterion_type': author_type, 'rule_id': str(author_record.get('rule_id') or ''), 'mode': str(author_output.get('mode') or 'direct')}
                matched_rule = {'identity': dict(author_identity)}
                from cex_core.engine.case_compiler.criterion_author_rules import VETO_ANSWER, build_criterion_veto_question
                veto_question = build_criterion_veto_question(author_record)
                veto_binding = {'answer_key': str(veto_question.get('_answer_key') or ''), 'answer': VETO_ANSWER, 'rule_sha256': str(author_record.get('rule_sha256') or '')}
        status = 'matched' if matched and matched.get('criterion_type') else 'unmatched'
        if matched and matched.get('triage') == 'manual_recommended':
            status = 'manual_recommended'
        if matched and matched.get('triage') == 'numeric_tolerance_out_of_range':
            status = 'numeric_tolerance_out_of_range'
        criterion_type = str((matched or {}).get('criterion_type') or '') or None
        if criterion_type is not None and criterion_type not in type_ids:
            raise CriterionNormalizationError('matched criterion type is outside catalogue')
        normalized_claim: dict[str, Any] = {'schema': NORMALIZED_CLAIM_SCHEMA, 'expectation_id': expectation_id, 'semantic_key': semantic_key, 'original_text': str(expectation.get('text') or ''), 'original_claim_sha256': str(claim.get('claim_sha256') or '') if isinstance(claim, dict) else '', 'source_span': span, 'shape_key': shape_key, 'version_family': str(version_family or ''), 'algorithm_classes': sorted(algorithms), 'authored_step': claim_step, 'authored_step_cause': claim_step_cause, 'status': status, 'criterion_type': criterion_type, 'criterion_label_zh': type_labels.get(criterion_type or '') or None, 'rule_id': str((matched or {}).get('rule_id') or '') or None, 'rule_identity': dict(matched_rule.get('identity') or {}) if isinstance(matched_rule, dict) else None, 'evidence_chain': dict((matched_rule.get('identity') or {}).get('evidence_chain') or {}) if isinstance(matched_rule, dict) and isinstance(matched_rule.get('identity'), Mapping) and isinstance((matched_rule.get('identity') or {}).get('evidence_chain'), Mapping) else None, 'author_veto': veto_binding, 'anchor_citation_corrected': bool(author_record.get('anchor_citation_corrected')) if status == 'matched' and isinstance(author_record, Mapping) else False, 'supersede_cause': str(author_record.get('supersede_cause') or '') or None if status == 'matched' and isinstance(author_record, Mapping) else None, 'mode': str((matched or {}).get('mode') or '') or None, 'disclosure': str(author_record.get('disclosure') or '') if status == 'matched' and isinstance(author_record, Mapping) else '作者原文保持不变；带身份规则只给出判据类型，编写期不得另行改读。' if status == 'matched' else '作者原文保持不变；静态规则未命中，等待引擎内部判据裁定。', 'catalog_sha256': str(projection.get('projection_sha256') or ''), **{key: value for key, value in (matched or {}).items() if key not in {'criterion_type', 'rule_id', 'mode'}}}
        normalized_claim['required_carriers'] = derive_required_carriers(expectation, normalized_claim, requirement_sources=requirement_sources)
        expectation['normalized_claim'] = normalized_claim
        expectation['text_anchor'] = with_authored_step_anchor(expectation.get('text_anchor'), claim_step)
        out.append(expectation)
        disclosure = {'autoid': str(case.get('autoid') or ''), 'expectation_id': expectation_id, 'shape_key': shape_key, 'version_family': str(version_family or ''), 'algorithm_classes': sorted(algorithms), 'status': status, 'criterion_type': criterion_type, 'rule_id': normalized_claim['rule_id'], 'authored_step': claim_step, 'authored_step_cause': claim_step_cause, 'source_span': span, 'evidence_chain': normalized_claim['evidence_chain'], 'message': normalized_claim['disclosure']}
        disclosures.append(disclosure)
        if status != 'matched':
            pending.append({**disclosure, 'original_text': str(expectation.get('text') or '')})
    return NormalizationResult(tuple(out), tuple(disclosures), tuple(pending))
