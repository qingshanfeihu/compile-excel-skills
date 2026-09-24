# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/mindmap_contract_projector.py（sha256 e53fef3f7b843415）。不在这里手改。
from __future__ import annotations
import copy
import json
import os
import re
import stat
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping
from cex_core.engine.common.schema_identity import accepts_schema
from cex_core.engine.case_compiler._sealed_io import CONTRACT_CARD_MAX_BYTES, open_directory_nofollow, read_regular_at_nofollow, read_regular_nofollow, scan_json_budget, sha256_bytes, stat_regular_nofollow, validate_json_budget
from cex_core.engine.case_compiler.contract_entry import ContractError, build_validation_cards, build_warning_panel, encode_json_atomic, normalize_contract, write_json_atomic
from cex_core.engine.engine_managed_outputs import MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME
_CARD_BUCKETS = frozenset({'exp_recipe', 'step_recipe'})
_SCENARIO2_REASON = 'missing_case_description_steps_or_expectation'
_SCENARIO2_SOURCE_FIELDS = ('intent', 'steps', 'expectation')
_SOURCE_STATUSES = frozenset({'complete', 'incomplete'})
_TYPED_ASSERTION_STATUSES = frozenset({'ready', 'pending'})
_SHA256_RE = re.compile('^[0-9a-f]{64}$')
_CONSISTENCY_DRAFT_SCHEMA = 'ist.consistency-verdict'
_CONSISTENCY_MATERIAL_SCHEMA = 'ist.consistency-verdict-material'
_CONSISTENCY_MATERIAL_KEYS = frozenset({'schema', 'autoid', 'verdict', 'spec_quote', 'case_quote', 'spec_locator', 'case_locator', 'incompatibility', 'premises', 'spec_clauses'})
DISCLOSURE_LOAD_SCHEMA = 'ist.mindmap-disclosure-load'
_SCENARIO1_DISPOSITIONS = frozenset({'contradicts', 'consistent', 'not_applicable'})
RECOMPOSE_CONSISTENCY_SCHEMA = 'ist.recompose-consistency'
RECOMPOSE_CONSISTENCY_VERDICTS = frozenset({'consistent', 'mutually_exclusive', 'underdetermined'})
AUTHORED_CONFLICT_KEY = 'authored_conflict'
AUTHORED_CONFLICT_SURFACE_KEYS = frozenset({'locator', 'quote'})
AUTHORED_CONFLICT_MIN_SURFACES = 2
AUTHORED_CONFLICT_MAX_SURFACES = 8
_RECOMPOSE_CONSISTENCY_KEYS = frozenset({'schema', 'verdict', 'spec_quote', 'case_quote', 'spec_locator', 'case_locator', 'incompatibility', 'premises', 'spec_clauses', 'missing_preconditions', AUTHORED_CONFLICT_KEY})
_FIELD_VERBAL_ZH = {'expectation': '预期', 'intent': '描述', 'adaptation_notes': '描述', 'steps': '步骤', 'verification_method': '验证方法', 'consistency': '和规格是否一致'}
_CRITERION_VERBAL_ZH = {'reachability': '能不能连上', 'status_value': '状态对不对', 'content_match': '内容对不对', 'absence': '没有出现', 'count': '出现几次', 'distribution': '怎么分布', 'before_after': '改前改后对不对', '可达性': '能不能连上', '状态值': '状态对不对', '内容匹配': '内容对不对', '不存在性': '没有出现', '计数': '出现几次', '分布': '怎么分布', '前后对照': '改前改后对不对'}

def criterion_verbal_zh(criterion_type: str) -> str:
    key = str(criterion_type or '').strip()
    return _CRITERION_VERBAL_ZH.get(key, key)
_SUPERSEDE_CAUSE_VERBAL_ZH = {'author_veto': '上一代判据经你否决后重裁', 'manual_section_changed': '手册这一节内容已更新，上一代判据已按新手册重裁', 'prior_not_verifiable': '上一代判据没有可核验的手册指纹，证不出手册未变，已按当前手册重裁'}

def supersede_cause_verbal_zh(cause: Any) -> str:
    return _SUPERSEDE_CAUSE_VERBAL_ZH.get(str(cause or '').strip(), '')

def _field_verbal_zh(field: str) -> str:
    raw = str(field or '').strip()
    base = re.sub('\\[\\d+\\]$', '', raw)
    return _FIELD_VERBAL_ZH.get(base, raw)

def _verbatim_quarantine_error(fields: str) -> str:
    names = [part.strip() for part in str(fields or '').split('、') if part.strip()]
    if not names:
        names = [str(fields or '').strip() or '字段']
    if len(names) == 1:
        field = names[0]
        verbal = _field_verbal_zh(field)
        rewritten = re.sub('\\[\\d+\\]$', '', field) in {'adaptation_notes', 'intent'}
        verb = '改写的' if rewritten else '写的'
        return f'重组{verb}{verbal}（{field}）和人工脑图原文对不上，本轮退回，不编写'
    verbal_joined = '、'.join((_field_verbal_zh(name) for name in names))
    field_joined = '、'.join(names)
    return f'重组写的{verbal_joined}（{field_joined}）和人工脑图原文对不上，本轮退回，不编写'

def _verbatim_quarantine_disclosure(fields: str) -> str:
    shown = str(fields or '').strip() or '字段'
    return f'{shown} 和你脑图对不上，是重组没对齐；本轮不出卡、不编写，再跑会重新重组，你的原文不受影响'
_STAMP_FAILURE_GRAMMAR: tuple[tuple[str, str], ...] = (('premises', 'consistency_premise_(\\d+)_([a-z0-9_]+)'), ('authored_conflict.surfaces', 'consistency_authored_conflict_surface_(\\d+)_([a-z0-9_]+)'))
_STAMP_FAILURE_PATTERNS = tuple(((collection, re.compile(pattern)) for collection, pattern in _STAMP_FAILURE_GRAMMAR))
STAMP_FAILURE_CODE_SEARCH = re.compile('(consistency_premise_\\d+_[a-z0-9_]+|consistency_authored_conflict_[a-z0-9_]+)')

class ConsistencyStampFailure(str):
    """盖章失败码，**连同它编进码名里的那两个字段一起传**。

    `consistency_premise_{i}_{problem}` 与
    `consistency_authored_conflict_surface_{i}_{problem}` 此前只有码名一个载体，
    (序号, 问题) 被四处各自写一份正则或前缀切片解回去——同一份文法四份实现，
    改一处码名就得记得改另外四处。

    码本身还是同一个字符串：比较、`in`、JSON 落盘、拼进文案全部逐字不变；
    序号与问题直接读 `.index` / `.problem`，生产路径一次都不再解码。
    """
    collection: str
    index: int
    problem: str

    def __new__(cls, code: str, *, collection: str='', index: int=-1, problem: str='') -> 'ConsistencyStampFailure':
        obj = super().__new__(cls, code)
        obj.collection = collection
        obj.index = index
        obj.problem = problem
        return obj

    @classmethod
    def of(cls, value: object) -> 'ConsistencyStampFailure':
        """已带字段的原样返回；裸串按文法解一次——全仓唯一的解码点。

        裸串只从外部进来（直调本函数的测试、经 JSON 落盘再读回的码）。生产路径上
        产码点直接给带字段的对象，走不到解析这一支。
        """
        if isinstance(value, cls):
            return value
        text = str(value or '')
        for collection, pattern in _STAMP_FAILURE_PATTERNS:
            match = pattern.fullmatch(text)
            if match is not None:
                return cls(text, collection=collection, index=int(match.group(1)), problem=match.group(2))
        return cls(text)

def premise_stamp_failure(index: int, problem: str) -> ConsistencyStampFailure:
    """`premises[index]` 的盖章失败码。"""
    return ConsistencyStampFailure(f'consistency_premise_{index}_{problem}', collection='premises', index=index, problem=problem)

def conflict_surface_stamp_failure(index: int, problem: str) -> ConsistencyStampFailure:
    """`authored_conflict.surfaces[index]` 的盖章失败码。"""
    return ConsistencyStampFailure(f'consistency_authored_conflict_surface_{index}_{problem}', collection='authored_conflict.surfaces', index=index, problem=problem)

def _invalid_contract_user_text(why: str) -> tuple[str, str]:
    text = str(why or '').strip()
    code_match = STAMP_FAILURE_CODE_SEARCH.search(text)
    code = code_match.group(1) if code_match else ''
    if 'locator_unresolved' in text or '出处解不出' in text:
        token = code or text
        return (f'机器稿作废：重组写「和规格是否一致」时，出处在本批绑定的源里解不出来（{token}）', f'一致性出处解不出（{token}），这张机器稿作废，不能当成「你的人工脑图没写完」')
    if 'quote_drift' in text or 'text_drift' in text or '盖章不一致' in text:
        token = code or text
        return (f'机器稿作废：重组写「和规格是否一致」时，调用方给的引文与引擎按出处解出的字节不一致（{token}）', f'一致性引文与引擎盖章不一致（{token}），这张机器稿作废，不能当成「你的人工脑图没写完」')
    if 'outside_closure' in text or '出处闭包' in text:
        token = code or text
        return (f'机器稿作废：重组写「和规格是否一致」时，引文与规格书/脑图里的整句原文不一致（{token}）', f'一致性那句引文不是出处里的整句（{token}），这张机器稿作废，不能当成「你的人工脑图没写完」')
    return (f'机器稿作废：{text}', f'{text}，这张机器稿作废，不能当成「你的人工脑图没写完」')

def _criterion_disclosure_message(normalized_claim: dict[str, Any]) -> str:
    raw_type = str(normalized_claim.get('criterion_label_zh') or normalized_claim.get('criterion_type') or '')
    verbal = criterion_verbal_zh(raw_type) if raw_type else '还没定'
    status = str(normalized_claim.get('status') or 'unmatched')
    head = f'人工脑图预期原文不动；归类为「{verbal}」'
    if status != 'matched':
        head += '（类型还没定下来）'
    parts = [head]
    evidence_chain = normalized_claim.get('evidence_chain')
    manuals: list[str] = []
    trees: list[str] = []
    if isinstance(evidence_chain, dict):
        manuals = [f"{row.get('source_path')}:{row.get('line_start') or int((row.get('source_span') or {}).get('start') or 0)}" for row in evidence_chain.get('manual_anchors') or [] if isinstance(row, dict) and row.get('source_path')]
        trees = [str(row.get('context_id') or '') for row in evidence_chain.get('tree_context') or [] if isinstance(row, dict) and row.get('context_id')]
        if manuals and (not normalized_claim.get('anchor_citation_corrected')):
            parts.append(f'依据手册 {manuals[0]}' + (f' 等 {len(manuals)} 处引用' if len(manuals) > 1 else ''))
        if trees:
            parts.append(f'对照树节点 {trees[0]}' if len(trees) == 1 else f'对照树节点共 {len(trees)} 条引用')
        if len(manuals) > 1 or len(trees) > 1:
            parts.append('完整引用随本案判据记录保留')
    identity = normalized_claim.get('rule_identity')
    if not manuals and (not trees) and isinstance(identity, dict) and (identity.get('kind') == 'user_ruling'):
        anchor = identity.get('manual_method_anchor') or {}
        parts.append(f"依据你 {identity.get('ruled_at')} 的裁定；手册 {anchor.get('source_path')}:{anchor.get('line_start')}")
    supersede = supersede_cause_verbal_zh(normalized_claim.get('supersede_cause'))
    if supersede:
        parts.append(supersede)
    veto = normalized_claim.get('author_veto')
    identity = normalized_claim.get('rule_identity')
    if isinstance(veto, dict) and veto.get('answer_key') and isinstance(identity, dict) and (identity.get('adjudicator') == 'criterion-adjudicator'):
        parts.append(f"这条归类是引擎裁定的，与你写的不符就可以翻掉：答「{veto.get('answer')}」（键 {str(veto['answer_key'])[:16]}），下次同类编译重新裁定")
    return '；'.join(parts)

def _clause_shape_failure_one(clause: object) -> str:
    if not isinstance(clause, dict) or set(clause) != {'text', 'disposition', 'reason'}:
        return 'scenario1_clauses_invalid'
    text = clause.get('text')
    disposition = clause.get('disposition')
    reason = clause.get('reason')
    if not isinstance(text, str) or not text.strip() or disposition not in _SCENARIO1_DISPOSITIONS or (not isinstance(reason, str)):
        return 'scenario1_clauses_invalid'
    if disposition == 'not_applicable' and (not reason.strip()):
        return 'scenario1_clause_reason_missing'
    return ''

def _clause_gap_locus(spec_quote: str, clauses: list) -> tuple[str, int, tuple[int, int] | None]:
    normalized_quote = _norm_ws(spec_quote)
    fragments = [re.sub('\\s+', ' ', clause['text']) for clause in clauses]
    fragments[0] = fragments[0].lstrip(' ')
    fragments[-1] = fragments[-1].rstrip(' ')
    cursor = 0
    for ordinal, fragment in enumerate(fragments):
        if ordinal and fragments[ordinal - 1].endswith(' '):
            fragment = fragment.lstrip(' ')
        index = normalized_quote.find(fragment, cursor)
        if index < 0:
            return ('scenario1_clause_outside_quote', ordinal + 1, None)
        if index > cursor:
            return ('scenario1_clause_gap', ordinal + 1, (cursor + 1, index))
        cursor = index + len(fragment)
    if cursor < len(normalized_quote):
        return ('scenario1_clause_gap', len(clauses), (cursor + 1, len(normalized_quote)))
    return ('', 0, None)

def _clause_gap_failure(spec_quote: str, clauses: list) -> str:
    return _clause_gap_locus(spec_quote, clauses)[0]

def clause_coverage_locus(spec_quote: str, clauses: object) -> tuple[str, int, tuple[int, int] | None]:
    """生产判据与工具反馈共用的切片复核，位置为标准化引文的 1 起始闭区间。"""
    if not isinstance(clauses, list) or not clauses or any((not isinstance(item, dict) for item in clauses)):
        return ('scenario1_clauses_invalid', 0, None)
    for index, clause in enumerate(clauses):
        failure = _clause_shape_failure_one(clause)
        if failure:
            return (failure, index + 1, None)
    return _clause_gap_locus(spec_quote, clauses)

def clause_coverage_failure(spec_quote: str, clauses: object) -> str:
    return clause_coverage_locus(spec_quote, clauses)[0]

def _authored_conflict_shape_report(value: object) -> tuple[str, str]:
    """案内互斥声明的形状走查：返回（失败码, 指到具体字段的原因）。

    这一格答的是**案自己跟自己**的问题：作者的两处表面（标题/分组、某一步、某条
    预期）能不能同时是本案要验的东西。`verdict` 答的是案跟规格的问题，两个问题正交，
    所以这是 `consistency` 上一个可选子结构，不是 `verdict` 闭集里的第四个值。

    引用的是**作者两处表面**的逐字引文而不是 spec ——`mutually_exclusive` 那条路要求
    `spec_clauses` 平铺 `spec_quote`，案内互斥在那个表面上结构性写不出来，这正是它
    此前只能写成散文 `proposal` 的原因。

    码前缀统一 `consistency_authored_conflict_`，八条形态各自一句原因（只回码等于
    「只否定不指路」，模型读不出自己差哪一个字段）。
    """
    if value is None:
        return ('', '')
    if not isinstance(value, dict):
        return ('consistency_authored_conflict_invalid', f'{AUTHORED_CONFLICT_KEY} is a {type(value).__name__}; when present it is an object with exactly surfaces and incompatibility')
    extra = sorted(set(value) - {'surfaces', 'incompatibility'})
    if extra:
        return ('consistency_authored_conflict_invalid', f'{AUTHORED_CONFLICT_KEY} carries key(s) outside the legal set: ' + ', '.join(extra) + '; the legal keys are incompatibility, surfaces')
    incompatibility = value.get('incompatibility')
    if not isinstance(incompatibility, str) or not incompatibility.strip():
        return ('consistency_authored_conflict_incompatibility_missing', f'{AUTHORED_CONFLICT_KEY}.incompatibility is {incompatibility!r}; it is one sentence saying why the cited authored surfaces cannot both be what this case verifies')
    surfaces = value.get('surfaces')
    if not isinstance(surfaces, list):
        return ('consistency_authored_conflict_surfaces_invalid', f'{AUTHORED_CONFLICT_KEY}.surfaces is a {type(surfaces).__name__}; it is an array of {{locator, quote}} objects')
    if len(surfaces) < AUTHORED_CONFLICT_MIN_SURFACES:
        return ('consistency_authored_conflict_surfaces_insufficient', f'{AUTHORED_CONFLICT_KEY}.surfaces cites {len(surfaces)} authored surface(s); a contradiction inside one case needs at least {AUTHORED_CONFLICT_MIN_SURFACES} distinct authored locators. One surface alone is a missing definition, not a contradiction')
    if len(surfaces) > AUTHORED_CONFLICT_MAX_SURFACES:
        return ('consistency_authored_conflict_surfaces_invalid', f'{AUTHORED_CONFLICT_KEY}.surfaces cites {len(surfaces)} authored surfaces; at most {AUTHORED_CONFLICT_MAX_SURFACES} are judged')
    seen: list[str] = []
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict) or set(surface) - AUTHORED_CONFLICT_SURFACE_KEYS or 'locator' not in surface:
            return (conflict_surface_stamp_failure(index, 'invalid'), f'{AUTHORED_CONFLICT_KEY}.surfaces[{index}] is exactly {{locator, quote}}, where quote may be omitted because the engine stamps it from the locator; got ' + (', '.join(sorted((str(key)[:80] for key in surface))) if isinstance(surface, dict) else f'a {type(surface).__name__}'))
        locator = surface.get('locator')
        if not isinstance(locator, str) or not locator.strip():
            return (conflict_surface_stamp_failure(index, 'invalid'), f'{AUTHORED_CONFLICT_KEY}.surfaces[{index}].locator is {locator!r}; it names one authored surface of this case (title, step:<n>, expectation:<label> or orphan_note:<n>)')
        quote = surface.get('quote')
        if quote is not None and (not isinstance(quote, str)):
            return (conflict_surface_stamp_failure(index, 'invalid'), f'{AUTHORED_CONFLICT_KEY}.surfaces[{index}].quote is a {type(quote).__name__}; when present it is a string and the engine overwrites it with the bytes its locator resolves to')
        if locator.strip() in seen:
            return ('consistency_authored_conflict_surfaces_not_distinct', f'{AUTHORED_CONFLICT_KEY}.surfaces names {locator.strip()!r} twice; a contradiction needs two different authored surfaces, so the locators are pairwise distinct')
        seen.append(locator.strip())
    return ('', '')

def recompose_consistency_shape_report(value: object) -> tuple[str, str]:
    """返回（失败码, 指到具体字段的原因）。

    码是既有闭集，八条形态违例共用 `consistency_conclusion_invalid` 一个码；只把码
    回给模型等于「只否定不指路」——它读不出自己差哪一个字段，只能整卡重发。所以原因
    在同一趟走查里一并算出，供拒绝文案用；判定仍由这一趟负责，没有第二份走查可漂移。
    原因串面向模型，用英文。
    """
    if value is None:
        return ('', '')
    if not isinstance(value, dict):
        return ('consistency_conclusion_invalid', f'the consistency field is a {type(value).__name__}, not an {RECOMPOSE_CONSISTENCY_SCHEMA} object')
    extra = sorted(set(value) - _RECOMPOSE_CONSISTENCY_KEYS)
    if extra:
        return ('consistency_conclusion_invalid', 'it carries key(s) outside the legal set: ' + ', '.join(extra) + '; the legal keys are ' + ', '.join(sorted(_RECOMPOSE_CONSISTENCY_KEYS)))
    if value.get('schema') != RECOMPOSE_CONSISTENCY_SCHEMA:
        return ('consistency_conclusion_invalid', f"its schema key is {value.get('schema')!r}; it must be present and exactly {RECOMPOSE_CONSISTENCY_SCHEMA!r}")
    verdict = value.get('verdict')
    if verdict not in RECOMPOSE_CONSISTENCY_VERDICTS:
        return ('consistency_conclusion_invalid', f'its verdict is {verdict!r}; it must be one of ' + ', '.join(sorted(RECOMPOSE_CONSISTENCY_VERDICTS)))
    for field in ('spec_locator', 'case_locator'):
        if not isinstance(value.get(field), str):
            return ('consistency_conclusion_invalid', f'{field} is {value.get(field)!r}; it must be present and a string')
    for field in ('spec_quote', 'case_quote'):
        if field in value and (not isinstance(value.get(field), str)):
            return ('consistency_conclusion_invalid', f'{field} is {value.get(field)!r}; when present it must be a string')
    missing = value.get('missing_preconditions') or []
    if not isinstance(missing, list) or any((not isinstance(item, str) or not item.strip() for item in missing)):
        return ('consistency_conclusion_invalid', 'missing_preconditions must be a list of non-empty strings')
    conflict_failure, conflict_reason = _authored_conflict_shape_report(value.get(AUTHORED_CONFLICT_KEY))
    if conflict_failure:
        return (conflict_failure, conflict_reason)
    if verdict == 'underdetermined':
        if not missing:
            return ('consistency_underdetermined_without_preconditions', 'the underdetermined verdict requires at least one entry in missing_preconditions')
        return ('', '')
    if missing:
        return ('consistency_conclusion_invalid', f'missing_preconditions is only legal on the underdetermined verdict, and this conclusion states {verdict!r}')
    if verdict == 'mutually_exclusive':
        clause_failure = clause_coverage_failure(str(value.get('spec_quote') or ''), value.get('spec_clauses'))
        if clause_failure:
            return (clause_failure, f'spec_clauses does not tile spec_quote ({clause_failure})')
        return ('', '')
    return ('', '')

def recompose_consistency_failure(value: object) -> str:
    return recompose_consistency_shape_report(value)[0]

def _scenario1_clause_failure(spec_quote: str, clauses: object) -> str:
    if not isinstance(clauses, list) or not clauses or any((not isinstance(item, dict) for item in clauses)):
        return 'scenario1_clauses_invalid'
    seen_contradiction = False
    for clause in clauses:
        failure = _clause_shape_failure_one(clause)
        if failure:
            return failure
        disposition = clause.get('disposition')
        if disposition == 'consistent':
            return 'scenario1_clause_consistent_branch'
        if disposition == 'contradicts':
            seen_contradiction = True
    if not seen_contradiction:
        return 'scenario1_clause_no_contradiction'
    return _clause_gap_failure(spec_quote, clauses)
_VALUE_GROUNDING = '作者侧原文值，环境绑定在编写期查证完成'
_LOCATOR_TOKEN = '[A-Za-z0-9_-]+'
_ORIGIN_STEP_RE = re.compile(f'^step:({_LOCATOR_TOKEN})$')
_ORIGIN_EXPECT_RE = re.compile(f'^expectation:({_LOCATOR_TOKEN})$')
_ORIGIN_SPEC_RE = re.compile('^spec:([^/\\\\:]+):(\\d+(?:-\\d+)?)$')
_ORIGIN_DEFECT_SPEC_RE = re.compile(f'^defect:({_LOCATOR_TOKEN}):({_LOCATOR_TOKEN}):(title|description)$', re.IGNORECASE)
_MACHINE_MINDMAP_MAX_BYTES = 16 * 1024 * 1024
_PROJECTION_JSON_MAX_BYTES = 4 * 1024 * 1024
_PROJECTION_JSON_MAX_TOKENS = 100000
_PROJECTION_JSON_MAX_DEPTH = 128
_DISCLOSURE_REF_FIELDS = ('evidence_chain', 'rule_identity')
_DISCLOSURE_REF_KEYS = frozenset({'autoid', 'expectation_id'})
DISCLOSURE_STORAGE_CONTRACT_REFS = 'contract_refs'
DISCLOSURE_LOAD_REASONS = frozenset({'bytes_over_limit', 'structure_budget_exceeded', 'json_invalid', 'digest_mismatch', 'ref_invalid', 'sealed_read_failed'})
_MACHINE_MINDMAP_SCHEMA = 'ist.machine-mindmap'
_MACHINE_MINDMAP_REQUIRED_KEYS = frozenset({'schema', 'source', 'case_count', 'cases'})
_MACHINE_MINDMAP_ALLOWED_KEYS = _MACHINE_MINDMAP_REQUIRED_KEYS | frozenset({'governing_spec', 'defect_spec_status', 'defect_spec_receipt_sha256', 'orphan_notes', 'self_check'})

class MachineMindmapError(ValueError):
    pass

def validate_machine_mindmap_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise MachineMindmapError('machine mindmap root must be an object')
    keys = set(payload)
    if not _MACHINE_MINDMAP_REQUIRED_KEYS.issubset(keys):
        raise MachineMindmapError('machine mindmap required fields are missing')
    if not keys.issubset(_MACHINE_MINDMAP_ALLOWED_KEYS):
        raise MachineMindmapError('machine mindmap has unknown root fields')
    if not accepts_schema(payload.get('schema'), _MACHINE_MINDMAP_SCHEMA):
        raise MachineMindmapError('machine mindmap schema is unsupported')
    if not isinstance(payload.get('source'), str) or not payload['source'].strip():
        raise MachineMindmapError('machine mindmap source must be a non-empty string')
    if 'governing_spec' in payload and payload['governing_spec'] is not None:
        if not isinstance(payload['governing_spec'], str):
            raise MachineMindmapError('machine mindmap governing_spec is invalid')
    if 'defect_spec_status' in payload and (not isinstance(payload['defect_spec_status'], str)):
        raise MachineMindmapError('machine mindmap defect_spec_status is invalid')
    if 'defect_spec_receipt_sha256' in payload and payload['defect_spec_receipt_sha256'] is not None and (not isinstance(payload['defect_spec_receipt_sha256'], str)):
        raise MachineMindmapError('machine mindmap defect receipt is invalid')
    if 'orphan_notes' in payload and (not isinstance(payload['orphan_notes'], list)):
        raise MachineMindmapError('machine mindmap orphan_notes must be an array')
    if 'self_check' in payload and (not isinstance(payload['self_check'], dict)):
        raise MachineMindmapError('machine mindmap self_check must be an object')
    return payload

def load_machine_mindmap(path: str | Path) -> tuple[dict[str, Any], str]:
    target = Path(path)
    raw = read_regular_nofollow(target, error_type=MachineMindmapError, invalid_message='machine mindmap path is invalid', directory_message='machine mindmap directory is unavailable', open_message='machine mindmap is unavailable', bounds_message='machine mindmap exceeds the byte budget', changed_message='machine mindmap changed while being read', max_bytes=_MACHINE_MINDMAP_MAX_BYTES)
    assert isinstance(raw, bytes)
    validate_json_budget(raw, error_type=MachineMindmapError, message='machine mindmap exceeds the JSON structure budget')

    def _reject_duplicate_keys(pairs):
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('duplicate JSON key')
            out[key] = value
        return out

    def _reject_constant(value):
        raise ValueError(f'non-finite JSON constant: {value}')
    try:
        payload = json.loads(raw.decode('utf-8'), object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapError('machine mindmap is not valid JSON') from exc
    return (validate_machine_mindmap_payload(payload), sha256_bytes(raw))

def origin_zh(raw: str | None) -> str:
    text = str(raw or '').strip()
    if not text:
        return '脑图原文'
    if text == 'title':
        return '脑图原文：标题'
    m = _ORIGIN_STEP_RE.match(text)
    if m:
        return f'脑图原文：步骤{m.group(1)}'
    m = _ORIGIN_EXPECT_RE.match(text)
    if m:
        return f'脑图原文：期望{m.group(1)}'
    m = _ORIGIN_SPEC_RE.match(text)
    if m:
        stem = Path(m.group(1)).stem
        return f'规格书 {stem} 第{m.group(2)}行'
    m = _ORIGIN_DEFECT_SPEC_RE.match(text)
    if m:
        return f'缺陷规格 {m.group(1)}/{m.group(2)} 的{m.group(3)}字段'
    return f'脑图原文：{text}'

def _expectation_id(autoid: str, step: str, index: int) -> str:
    return f'u1:{autoid}:{step}:{index}'

def _semantic_key(autoid: str, step: str) -> str:
    return f'{autoid}:step:{step}'

def _canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256_bytes(raw)

def _author_claim(*, autoid: str, item: dict[str, Any], index: int, mindmap_source_sha256: str) -> dict[str, str]:
    if not _SHA256_RE.fullmatch(str(mindmap_source_sha256 or '')):
        raise ValueError('pending Author claim has no sealed mindmap source SHA256')
    origin = str(item.get('origin') or '').strip()
    source_text = str(item.get('text') or '')
    step = str(item.get('n') or '').strip()
    if not origin or not source_text or (not step):
        raise ValueError('pending Author claim source binding is incomplete')
    expectation_id = _expectation_id(autoid, step, index)
    body = {'schema': 'ist.author-claim', 'kind': 'Author', 'autoid': autoid, 'expectation_id': expectation_id, 'semantic_key': _semantic_key(autoid, step), 'origin': origin, 'source_text': source_text, 'source_sha256': mindmap_source_sha256}
    if not _locator_semantic_text(source_text, origin):
        raise ValueError('pending Author claim has no natural-language criterion')
    return {**body, 'claim_sha256': _canonical_sha256(body)}

def _defect_spec_claim(*, autoid: str, item: dict[str, Any], index: int, defect_spec_receipt: dict[str, Any] | None) -> dict[str, Any]:
    origin = str(item.get('origin') or '').strip()
    match = _ORIGIN_DEFECT_SPEC_RE.fullmatch(origin)
    if match is None or not isinstance(defect_spec_receipt, dict):
        raise ValueError('pending DefectSpec claim has no engine-bound receipt')
    projection = defect_spec_receipt.get('projection')
    source_text = str(item.get('text') or '')
    field = match.group(3).lower()
    if not isinstance(projection, dict) or source_text != str(projection.get(field) or ''):
        raise ValueError('pending DefectSpec claim is not the whole projection field')
    step = str(item.get('n') or '').strip()
    if not step:
        raise ValueError('pending DefectSpec claim has no step identity')
    expectation_id = _expectation_id(autoid, step, index)
    resolver_receipt_sha = _canonical_sha256(defect_spec_receipt)
    body: dict[str, Any] = {'schema': 'ist.defect-spec-claim', 'kind': 'DefectSpec', 'autoid': autoid, 'expectation_id': expectation_id, 'semantic_key': _semantic_key(autoid, step), 'origin': origin, 'source_text': source_text, 'locator': origin, 'resolver_receipt': defect_spec_receipt, 'resolver_receipt_sha256': resolver_receipt_sha}
    return {**body, 'claim_sha256': _canonical_sha256(body)}

def _case_missing_fields(case: dict[str, Any]) -> list[str]:
    contract = case.get('contract')
    origin = case.get('origin')
    if not isinstance(contract, dict) or not isinstance(origin, dict):
        return list(_SCENARIO2_SOURCE_FIELDS)
    missing: list[str] = []
    for field in ('intent', 'expectation'):
        if not isinstance(contract.get(field), str) or not str(contract.get(field) or '').strip() or (not _valid_origin(str(origin.get(field) or ''))):
            missing.append(field)
    steps = case.get('steps')
    if not isinstance(steps, list) or not steps or any((not isinstance(item, dict) or not str(item.get('n') or '').strip() or (not str(item.get('text') or '').strip()) for item in steps)):
        missing.insert(1 if 'intent' in missing else 0, 'steps')
    expectations = case.get('expectations_by_step')
    if not isinstance(expectations, list) or not expectations:
        if 'expectation' not in missing:
            missing.append('expectation')
    elif any((not isinstance(item, dict) or not str(item.get('n') or '').strip() or (not str(item.get('text') or '').strip()) or (not _valid_origin(str(item.get('origin') or ''))) for item in expectations)):
        if 'expectation' not in missing:
            missing.append('expectation')
    return [field for field in _SCENARIO2_SOURCE_FIELDS if field in missing]

def _decision_missing_fields(case: dict[str, Any]) -> list[str]:
    public_name = {'intent': 'description', 'steps': 'steps', 'expectation': 'expectation'}
    return [public_name[field] for field in _case_missing_fields(case)]

def _derived_source_status(case: dict[str, Any]) -> str:
    return 'incomplete' if _case_missing_fields(case) else 'complete'

def _derived_typed_assertion_status(case: dict[str, Any]) -> str:
    expectations = case.get('expectations_by_step')
    if not isinstance(expectations, list) or not expectations:
        return 'invalid'
    pending = False
    for index, item in enumerate(expectations, start=1):
        if not isinstance(item, dict) or 'assertion' not in item:
            return 'invalid'
        if item.get('assertion') is None:
            pending = True
            continue
        try:
            _typed_expectation(autoid=str(case.get('autoid') or ''), item=item, index=index)
        except Exception:
            return 'invalid'
    return 'pending' if pending else 'ready'

def _declared_status_matches(case: dict[str, Any], field: str, actual: str) -> bool:
    declared = case.get(field)
    if declared is None:
        return True
    allowed = _SOURCE_STATUSES if field == 'source_status' else _TYPED_ASSERTION_STATUSES
    return isinstance(declared, str) and declared in allowed and (declared == actual)

def case_status_mismatches(case: dict[str, Any]) -> list[tuple[str, str]]:
    source_status = _derived_source_status(case)
    mismatches: list[tuple[str, str]] = []
    if not _declared_status_matches(case, 'source_status', source_status):
        mismatches.append(('source_status', source_status))
    if source_status == 'complete':
        typed_status = _derived_typed_assertion_status(case)
        if typed_status not in _TYPED_ASSERTION_STATUSES or not _declared_status_matches(case, 'typed_assertion_status', typed_status):
            mismatches.append(('typed_assertion_status', typed_status))
    return mismatches

def normalize_submission_case_statuses(case: dict[str, Any]) -> None:
    source_status = _derived_source_status(case)
    case['source_status'] = source_status
    typed_status = _derived_typed_assertion_status(case)
    if typed_status in _TYPED_ASSERTION_STATUSES:
        case['typed_assertion_status'] = typed_status
    elif source_status == 'incomplete' and (not case.get('expectations_by_step')):
        case['typed_assertion_status'] = 'pending'

def primary_expectation_projection_problems(case: dict[str, Any]) -> list[tuple[str, str]]:
    authored = [item for item in case.get('expectations_by_step') or () if isinstance(item, dict) and str(item.get('text') or '').strip() and (str(item.get('origin') or '') == 'title' or str(item.get('origin') or '').startswith(('step:', 'expectation:')))]
    if not authored:
        return []
    contract = case.get('contract') or {}
    origin = case.get('origin') or {}
    problems: list[tuple[str, str]] = []
    if not str(contract.get('expectation') or '').strip():
        problems.append(('contract.expectation', 'primary_expectation_missing'))
    if not str(origin.get('expectation') or '').strip():
        problems.append(('origin.expectation', 'primary_expectation_origin_missing'))
    return problems

def expectation_source_binding(origin: str, expectation_id: str, *, defect_spec_receipt: dict[str, Any] | None=None) -> dict[str, Any]:
    text = str(origin or '').strip()
    if _ORIGIN_SPEC_RE.fullmatch(text):
        return {'kind': 'spec', 'locator': text.removeprefix('spec:')}
    if _ORIGIN_DEFECT_SPEC_RE.fullmatch(text):
        return {'kind': 'defect_spec', 'locator': text, **({'receipt': defect_spec_receipt} if isinstance(defect_spec_receipt, dict) else {})}
    return {'kind': 'intent', 'locator': str(expectation_id or '')}

def _typed_expectation(*, autoid: str, item: dict[str, Any], index: int, defect_spec_receipt: dict[str, Any] | None=None) -> dict[str, Any]:
    raw = item.get('assertion')
    if not isinstance(raw, dict):
        raise ValueError('expectation assertion tuple is missing')
    operator = str(raw.get('operator') or '').strip()
    value = str(raw.get('value') or '')
    if not operator or not value:
        raise ValueError('expectation assertion operator/value is incomplete')
    from cex_core.engine.case_compiler.excel_contract import contract_entry, load_excel_contract, validate_g_for_entry
    excel_contract = load_excel_contract()
    entry = contract_entry('check_point', operator, excel_contract)
    if entry is None or entry.get('status') != 'enabled':
        raise ValueError('expectation assertion operator is not enabled')
    validate_g_for_entry(entry, value, excel_contract)
    origin = str(item.get('origin') or '').strip()
    step = str(item.get('n') or '').strip()
    expectation_id = _expectation_id(autoid, step, index)
    source_binding = expectation_source_binding(origin, expectation_id, defect_spec_receipt=defect_spec_receipt)
    return {'expectation_id': expectation_id, 'semantic_key': _semantic_key(autoid, step), 'operator': operator, 'value': value, 'origin': origin, 'source': source_binding}

def _author_expectation_clauses(text: str) -> list[str]:
    source = str(text or '')
    if not source.strip():
        return []
    opening = {'(': ')', '（': '）', '[': ']', '【': '】', '{': '}'}
    closing = set(opening.values())
    quote_pairs = {'“': '”', '‘': '’', '"': '"', "'": "'"}
    stack: list[str] = []
    quote: str | None = None
    start = 0
    clauses: list[str] = []
    for index, char in enumerate(source):
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in quote_pairs:
            quote = quote_pairs[char]
            continue
        if char in opening:
            stack.append(opening[char])
            continue
        if char in closing:
            if not stack or stack.pop() != char:
                return [source.strip()]
            continue
        if char in {'，', '；'} and (not stack):
            clause = source[start:index].strip()
            if not clause:
                return [source.strip()]
            clauses.append(clause)
            start = index + 1
    if stack or quote is not None:
        return [source.strip()]
    tail = source[start:].strip()
    if not tail:
        return [source.strip()]
    clauses.append(tail)
    return clauses if len(clauses) > 1 else [source.strip()]

def _expectations(case: dict[str, Any], *, mindmap_source_sha256: str, defect_spec_receipt: dict[str, Any] | None=None) -> list[dict[str, Any]]:
    by_step = [e for e in case.get('expectations_by_step') or [] if isinstance(e, dict) and str(e.get('text') or '').strip()]
    if by_step:
        autoid = str(case.get('autoid') or '')
        claim_inputs: list[tuple[dict[str, Any], int, int]] = []
        for source_index, source_item in enumerate(by_step, start=1):
            origin = str(source_item.get('origin') or '').strip()
            clauses = _author_expectation_clauses(str(source_item.get('text') or '')) if not isinstance(source_item.get('assertion'), dict) and _ORIGIN_DEFECT_SPEC_RE.fullmatch(origin) is None else [str(source_item.get('text') or '')]
            for clause_index, clause in enumerate(clauses, start=1):
                claim_inputs.append(({**source_item, 'text': clause}, source_index, clause_index))
        projected: list[dict[str, Any]] = []
        for claim_index, (item, source_index, clause_index) in enumerate(claim_inputs, start=1):
            origin = str(item.get('origin') or '').strip()
            clause_count = sum((1 for _item, item_source_index, _clause_index in claim_inputs if item_source_index == source_index))
            anchor = origin_zh(origin)
            if clause_count > 1:
                anchor += f'；原文分句{clause_index}/{clause_count}'
            projected.append({'text': str(item['text']), 'text_anchor': anchor, 'value_grounding': _VALUE_GROUNDING, **({'assertion': _typed_expectation(autoid=autoid, item=item, index=claim_index, defect_spec_receipt=defect_spec_receipt)} if isinstance(item.get('assertion'), dict) else {'defect_spec_claim': _defect_spec_claim(autoid=autoid, item=item, index=claim_index, defect_spec_receipt=defect_spec_receipt)} if _ORIGIN_DEFECT_SPEC_RE.fullmatch(origin) else {'author_claim': _author_claim(autoid=autoid, item=item, index=claim_index, mindmap_source_sha256=mindmap_source_sha256)})})
        return projected
    origin = case.get('origin') or {}
    return [{'text': str((case.get('contract') or {}).get('expectation') or ''), 'text_anchor': origin_zh(origin.get('expectation')), 'value_grounding': _VALUE_GROUNDING, 'assertion': _typed_expectation(autoid=str(case.get('autoid') or ''), item={'n': 'fallback', 'origin': origin.get('expectation'), 'assertion': case.get('assertion')}, index=1, defect_spec_receipt=defect_spec_receipt)}]

def _card_bucket(case: dict[str, Any]) -> str:
    bucket = case.get('bucket')
    if isinstance(bucket, str) and bucket in _CARD_BUCKETS:
        return bucket
    if bucket == 'true_gap':
        return 'step_recipe'
    raise MachineMindmapError('machine mindmap case bucket cannot be carded')

def _engine_sampling_records(card: Mapping[str, Any]) -> list[dict[str, Any]]:
    from cex_core.engine.case_compiler.step_structure import ENGINE_SLOTS_KEY, engine_sampling_records
    return engine_sampling_records({ENGINE_SLOTS_KEY: card.get(ENGINE_SLOTS_KEY) or []})

def _algorithm_family_token_map() -> dict[str, tuple[str, ...]]:
    """词表令牌 → 全部登记分类；分类可重叠，不选一个覆盖另一个。"""
    from cex_core.engine.case_compiler.domain_grammar import load_grammar
    tokens: dict[str, set[str]] = {}
    for family, entry in (load_grammar().get('algorithm_classes') or {}).items():
        for method in entry.get('methods') or []:
            tokens.setdefault(str(method).strip().lower(), set()).add(str(family))
    return {token: tuple(sorted(families)) for token, families in tokens.items()}

def _author_algorithm_mentions_disclosures(autoid: str, raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    """披露标题/分组与步骤出现的词表字符串，语义作用域保持未核。

    词边界匹配也会命中域名、不同对象层次和迁移过程，不能据此认定算法声明或
    来源冲突。只保留原文与词面命中，不改变一致性处置、采样、预期或受理结论。
    """
    tokens = _algorithm_family_token_map()
    if not tokens:
        return []

    def _mentions(text: str) -> set[str]:
        found: set[str] = set()
        lowered = str(text or '').lower()
        for token in tokens:
            if re.search(f'(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])', lowered):
                found.add(token)
        return found

    def _labels(mentions: set[str]) -> list[str]:
        return [f"{token}({','.join(tokens[token])})" for token in sorted(mentions)]
    group = raw.get('mindmap_group')
    group_text = '/'.join((str(part) for part in group.get('group_path') or [])) if isinstance(group, Mapping) else str(group or '')
    title_text = str(raw.get('intent_verbatim') or '')
    title_tokens = _mentions(f'{group_text} {title_text}')
    if not title_tokens:
        return []
    differing: list[tuple[str, str, set[str]]] = []
    for step in raw.get('author_steps') or []:
        if not isinstance(step, Mapping):
            continue
        step_text = str(step.get('text') or '')
        step_tokens = _mentions(step_text)
        if not step_tokens:
            continue
        if step_tokens - title_tokens:
            differing.append((str(step.get('n') or '?'), step_text, step_tokens))
    if not differing:
        return []
    quoted = '；'.join((f"第 {n} 步「{text}」出现 {', '.join(_labels(mentions))}" for n, text, mentions in differing))
    return [{'autoid': autoid, 'code': 'author_algorithm_mentions_disclosure', 'message': f"用例 {autoid} 的分组「{group_text}」、标题「{title_text}」中匹配到词表字符串 {', '.join(_labels(title_tokens))}；步骤中还出现其它词表字符串：{quoted}。括号只列词表分类。匹配可能来自域名、不同对象层次或迁移过程，是否构成算法声明、是否指向同一作用域及是否冲突均未核验。此项只记录原文与字符串命中，不改变来源一致性处置、采样与预期。", 'reason_code': 'author_algorithm_mentions_unverified', 'fallback_allowed': True, 'group_text': group_text, 'title_text': title_text, 'title_tokens': _labels(title_tokens), 'differing_steps': [{'n': n, 'text': text, 'tokens': _labels(mentions)} for n, text, mentions in differing]}]

def _step_structure_disclosures(autoid: str, raw: Mapping[str, Any], *, object_kinds_available: bool, tiers: Sequence[Mapping[str, Any]]=()) -> list[dict[str, Any]]:
    from cex_core.engine.ist_core.display_lexicon import STEP_STRUCTURE_ABSENT_CN, STEP_STRUCTURE_KIND_SKIPPED_CN, device_disclosure_cn
    out: list[dict[str, Any]] = []
    if (raw.get('author_steps') or []) and (not (raw.get('step_structure') or [])):
        out.append({'autoid': autoid, 'code': 'step_structure_absent', 'message': STEP_STRUCTURE_ABSENT_CN, 'reason_code': 'step_structure_absent'})
    elif not object_kinds_available:
        out.append({'autoid': autoid, 'code': 'step_structure_kind_check_skipped', 'message': STEP_STRUCTURE_KIND_SKIPPED_CN, 'reason_code': 'projection_unavailable'})
    rows = [row for row in tiers or () if isinstance(row, Mapping)]
    if not any((str(row.get('tier') or '') == 'T1' for row in rows)):
        return out
    for row in rows:
        out.append({'autoid': autoid, 'code': 'device_disclosure', 'message': device_disclosure_cn(row), 'tier': str(row.get('tier') or ''), 'reason_code': str(row.get('code') or ''), 'fact_id': str(row.get('fact_id') or ''), 'characteristic_class': str(row.get('characteristic_class') or ''), 'locator': str(row.get('locator') or ''), 'pinned': str(row.get('pinned') or ''), 'detail': dict(row.get('detail') or {})})
    return out

def _card_step_structure(case: Mapping[str, Any], expectations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    from cex_core.engine.case_compiler.step_structure import ENGINE_SLOTS_KEY, STEP_STRUCTURE_KEY, apply_engine_slots, distribution_criterion_bindings, strip_engine_slots
    structure = case.get(STEP_STRUCTURE_KEY)
    if not isinstance(structure, list):
        return ([], [], [])
    staged = {'autoid': str(case.get('autoid') or ''), STEP_STRUCTURE_KEY: copy.deepcopy(structure), 'concretizations': copy.deepcopy(case.get('concretizations') or []), 'steps': list(case.get('steps') or [])}
    strip_engine_slots(staged)
    bindings = distribution_criterion_bindings(expectations)
    apply_engine_slots(staged, bindings)
    entries = [item for item in staged[STEP_STRUCTURE_KEY] if isinstance(item, dict)]
    records = [item for item in staged.get(ENGINE_SLOTS_KEY) or [] if isinstance(item, dict)]
    return (entries, records, _card_device_disclosure(case, entries, records, has_distribution_criterion=bool(bindings)))

def _card_device_disclosure(case: Mapping[str, Any], entries: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]], *, has_distribution_criterion: bool) -> list[dict[str, Any]]:
    from cex_core.engine.case_compiler.behaviour_classes import resolve_behaviour_classes
    from cex_core.engine.case_compiler.device_characteristics import flatten_tiers, observation_pairing_unavailable_disclosure, select_disclosure
    steps = [str(number) for record in records for number in record.get('applies_to_steps') or [] if str(number).strip()]
    tiers = select_disclosure(entries, resolve_behaviour_classes(entries), case=case, distribution_steps=steps, has_distribution_criterion=has_distribution_criterion)
    if any((str(record.get('reason_code') or '') == 'pairing_ambiguous' for record in records)):
        tiers['T4'].append(observation_pairing_unavailable_disclosure())
    return flatten_tiers(tiers)

def ground_condition_author_text(author_text: str, step_text: str) -> dict | None:
    """条件 author_text 的接地：在两侧转义形态的笛卡尔积上找 span。

    与条件 text 的子串检查同一份形态集（verbatim_candidates），转义形态与
    空白归一都容——判定侧只收「接得到/接不到」这一个关系。
    """
    for form in verbatim_candidates(str(author_text or '')):
        for step_form in verbatim_candidates(str(step_text or '')):
            span = ground_source_span(form, step_form)
            if span is not None:
                return span
    return None

def _condition_grounding(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """条件 author_text 的接地收据：只记非逐字命中的矫正（空白归一后接上）。

    逐字接地零记录；这里披露的是「模型写的 author_text 与密封原文有空白差
    异、引擎按区间矫正放行」的痕迹，停批不发生（09-11 改写制条款）。
    """
    from cex_core.engine.case_compiler.step_structure import STEP_STRUCTURE_KEY
    out: list[dict[str, Any]] = []
    structure = case.get(STEP_STRUCTURE_KEY)
    if not isinstance(structure, list):
        return out
    by_number = {str(item.get('n') or '').strip(): str(item.get('text') or '') for item in case.get('steps') or [] if isinstance(item, dict)}
    for entry_position, entry in enumerate(structure):
        if not isinstance(entry, dict):
            continue
        number = str(entry.get('n') or '').strip()
        step_text = by_number.get(number)
        if step_text is None:
            continue
        for condition_position, condition in enumerate(entry.get('stated_conditions') or ()):
            if not isinstance(condition, dict):
                continue
            author_text = str(condition.get('author_text') or '')
            if not author_text.strip():
                continue
            span = ground_condition_author_text(author_text, step_text)
            if span is None or span.get('match') == 'verbatim':
                continue
            out.append({'n': number, 'entry': entry_position, 'condition': condition_position, 'match': str(span.get('match') or ''), 'start': int(span.get('start') or 0), 'end': int(span.get('end') or 0)})
    return out

def _project_case(case: dict[str, Any], *, mindmap_source_sha256: str, defect_spec_receipt: dict[str, Any] | None=None, mindmap_text: str | None=None, resource: Any=None, criterion_version_family: str='', criterion_manual_version: str='', criterion_rule_records: Mapping[tuple[str, str], Mapping[str, Any]] | None=None) -> dict[str, Any]:
    contract = case.get('contract') or {}
    origin = case.get('origin') or {}
    scope: list[str] = [str(x) for x in case.get('adaptation_notes') or [] if str(x).strip()]
    depends_on = str(case.get('depends_on') or '').strip()
    if depends_on:
        scope.append(f'依赖前序案尾号{depends_on[-6:]}的最终状态，编写期并入或适配')
    method = str(contract.get('verification_method') or '').strip()
    method_origin = str(origin.get('verification_method') or '').strip()
    if not method or not _valid_origin(method_origin):
        first_step = (case.get('steps') or [{}])[0]
        method = str(first_step.get('text') or '')
        method_origin = f"step:{str(first_step.get('n') or '').strip()}"
    consistency_card: dict[str, Any] = {'consistency': case['consistency']} if 'consistency' in case else {}
    projected_expectations = _expectations(case, mindmap_source_sha256=mindmap_source_sha256, defect_spec_receipt=defect_spec_receipt)
    if mindmap_text is not None:
        from cex_core.engine.case_compiler.criterion_normalization import normalize_case_expectations
        normalized = normalize_case_expectations(case=case, expectations=projected_expectations, mindmap_text=mindmap_text, resource=resource, version_family=criterion_version_family, author_rules=criterion_rule_records, manual_version=criterion_manual_version or None)
        projected_expectations = list(normalized.expectations)
    step_structure, engine_slots, device_disclosure = _card_step_structure(case, projected_expectations)
    from cex_core.engine.case_compiler.step_structure import ADAPTED_STEPS_KEY
    return {**consistency_card, 'contract_class': 'mindmap_verbatim', 'autoid': str(case.get('autoid') or ''), 'bucket': _card_bucket(case), 'source_status': _derived_source_status(case), 'typed_assertion_status': _derived_typed_assertion_status(case), 'mindmap_group': {'group_path': [str(x) for x in case.get('group_path') or []] or ['（未分组）']}, 'intent_verbatim': str(contract.get('intent') or case.get('title') or ''), 'intent_anchor': origin_zh(origin.get('intent')), 'verification_method': {'selected_rule': method, 'authority': origin_zh(method_origin)}, 'author_steps': [{'n': str(item.get('n') or ''), 'text': str(item.get('text') or ''), 'origin': f"step:{str(item.get('n') or '')}"} for item in case.get('steps') or [] if isinstance(item, dict) and str(item.get('n') or '').strip() and str(item.get('text') or '').strip()], 'adapted_steps': [{'n': str(item.get('n') or ''), 'text': str(item.get('text') or ''), 'basis': str(item.get('basis') or '')} for item in case.get(ADAPTED_STEPS_KEY) or [] if isinstance(item, dict) and str(item.get('n') or '').strip() and str(item.get('text') or '').strip()], 'rebind_licenses': [{'author_literal': str(item.get('author_literal') or ''), 'verdict': str(item.get('verdict') or ''), 'occurrences': [str(occ).strip() for occ in item.get('occurrences') or [] if str(occ).strip()], 'constraints': str(item.get('constraints') or ''), 'reason': str(item.get('reason') or '')} for item in case.get('rebind_licenses') or [] if isinstance(item, dict) and str(item.get('author_literal') or '').strip() and str(item.get('verdict') or '').strip()], 'step_structure': step_structure, 'condition_grounding': _condition_grounding(case), 'engine_slots': engine_slots, 'device_disclosure': device_disclosure, 'expectations': projected_expectations, 'scope_adaptations': scope}

def _project_manifest_fallback_case(manifest_case: dict[str, Any], *, mindmap_source_sha256: str) -> dict[str, Any]:
    autoid = str(manifest_case.get('autoid') or '').strip()
    title = str(manifest_case.get('title') or '').strip()
    if not re.fullmatch(_LOCATOR_TOKEN, autoid) or not title:
        raise ValueError('manifest fallback identity or title is invalid')
    if _SHA256_RE.fullmatch(str(mindmap_source_sha256 or '')) is None:
        raise ValueError('manifest fallback has no sealed mindmap source SHA256')
    raw_steps = manifest_case.get('step_intents')
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError('manifest fallback has no author step_intents')
    authored_steps: list[tuple[int, str, str]] = []
    for index, item in enumerate(raw_steps, start=1):
        if not isinstance(item, dict):
            raise ValueError('manifest fallback step_intents contains a non-object')
        desc = str(item.get('desc') or '').strip()
        expected = str(item.get('expected') or '').strip()
        if not desc:
            raise ValueError('manifest fallback has an empty author step description')
        authored_steps.append((index, desc, expected))
    claim_inputs: list[dict[str, str]] = [{'n': str(step_index), 'text': expected, 'origin': f'manifest:step_intents[{step_index - 1}].expected', 'text_anchor': f'作者用例：第{step_index}步预期'} for step_index, _desc, expected in authored_steps if expected]
    raw_unbound = manifest_case.get('unbound_expectations') or []
    if not isinstance(raw_unbound, list) or any((not isinstance(value, str) for value in raw_unbound)):
        raise ValueError('manifest fallback unbound_expectations is invalid')
    claim_inputs.extend(({'n': f'unbound-{index}', 'text': value.strip(), 'origin': f'manifest:unbound_expectations[{index - 1}]', 'text_anchor': f'作者用例：未绑定预期{index}'} for index, value in enumerate(raw_unbound, start=1) if value.strip()))
    if not claim_inputs:
        raise ValueError('manifest fallback has no Author expected declaration')
    expectations: list[dict[str, Any]] = []
    for claim_index, item in enumerate(claim_inputs, start=1):
        expectations.append({'text': item['text'], 'text_anchor': item['text_anchor'], 'value_grounding': _VALUE_GROUNDING, 'author_claim': _author_claim(autoid=autoid, item=item, index=claim_index, mindmap_source_sha256=mindmap_source_sha256)})
    first_step_index, first_desc, _expected = authored_steps[0]
    return {'contract_class': 'mindmap_verbatim', 'autoid': autoid, 'bucket': 'step_recipe', 'source_status': 'complete', 'typed_assertion_status': 'pending', 'mindmap_group': {'group_path': [str(value) for value in manifest_case.get('group_path') or [] if str(value).strip()] or ['（未分组）']}, 'intent_verbatim': title, 'intent_anchor': '作者用例：标题', 'verification_method': {'selected_rule': first_desc, 'authority': f'作者用例：第{first_step_index}步描述'}, 'author_steps': [{'n': str(step_index), 'text': desc, 'origin': f'manifest:step_intents[{step_index - 1}].desc'} for step_index, desc, _expected in authored_steps], 'expectations': expectations, 'scope_adaptations': []}

def _enhancement_disclosures_for_case(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    autoid = str(case.get('autoid') or '')
    out: list[dict[str, Any]] = []
    from cex_core.engine.case_compiler.step_structure import ADAPTED_STEPS_KEY, step_is_adapted
    authored_steps = {str(item.get('n') or '').strip(): str(item.get('text') or '') for item in case.get('steps') or [] if isinstance(item, dict)}
    for item in case.get(ADAPTED_STEPS_KEY) or []:
        if not isinstance(item, dict):
            continue
        number = str(item.get('n') or '').strip()
        adapted_text = str(item.get('text') or '').strip()
        authored_text = authored_steps.get(number, '')
        if not number or not adapted_text or (not step_is_adapted(authored_text, adapted_text)):
            continue
        out.append({'autoid': autoid, 'code': 'adapted_step_disclosure', 'message': f'步骤适配（第{number}步）：作者原文「{authored_text[:200]}」→适配为「{adapted_text[:200]}」' + (f"，依据：{str(item.get('basis') or '').strip()[:200]}" if str(item.get('basis') or '').strip() else ''), 'reason_code': 'recompose_adapted_step'})
    for text in case.get('proposal') or []:
        if isinstance(text, str) and text.strip():
            out.append({'autoid': autoid, 'code': 'mindmap_proposal_disclosure', 'message': f'重组 proposal：{text.strip()[:200]}', 'reason_code': 'recompose_proposal'})
    for item in case.get('concretizations') or []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get('slot') or '')
        author_text = str(item.get('author_text') or '')
        value = str(item.get('value') or '')
        out.append({'autoid': autoid, 'code': 'process_value_concretization', 'message': f"过程值具体化（{slot}）：「{author_text or '（留白）'}」→「{value}」（预期文本未改）", 'reason_code': 'recompose_concretization'})
    for lic in case.get('rebind_licenses') or []:
        if not isinstance(lic, dict):
            continue
        author_literal = str(lic.get('author_literal') or '')
        verdict = str(lic.get('verdict') or '')
        constraints = str(lic.get('constraints') or '')
        reason = str(lic.get('reason') or '')
        out.append({'autoid': autoid, 'code': 'rebind_license_mapping', 'message': f'重绑许可披露（{verdict}）：作者原文「{author_literal}」' + ('已按改写制在适配步骤中转为可执行的自动化取值' if verdict == 'rebindable' else '判定承重，适配与编译均保持该字面') + f'；承重判断依据：{reason[:200]}' + (f'；约束：{constraints[:200]}' if constraints else ''), 'reason_code': 'recompose_rebind_license'})
    return out
PROPOSAL_SHAPE_ERROR_CN = 'proposal 必须是非空字符串组成的数组（无缺口时为空数组）'

def proposal_shape_error(case: Mapping[str, Any] | dict[str, Any]) -> str | None:
    """`proposal` 形态判据的唯一一份：非空纯字符串数组，无缺口时为空数组；缺键同样不合规。
    分片提交口（recompose_parts）用它教回重交，投影器（_eligible）用它 fail-closed。"""
    proposal = case.get('proposal')
    if not isinstance(proposal, list) or any((not isinstance(item, str) or not item.strip() for item in proposal)):
        return PROPOSAL_SHAPE_ERROR_CN
    return None

def primary_expectation_membership_error(case: Mapping[str, Any]) -> str | None:
    """完整来源的主期望必须以同一出处和既有文本形式出现在分步闭集。

    不比较两个声明的语义，也不选择权威来源。缺口或其他形态不完整的材料仍交给
    原有完整性/形状路由；分片入口与投影器只在本规则原有前提成立时消费同一判据。
    """
    material = dict(case)
    if _derived_source_status(material) != 'complete' or _derived_typed_assertion_status(material) not in _TYPED_ASSERTION_STATUSES:
        return None
    contract = material.get('contract') or {}
    origin = material.get('origin') or {}
    primary = _norm_ws(str(contract.get('expectation') or ''))
    primary_origin = str(origin.get('expectation') or '').strip()
    if not any((str(item.get('origin') or '').strip() == primary_origin and primary in {_norm_ws(str(item.get('text') or '')), _locator_semantic_text(str(item.get('text') or ''), str(item.get('origin') or ''))} for item in material['expectations_by_step'])):
        return '主期望未进入分步期望闭集'
    return None

def _eligible(case: dict[str, Any], *, mindmap_text: str='', governing_spec: str | None=None, spec_text: str | None=None, defect_spec_receipt: dict[str, Any] | None=None) -> tuple[bool, str]:
    proposal_error = proposal_shape_error(case)
    if proposal_error:
        return (False, proposal_error)
    from cex_core.engine.ist_core.compile_engine.rebind_binder import validate_case_enhancement_fields
    enhancement_errors = validate_case_enhancement_fields(case)
    if enhancement_errors:
        return (False, enhancement_errors[0])
    if 'consistency' in case:
        consistency = case['consistency']
        if isinstance(consistency, dict):
            stamp_failure = stamp_consistency_quotes(consistency, str(case.get('autoid') or ''), mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt, cross_check=False)
            if stamp_failure:
                if 'locator_unresolved' in stamp_failure:
                    return (False, f'recompose 一致性结论的出处解不出（{stamp_failure}）')
                if 'drift' in stamp_failure:
                    return (False, f'recompose 一致性结论的引文与引擎盖章不一致（{stamp_failure}）')
                return (False, f'recompose 一致性结论不在闭集（{stamp_failure}）')
        consistency_failure = recompose_consistency_failure(consistency)
        if consistency_failure:
            return (False, f'recompose 一致性结论不在闭集（{consistency_failure}）')
    contract = case.get('contract') or {}
    origin = case.get('origin') or {}
    for field in ('intent', 'expectation'):
        if not str(contract.get(field) or '').strip():
            return (False, '用例描述或预期不完整')
        if not _valid_origin(str(origin.get(field) or '')):
            return (False, '契约字段缺少可核验出处')
    raw_step_expectations = case.get('expectations_by_step')
    if not isinstance(raw_step_expectations, list) or not raw_step_expectations or any((not isinstance(item, dict) or not str(item.get('n') or '').strip() or (not str(item.get('text') or '').strip()) or (not _valid_origin(str(item.get('origin') or ''))) or ('assertion' not in item) for item in raw_step_expectations)):
        return (False, '分步期望缺少步骤绑定、原文、出处或 assertion 状态')
    source_status = _derived_source_status(case)
    typed_status = _derived_typed_assertion_status(case)
    mismatches = case_status_mismatches(case)
    if mismatches:
        return (False, f'{mismatches[0][0]} 与机械复算结果不一致')
    if source_status != 'complete':
        return (False, '脑图源描述、步骤或自然语言预期不完整')
    if typed_status not in _TYPED_ASSERTION_STATUSES:
        return (False, '分步期望的 typed assertion 既非 ready 也非 pending')
    membership_error = primary_expectation_membership_error(case)
    if membership_error:
        return (False, membership_error)
    return (True, '')

def _scenario2_incomplete_reason(case: dict[str, Any], *, governing_spec_status: str | None, defect_spec_status: str | None, defect_spec_receipt_sha256: str | None, mindmap_text: str | None=None) -> str:
    raw_proposal = case.get('proposal')
    if not isinstance(raw_proposal, list) or any((not isinstance(item, str) or not item.strip() for item in raw_proposal)):
        return ''
    proposal = [item.strip() for item in raw_proposal]
    if not proposal:
        return ''
    proof = case.get('scenario2')
    if not isinstance(proof, dict):
        return ''
    if set(proof) != {'reason_code', 'missing_fields', 'spec_status', 'defect_spec_status', 'defect_spec_receipt_sha256'}:
        return ''
    reason_code = str(proof.get('reason_code') or '').strip()
    proof_missing = proof.get('missing_fields')
    if reason_code != _SCENARIO2_REASON or not isinstance(proof_missing, list) or (not proof_missing) or any((field not in _SCENARIO2_SOURCE_FIELDS for field in proof_missing)) or (len(set(proof_missing)) != len(proof_missing)):
        return ''
    expected_missing = list(proof_missing)
    expected_spec_status = {'bound': 'checked_no_static_declaration', 'no_governing_spec': 'no_governing_spec', 'ambiguous': 'ambiguous'}.get(str(governing_spec_status or ''))
    if expected_spec_status is None:
        return ''
    if str(proof.get('spec_status') or '') != expected_spec_status:
        return ''
    expected_defect_status = {'not_queried': 'not_queried', 'no_ticket_reference': 'no_ticket_reference', 'missing': 'checked_no_defect_spec', 'candidate_only': 'checked_no_claimable_declaration', 'resolved': 'checked_no_applicable_declaration', 'ambiguous': 'ambiguous', 'resolved_absent': 'resolved_absent'}.get(str(defect_spec_status or ''))
    if expected_defect_status is None:
        return ''
    if str(proof.get('defect_spec_status') or '') != expected_defect_status:
        return ''
    expected_receipt_sha = str(defect_spec_receipt_sha256 or '')
    supplied_receipt_sha = str(proof.get('defect_spec_receipt_sha256') or '')
    if expected_defect_status in {'not_queried', 'no_ticket_reference', 'ambiguous', 'resolved_absent'}:
        if supplied_receipt_sha:
            return ''
    elif not _SHA256_RE.fullmatch(expected_receipt_sha) or supplied_receipt_sha != expected_receipt_sha:
        return ''
    actual_missing = _case_missing_fields(case)
    if actual_missing != expected_missing:
        return ''
    if mindmap_text is not None:
        source_missing = _source_missing_fields(case, mindmap_text)
        if source_missing != actual_missing:
            return ''
    return '人工脑图和规格书都没写全描述、步骤和预期'

def _source_missing_fields(case: dict[str, Any], mindmap_text: str) -> list[str]:
    autoid = str(case.get('autoid') or '')
    anchors = _mindmap_anchor_map(mindmap_text).get(autoid) or {}
    if not anchors:
        return list(_SCENARIO2_SOURCE_FIELDS)
    present = {'intent': bool(anchors.get('title')), 'steps': bool(anchors.get('__step_text__')), 'expectation': any((key.startswith('expectation:') for key in anchors))}
    return [f for f in _SCENARIO2_SOURCE_FIELDS if not present[f]]

def _valid_origin(value: str) -> bool:
    text = str(value or '').strip()
    return bool(text == 'title' or _ORIGIN_STEP_RE.fullmatch(text) or _ORIGIN_EXPECT_RE.fullmatch(text) or _ORIGIN_SPEC_RE.fullmatch(text) or _ORIGIN_DEFECT_SPEC_RE.fullmatch(text))

def _norm_ws(s: str) -> str:
    return re.sub('\\s+', ' ', str(s or '')).strip()

def _locator_semantic_text(text: str, origin: str, *, strip_trailing_binding: bool=True) -> str:
    normalized = _norm_ws(text)
    origin_text = str(origin or '').strip()
    match = _ORIGIN_EXPECT_RE.fullmatch(origin_text) or _ORIGIN_STEP_RE.fullmatch(origin_text)
    if match is None:
        return normalized
    label = re.escape(match.group(1))
    prefix = re.compile(f'^\\s*(?:\\[{label}\\]|{label}[.、:：)）])\\s*')
    semantic = prefix.sub('', normalized, count=1)
    if strip_trailing_binding and _ORIGIN_STEP_RE.fullmatch(origin_text):
        semantic = re.sub(f'\\s*\\[({_LOCATOR_TOKEN})\\]\\s*$', '', semantic, count=1)
    return _norm_ws(semantic)

def _source_atom_forms(raw_value: str, origin: str) -> list[str]:
    out: list[str] = []

    def _add(text: str) -> None:
        for form in (_norm_ws(text), _locator_semantic_text(text, origin, strip_trailing_binding=False), _locator_semantic_text(text, origin)):
            if form and form not in out:
                out.append(form)
    for value in _verbatim_candidates(raw_value):
        _add(value)
    if '\n' in str(raw_value):
        for line in str(raw_value).splitlines():
            _add(line)
    return out
_WS_RUN_RE = re.compile('\\s+')

def _whitespace_tolerant_pattern(quote: str) -> re.Pattern | None:
    parts = [re.escape(seg) for seg in _WS_RUN_RE.split(quote) if seg]
    if not parts:
        return None
    try:
        return re.compile('\\s+'.join(parts))
    except re.error:
        return None

def ground_source_span(source_text: str, mindmap_text: str, *, origin: str='') -> dict | None:
    quote = str(source_text or '')
    text = str(mindmap_text or '')
    if not quote.strip() or not text:
        return None

    def _locate(needle: str, *, prefix: int, suffix: int, how: str) -> dict | None:
        index = text.find(needle)
        if index >= 0:
            return {'start': index, 'end': index + len(needle), 'trimmed_prefix_len': prefix, 'trimmed_suffix_len': suffix, 'basis': 'mindmap_text_chars', 'match': how}
        pattern = _whitespace_tolerant_pattern(needle)
        found = pattern.search(text) if pattern is not None else None
        if found is None:
            return None
        return {'start': found.start(), 'end': found.end(), 'trimmed_prefix_len': prefix, 'trimmed_suffix_len': suffix, 'basis': 'mindmap_text_chars', 'match': f'{how}:whitespace_tolerant'}
    span = _locate(quote, prefix=0, suffix=0, how='verbatim')
    if span is not None:
        return span
    semantic = _locator_semantic_text(quote, origin)
    if semantic and semantic != quote:
        head, _, tail = quote.partition(semantic)
        return _locate(semantic, prefix=len(head), suffix=len(tail), how='locator_stripped')
    return None

def source_span_shadow(data: object, mindmap_text: str) -> list[dict]:
    if not isinstance(data, dict):
        return []
    text = str(mindmap_text or '')
    if not text:
        return []
    out: list[dict] = []
    for case in data.get('cases') or []:
        if not isinstance(case, dict):
            continue
        autoid = str(case.get('autoid') or '')
        origins = case.get('origin') if isinstance(case.get('origin'), dict) else {}
        for field, raw in (('intent', case.get('contract', {}).get('intent') if isinstance(case.get('contract'), dict) else None), ('expectation', case.get('contract', {}).get('expectation') if isinstance(case.get('contract'), dict) else None)):
            if not isinstance(raw, str) or not raw.strip():
                continue
            origin = str(origins.get(field) or '')
            forms = _source_atom_forms(raw, origin)
            form_ok = any((form and form in _norm_ws(text) for form in forms))
            span = ground_source_span(raw, text, origin=origin)
            if form_ok and span is None:
                out.append({'autoid': autoid, 'field': field, 'origin': origin, 'divergence': 'form_set_ok_span_missing'})
            elif span is not None and (not form_ok):
                out.append({'autoid': autoid, 'field': field, 'origin': origin, 'divergence': 'span_found_form_set_rejected', 'source_span': [span['start'], span['end']], 'match': span['match']})
    return out

def _assertion_source_forms(raw_value: str, origin: str) -> list[str]:
    out: list[str] = []
    for value in _verbatim_candidates(raw_value):
        semantic = _locator_semantic_text(value, origin)
        if semantic and semantic not in out:
            out.append(semantic)
    return out

def _spec_sentence_forms(raw_value: str) -> list[str]:
    out: list[str] = []
    for value in _verbatim_candidates(raw_value):
        stripped = _norm_ws(re.sub('^(?:(?:[-*+]\\s+)|(?:#{1,6}\\s+)|(?:>\\s+)|(?:\\d+[.、)）]\\s+))+', '', value))
        for form in (value, stripped):
            if form and form not in out:
                out.append(form)
    return out

def _verbatim_candidates(raw_value: str) -> list[str]:
    out = [_norm_ws(raw_value)]
    escaped = json.dumps(raw_value, ensure_ascii=False)[1:-1]
    if escaped != raw_value:
        out.append(_norm_ws(escaped))
    return [c for c in out if c]

def verbatim_candidates(raw_value: str) -> list[str]:
    return _verbatim_candidates(raw_value)

def _spec_origin_resolved_span(origin: str, *, governing_spec: str | None, spec_text: str | None) -> tuple[list[str], int, int] | None:
    match = _ORIGIN_SPEC_RE.fullmatch(str(origin or ''))
    if match is None or spec_text is None or match.group(1) != governing_spec:
        return None
    span = match.group(2).split('-', 1)
    start = int(span[0])
    end = int(span[-1])
    lines = spec_text.splitlines()
    if start < 1 or end < start or end > len(lines):
        return None
    return (lines, start, end)

def _spec_anchor_span_text(origin: str, *, governing_spec: str | None, spec_text: str | None) -> str | None:
    resolved = _spec_origin_resolved_span(origin, governing_spec=governing_spec, spec_text=spec_text)
    if resolved is None:
        return None
    lines, start, end = resolved
    return '\n'.join(lines[start - 1:end])

def _spec_anchor_text(origin: str, *, governing_spec: str | None, spec_text: str | None) -> str | None:
    raw = _spec_anchor_span_text(origin, governing_spec=governing_spec, spec_text=spec_text)
    return None if raw is None else _norm_ws(raw)

def _defect_spec_anchor_raw_text(origin: str, *, defect_spec_receipt: dict[str, Any] | None) -> str | None:
    match = _ORIGIN_DEFECT_SPEC_RE.fullmatch(str(origin or ''))
    if match is None or not isinstance(defect_spec_receipt, dict):
        return None
    ticket = defect_spec_receipt.get('ticket')
    projection = defect_spec_receipt.get('projection')
    if not accepts_schema(defect_spec_receipt.get('schema'), 'ist.defect-spec-receipt') or defect_spec_receipt.get('status') != 'resolved' or defect_spec_receipt.get('eligible') is not True or (defect_spec_receipt.get('authority_group') != 'spec') or (not isinstance(ticket, dict)) or (not isinstance(projection, dict)) or (str(ticket.get('backend') or '').lower() != match.group(1).lower()) or (str(ticket.get('ticket_id') or '').upper() != match.group(2).upper()):
        return None
    return str(projection.get(match.group(3).lower()) or '')

def _defect_spec_anchor_text(origin: str, *, defect_spec_receipt: dict[str, Any] | None) -> str | None:
    raw = _defect_spec_anchor_raw_text(origin, defect_spec_receipt=defect_spec_receipt)
    return None if raw is None else _norm_ws(raw) or None

def _external_origin_forms(origin: str, *, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None) -> list[str] | None:
    if str(origin or '').startswith('spec:'):
        side = _spec_anchor_text(origin, governing_spec=governing_spec, spec_text=spec_text)
        return list(_spec_sentence_forms(side)) if side is not None else []
    if str(origin or '').startswith('defect:'):
        side = _defect_spec_anchor_text(origin, defect_spec_receipt=defect_spec_receipt)
        return _verbatim_candidates(side) if side is not None else []
    return None

def _external_origin_raw_text(origin: str, *, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None) -> str:
    if str(origin or '').startswith('spec:'):
        return _spec_anchor_span_text(origin, governing_spec=governing_spec, spec_text=spec_text) or ''
    if str(origin or '').startswith('defect:'):
        return _defect_spec_anchor_raw_text(origin, defect_spec_receipt=defect_spec_receipt) or ''
    return ''

def _node_text(node: dict[str, Any]) -> str:
    data = node.get('data') if isinstance(node.get('data'), dict) else {}
    return str(data.get('text') or node.get('text') or '')

def _node_autoid(node: dict[str, Any]) -> str:
    data = node.get('data') if isinstance(node.get('data'), dict) else {}
    return str(data.get('autoid') or node.get('autoid') or '').strip()

def _node_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [child for child in node.get('children') or [] if isinstance(child, dict)]

def _numbered_atoms(text: str) -> dict[str, str]:
    pattern = re.compile(f'(?m)^\\s*\\[?({_LOCATOR_TOKEN})\\]?[.、:：)）]\\s*')
    matches = list(pattern.finditer(str(text or '')))
    out: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        atom = text[match.start():end].strip()
        if atom:
            out[match.group(1)] = atom
    return out

def _action_atoms(text: str) -> dict[str, str]:
    source = str(text or '')
    numbered = _numbered_atoms(source)
    if numbered:
        first = re.search(f'(?m)^\\s*\\[?({_LOCATOR_TOKEN})\\]?[.、:：)）]\\s*', source)
        prefix = source[:first.start()].strip() if first is not None else ''
        if prefix:
            prefix_label = '1' if '1' not in numbered else 'pre1'
            return {prefix_label: prefix, **numbered}
        return numbered
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if len(lines) > 1:
        return {str(index): line for index, line in enumerate(lines, 1)}
    return {'1': source.strip()} if source.strip() else {}

def _bracket_labeled_atoms(text: str) -> dict[str, str]:
    source = str(text or '')
    pattern = re.compile(f'(?m)^\\s*\\[({_LOCATOR_TOKEN})\\]\\s*')
    matches = list(pattern.finditer(source))
    out: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        atom = source[match.start():end].strip()
        if atom:
            out[match.group(1)] = atom
    return out

def _expectation_step_anchor(label: str) -> str:
    return f'__expectation_step__:{label}'

@lru_cache(maxsize=2)
def _cached_mindmap_anchor_map(mindmap_text: str) -> dict[str, dict[str, list[str]]]:
    return _mindmap_anchor_map(mindmap_text)

def _semantic_whitespace(text: Any) -> str:
    return ' '.join(str(text or '').split())
AUTHORED_STEP_ANCHOR_CN = '作者步骤'
_AUTHORED_STEP_ANCHOR_TAIL_RE = re.compile(f'；{AUTHORED_STEP_ANCHOR_CN}[0-9]+$')

def authored_step_anchor_suffix(authored_step: Any) -> str:
    """``text_anchor`` 上的作者步号段；步号不知道就是空串。

    卡面与判据谓词说的是同一件事，所以两边取同一个值：谓词读
    ``normalized_claim.authored_step``，卡面读同一个字段生成这一段。取不到时这一段
    不写——写一个猜的步号比不写更坏（`expectations_by_step.n` 对 origin=
    ``expectation:N`` 的行大多恒为 1，卡面照它写就是把多步案一律说成第 1 步）。
    """
    if isinstance(authored_step, bool) or not isinstance(authored_step, int):
        return ''
    return f'；{AUTHORED_STEP_ANCHOR_CN}{authored_step}' if authored_step >= 1 else ''

def with_authored_step_anchor(text_anchor: Any, authored_step: Any) -> str:
    """把 ``text_anchor`` 末尾的作者步号段换成 ``authored_step`` 那一段。

    幂等：已经带着步号段时先摘掉再贴，二次归一不会把同一段贴两遍。
    """
    base = _AUTHORED_STEP_ANCHOR_TAIL_RE.sub('', str(text_anchor or ''))
    return base + authored_step_anchor_suffix(authored_step)
AUTHORED_STEP_CAUSE_ORIGIN = 'origin_not_a_step_locator'
AUTHORED_STEP_CAUSE_ANCHORS = 'anchor_rows_unbalanced'
AUTHORED_STEP_CAUSE_TEXT = 'claim_text_not_uniquely_bound'
AUTHORED_STEP_UNKNOWN_CAUSES = frozenset({AUTHORED_STEP_CAUSE_ORIGIN, AUTHORED_STEP_CAUSE_ANCHORS, AUTHORED_STEP_CAUSE_TEXT})

def authored_expectation_step_binding(mindmap_text: str, *, autoid: str, origin: str, source_text: str) -> tuple[int | None, str | None]:
    """作者把这条期望挂在了哪一步，以及绑不到时是哪一种绑不到。

    返回 ``(步号, 成因码)``：绑到了就是 ``(N, None)``，绑不到就是 ``(None, 成因码)``，
    成因码取自 :data:`AUTHORED_STEP_UNKNOWN_CAUSES` 三值闭集。三种成因的修法完全不同
    ——第一种要改行的 ``origin``（或它根本不是脑图内部来源），第二种要改脑图结构，
    第三种是两条期望原文在同一标签下互相盖住。折成同一个「不知道」时，下游看不出该动哪里。

    事实源是 :func:`_mindmap_anchor_map` 已经算好的 ``__expectation_step__`` 锚——
    期望节点所在的那个步骤节点，或步骤原文里带 ``[<标签>]`` 定位符的那一步。同一标签
    下期望原文与步锚逐条并列（一条期望一条锚），靠原文把这一条认回它自己那条锚；
    条数对不上、或原文同时落在指向不同步的几条锚上，都按「不知道」返回，不挑一条凑数。
    分句提交的主张是整条期望原文的子串，所以按包含关系认。

    **``semantic_key`` / ``expectation_id`` 的步号段不是步指针**：那两个是身份字段，
    ``origin=expectation:<数字>`` 的行里数字是期望自己的序号，不是它说的那一步。
    """
    text = str(origin or '').strip()
    step_match = _ORIGIN_STEP_RE.fullmatch(text)
    if step_match is not None:
        digits = step_match.group(1)
        if digits.isdigit() and int(digits) >= 1:
            return (int(digits), None)
        return (None, AUTHORED_STEP_CAUSE_ORIGIN)
    label_match = _ORIGIN_EXPECT_RE.fullmatch(text)
    if label_match is None:
        return (None, AUTHORED_STEP_CAUSE_ORIGIN)
    case_anchors = _cached_mindmap_anchor_map(str(mindmap_text or '')).get(str(autoid or '')) or {}
    atoms = [_semantic_whitespace(item) for item in case_anchors.get(text) or []]
    steps = [str(item) for item in case_anchors.get(_expectation_step_anchor(label_match.group(1))) or []]
    if not steps or len(steps) != len(atoms):
        return (None, AUTHORED_STEP_CAUSE_ANCHORS)
    needle = _semantic_whitespace(source_text)
    bound = {steps[index] for index, atom in enumerate(atoms) if needle and needle in atom}
    if len(bound) != 1:
        return (None, AUTHORED_STEP_CAUSE_TEXT)
    only = bound.pop()
    if only.isdigit() and int(only) >= 1:
        return (int(only), None)
    return (None, AUTHORED_STEP_CAUSE_TEXT)

def authored_expectation_step(mindmap_text: str, *, autoid: str, origin: str, source_text: str) -> int | None:
    """作者把这条期望挂在了哪一步；密封脑图没绑到唯一一步就返回 ``None``。

    只要步号、不要成因码时用这个；成因码见
    :func:`authored_expectation_step_binding`。
    """
    return authored_expectation_step_binding(mindmap_text, autoid=autoid, origin=origin, source_text=source_text)[0]

def _mindmap_anchor_map(mindmap_text: str) -> dict[str, dict[str, list[str]]]:
    try:
        roots = json.loads(str(mindmap_text or '').lstrip('\ufeff\uffff'))
    except (TypeError, ValueError):
        return {}
    if isinstance(roots, dict):
        roots = [roots]
    if not isinstance(roots, list):
        return {}
    out: dict[str, dict[str, list[str]]] = {}

    def add(aid: str, origin: str, value: str) -> None:
        if aid and value:
            out.setdefault(aid, {}).setdefault(origin, []).append(value)

    def add_step(aid: str, label: str, value: str) -> None:
        add(aid, f'step:{label}', value)
        add(aid, '__step_label__', label)
        add(aid, '__step_text__', value)

    def process_case(case: dict[str, Any], orphan_notes: list[str], group_path: list[str]) -> None:
        aid = _node_autoid(case)
        title = _node_text(case)
        add(aid, 'title', title)
        add(aid, '__case_text__', title)
        for group in group_path:
            add(aid, '__group_path__', group)
        children = _node_children(case)
        leaf_expectation_layout = len(children) == 1 and (not _node_children(children[0])) and (not _numbered_atoms(_node_text(children[0])))
        if leaf_expectation_layout:
            step_atoms = _action_atoms(title)
            for label, atom in step_atoms.items():
                add_step(aid, label, atom)
            expectation_text = _node_text(children[0])
            add(aid, '__case_text__', expectation_text)
            expectation_atoms = _bracket_labeled_atoms(expectation_text)
            if not expectation_atoms:
                expectation_atoms = {'1': expectation_text}
            for label, atom in expectation_atoms.items():
                add(aid, f'expectation:{label}', atom)
                linked_steps = [step_label for step_label, step_atom in step_atoms.items() if re.search(f'\\[{re.escape(label)}\\]', step_atom)]
                if not linked_steps and len(step_atoms) == 1:
                    linked_steps = list(step_atoms)
                for step_label in linked_steps:
                    add(aid, _expectation_step_anchor(label), step_label)
            step_nodes: list[dict[str, Any]] = []
        else:
            step_nodes = children
        for index, step_node in enumerate(step_nodes, 1):
            step_text = _node_text(step_node)
            add(aid, '__case_text__', step_text)
            numbered_atoms = _numbered_atoms(step_text)
            atoms = _action_atoms(step_text) if numbered_atoms else {}
            parent_step_labels = list(atoms) or [str(index)]
            if atoms:
                for label, atom in atoms.items():
                    add_step(aid, label, atom)
            else:
                add_step(aid, str(index), step_text)
            for exp_index, exp_node in enumerate(_node_children(step_node), 1):
                exp_text = _node_text(exp_node)
                add(aid, '__case_text__', exp_text)
                exp_atoms = _numbered_atoms(exp_text)
                if exp_atoms:
                    for label, atom in exp_atoms.items():
                        add(aid, f'expectation:{label}', atom)
                        linked_steps = [step_label for step_label, step_atom in atoms.items() if re.search(f'\\[{re.escape(label)}\\]', step_atom)]
                        if not linked_steps and len(parent_step_labels) == 1:
                            linked_steps = parent_step_labels
                        for parent_label in linked_steps:
                            add(aid, _expectation_step_anchor(label), parent_label)
                else:
                    label_match = re.match(f'^\\s*\\[({_LOCATOR_TOKEN})\\]', exp_text)
                    label = label_match.group(1) if label_match else str(exp_index)
                    add(aid, f'expectation:{label}', exp_text)
                    linked_steps = [step_label for step_label, step_atom in atoms.items() if re.search(f'\\[{re.escape(label)}\\]', step_atom)]
                    if not linked_steps and len(parent_step_labels) == 1:
                        linked_steps = parent_step_labels
                    for parent_label in linked_steps:
                        add(aid, _expectation_step_anchor(label), parent_label)
        for index, note in enumerate(orphan_notes, 1):
            add(aid, f'orphan_note:{index}', note)

    def walk(parent: dict[str, Any], group_path: list[str], *, include_parent: bool=True) -> None:
        parent_text = _node_text(parent).strip()
        current_path = group_path + [parent_text] if include_parent and parent_text else list(group_path)
        children = _node_children(parent)
        cases = [child for child in children if _node_autoid(child)]
        if cases:
            orphan_notes = [_node_text(child) for child in children if not _node_autoid(child) and _node_text(child)]
            previous_sibling = ''
            for case in cases:
                process_case(case, orphan_notes, current_path)
                aid = _node_autoid(case)
                if previous_sibling:
                    add(aid, '__previous_sibling__', previous_sibling)
                previous_sibling = aid
        for child in children:
            if not _node_autoid(child):
                walk(child, current_path)
    for root in roots:
        if isinstance(root, dict):
            if _node_autoid(root):
                process_case(root, [], [])
            else:
                walk(root, [], include_parent=True)
    return out

def public_case_locators(case_anchors: dict[str, list[str]]) -> list[str]:
    if not isinstance(case_anchors, dict):
        return []
    return sorted({locator for locator in case_anchors if not locator.startswith('__')})

def _verbatim_duplicate_disclosures(mindmap_text: str) -> list[dict[str, Any]]:
    by_text: dict[tuple[str, ...], list[str]] = {}
    for aid, case_anchors in _mindmap_anchor_map(mindmap_text).items():
        case_text = tuple(case_anchors.get('__case_text__') or [])
        if case_text:
            by_text.setdefault(case_text, []).append(aid)
    groups = sorted((sorted(aids) for aids in by_text.values() if len(aids) > 1))
    disclosures: list[dict[str, Any]] = []
    for aids in groups:
        for first, second in zip(aids, aids[1:]):
            disclosures.append({'autoid': first, 'related_autoid': second, 'code': 'verbatim_duplicate_disclosure', 'message': f'用例 {first} 与 {second} 的标题、步骤、预期逐字完全相同；已按原文各出卡，不去重、不合并，请人工确认是否为有意重复', 'reason_code': 'verbatim_duplicate', 'fallback_allowed': False})
    return disclosures

def closed_mindmap_case_autoids(mindmap_text: str) -> tuple[str, ...]:
    anchors = _mindmap_anchor_map(mindmap_text)
    autoids = tuple((str(aid) for aid in anchors if re.fullmatch('[0-9]{18}', str(aid or ''))))
    if not autoids or len(autoids) != len(anchors):
        raise MachineMindmapError('trusted mindmap source has no closed 18-digit autoid set')
    return autoids

def closed_mindmap_command_heads(mindmap_text: str, *, autoids: Iterable[str] | None=None) -> tuple[str, ...]:
    anchors = _mindmap_anchor_map(mindmap_text)
    selected = None if autoids is None else {str(aid) for aid in autoids}
    segments: set[str] = set()
    for aid, case_anchors in anchors.items():
        if selected is not None and aid not in selected:
            continue
        for locator, atoms in case_anchors.items():
            if locator.startswith('__'):
                continue
            for atom in atoms:
                for line in str(atom).splitlines():
                    for segment in re.split('[；;。]', line):
                        segment = re.sub('^\\s*\\d+[.、．]?\\s*', '', ' '.join(segment.split()))
                        if segment and any((ch.isascii() and ch.isalpha() for ch in segment)):
                            segments.add(segment)
    return tuple(sorted(segments))

def _resolved_side_quote_bytes(locator: str, *, side: str, autoid: str, mindmap_text: str, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None) -> str | None:
    locator = str(locator or '').strip()
    if not locator:
        return ''
    if side == 'spec':
        raw = _external_origin_raw_text(locator, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
        return raw if raw else None
    case_anchors = _mindmap_anchor_map(mindmap_text).get(autoid, {})
    if locator not in public_case_locators(case_anchors):
        return None
    values = case_anchors.get(locator) or []
    if not values or not str(values[0]):
        return None
    return str(values[0])

def consistency_source_atoms_for_brief(mindmap_text: str) -> dict[str, Any]:
    anchors = _mindmap_anchor_map(mindmap_text)
    out: dict[str, Any] = {}
    for aid, case_anchors in anchors.items():
        locators: dict[str, str] = {}
        for locator in public_case_locators(case_anchors):
            values = case_anchors.get(locator) or []
            if values and str(values[0]):
                locators[locator] = str(values[0])
        if locators:
            out[str(aid)] = {'case_locators': locators}
    return out

def stamp_consistency_quotes(value: dict[str, Any], autoid: str, *, mindmap_text: str, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None, cross_check: bool, mutate: bool=True, spec_optional: bool | None=None, case_optional: bool | None=None) -> str:
    for field in ('spec_locator', 'case_locator'):
        if field in value and (not isinstance(value.get(field), str)):
            return 'consistency_conclusion_invalid'
    spec_locator = str(value.get('spec_locator') or '').strip()
    case_locator = str(value.get('case_locator') or '').strip()
    has_spec_surface = bool(str(spec_text or '').strip()) or isinstance(defect_spec_receipt, dict)
    if spec_optional is None:
        spec_optional = not spec_locator or not has_spec_surface
    if case_optional is None:
        case_optional = not case_locator
    resolve_kw = dict(autoid=autoid, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
    stamped_premises: list[dict[str, Any]] | None = None
    premises = value.get('premises')
    if isinstance(premises, list):
        stamped_premises = []
        for index, premise in enumerate(premises):
            if not isinstance(premise, dict):
                return premise_stamp_failure(index, 'shape_invalid')
            extra = set(premise) - {'text', 'origin', 'locator', 'source_sha256'}
            if extra:
                return premise_stamp_failure(index, 'shape_invalid')
            origin = str(premise.get('origin') or '')
            locator = str(premise.get('locator') or '').strip()
            if origin not in {'spec', 'case'} or not locator:
                return premise_stamp_failure(index, 'shape_invalid')
            text = premise.get('text')
            if text is None:
                text = ''
            if not isinstance(text, str):
                return premise_stamp_failure(index, 'shape_invalid')
            side = 'spec' if origin == 'spec' else 'case'
            raw = _resolved_side_quote_bytes(locator, side=side, **resolve_kw)
            if raw is None:
                if origin == 'spec' and (not has_spec_surface):
                    stamped_premises.append(dict(premise))
                    continue
                return premise_stamp_failure(index, 'locator_unresolved')
            if text.strip() and cross_check and (text != raw):
                return premise_stamp_failure(index, 'text_drift')
            stamped = dict(premise)
            stamped['text'] = raw
            stamped_premises.append(stamped)
    stamped_surfaces: list[dict[str, Any]] | None = None
    conflict = value.get(AUTHORED_CONFLICT_KEY)
    if isinstance(conflict, dict) and isinstance(conflict.get('surfaces'), list):
        stamped_surfaces = []
        for index, surface in enumerate(conflict['surfaces']):
            if not isinstance(surface, dict):
                return conflict_surface_stamp_failure(index, 'invalid')
            locator = str(surface.get('locator') or '').strip()
            raw = _resolved_side_quote_bytes(locator, side='case', **resolve_kw)
            if not raw:
                return conflict_surface_stamp_failure(index, 'locator_unresolved')
            caller = surface.get('quote')
            if caller is None:
                caller = ''
            if not isinstance(caller, str):
                return conflict_surface_stamp_failure(index, 'invalid')
            if caller.strip() and cross_check and (caller != raw):
                return conflict_surface_stamp_failure(index, 'text_drift')
            stamped = dict(surface)
            stamped['quote'] = raw
            stamped_surfaces.append(stamped)
    spec_raw = _resolved_side_quote_bytes(spec_locator, side='spec', **resolve_kw)
    if spec_locator:
        if spec_raw is None:
            if not spec_optional:
                return 'consistency_spec_locator_unresolved'
        else:
            caller = value.get('spec_quote')
            if caller is None:
                caller = ''
            if not isinstance(caller, str):
                return 'consistency_conclusion_invalid'
            if caller.strip() and cross_check and (caller != spec_raw):
                return 'consistency_spec_quote_drift'
    case_raw = _resolved_side_quote_bytes(case_locator, side='case', **resolve_kw)
    if case_locator:
        if case_raw is None:
            if not case_optional:
                return 'consistency_case_locator_unresolved'
        else:
            caller = value.get('case_quote')
            if caller is None:
                caller = ''
            if not isinstance(caller, str):
                return 'consistency_conclusion_invalid'
            if caller.strip() and cross_check and (caller != case_raw):
                return 'consistency_case_quote_drift'
    if not mutate:
        return ''
    if spec_locator and spec_raw:
        value['spec_quote'] = spec_raw
    elif 'spec_quote' not in value or value.get('spec_quote') is None:
        value['spec_quote'] = str(value.get('spec_quote') or '')
    if case_locator and case_raw:
        value['case_quote'] = case_raw
    elif 'case_quote' not in value or value.get('case_quote') is None:
        value['case_quote'] = str(value.get('case_quote') or '')
    if stamped_premises is not None:
        value['premises'] = stamped_premises
    if stamped_surfaces is not None:
        value[AUTHORED_CONFLICT_KEY] = {**value[AUTHORED_CONFLICT_KEY], 'surfaces': stamped_surfaces}
    return ''

def resolve_consistency_evidence(case: dict[str, Any], proposal: dict[str, Any], *, mindmap_text: str, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None) -> tuple[str, str, dict[str, Any] | None]:
    if not isinstance(proposal, dict) or set(proposal) != _CONSISTENCY_MATERIAL_KEYS or proposal.get('schema') != _CONSISTENCY_DRAFT_SCHEMA:
        return ('invalid', 'consistency_schema_keys_invalid', None)
    premises = proposal.get('premises')
    if not isinstance(premises, list):
        return ('invalid', 'consistency_conflict_premises_missing', None)
    autoid = str(case.get('autoid') or '')
    working: dict[str, Any] = dict(proposal)
    working['premises'] = [dict(item) if isinstance(item, dict) else item for item in premises]
    for index, premise in enumerate(working['premises']):
        if not isinstance(premise, dict):
            return ('invalid', premise_stamp_failure(index, 'shape_invalid'), None)
        extra = set(premise) - {'text', 'origin', 'locator'}
        if extra or premise.get('origin') not in {'spec', 'case'}:
            return ('invalid', premise_stamp_failure(index, 'shape_invalid'), None)
        if 'text' in premise and (not isinstance(premise.get('text'), str)):
            return ('invalid', premise_stamp_failure(index, 'shape_invalid'), None)
        if not isinstance(premise.get('locator'), str) or not str(premise.get('locator') or '').strip():
            return ('invalid', premise_stamp_failure(index, 'shape_invalid'), None)
    stamp_failure = stamp_consistency_quotes(working, autoid, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt, cross_check=True, spec_optional=False, case_optional=False)
    if stamp_failure:
        return ('invalid', stamp_failure, None)
    accepted_premises: list[dict[str, str]] = []
    for premise in working['premises']:
        raw = str(premise.get('text') or '')
        accepted_premises.append({'text': raw, 'origin': str(premise['origin']), 'locator': str(premise['locator']).strip(), 'source_sha256': sha256_bytes(_norm_ws(raw).encode('utf-8'))})
    accepted = {**working, 'schema': _CONSISTENCY_MATERIAL_SCHEMA, 'premises': accepted_premises}
    state, reason = consistency_evidence_status(case, accepted, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
    return (state, reason, accepted if state != 'invalid' else None)

def quote_closure_failure(autoid: str, *, spec_locator: str, spec_quote: str, case_locator: str, case_quote: str, mindmap_text: str, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None, spec_optional: bool=False, case_optional: bool=False) -> str:
    return stamp_consistency_quotes({'spec_locator': spec_locator, 'spec_quote': spec_quote, 'case_locator': case_locator, 'case_quote': case_quote}, autoid, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt, cross_check=True, mutate=False, spec_optional=spec_optional, case_optional=case_optional)

def recompose_consistency_anchor_failure(value: object, autoid: str, *, mindmap_text: str, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None) -> str:
    if not isinstance(value, dict):
        return ''
    return stamp_consistency_quotes(value, autoid, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt, cross_check=True, mutate=False)

def consistency_evidence_status(case: dict[str, Any], proposal: dict[str, Any], *, mindmap_text: str, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None) -> tuple[str, str]:
    if not isinstance(proposal, dict) or set(proposal) != _CONSISTENCY_MATERIAL_KEYS:
        return ('invalid', 'consistency_schema_keys_invalid')
    autoid = str(case.get('autoid') or '')
    if proposal.get('schema') != _CONSISTENCY_MATERIAL_SCHEMA or str(proposal.get('autoid') or '') != autoid or proposal.get('verdict') not in {'consistent', 'conflict'}:
        return ('invalid', 'consistency_identity_or_verdict_invalid')
    stamp_failure = stamp_consistency_quotes(proposal, autoid, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt, cross_check=True, spec_optional=False, case_optional=False)
    if stamp_failure:
        return ('invalid', stamp_failure)
    for key in ('schema', 'autoid', 'verdict', 'spec_quote', 'case_quote', 'spec_locator', 'case_locator', 'incompatibility'):
        value = proposal.get(key)
        if not isinstance(value, str) or not value.strip():
            return ('invalid', 'consistency_text_field_invalid')
    premises = proposal.get('premises')
    if not isinstance(premises, list) or (proposal.get('verdict') == 'conflict' and (not premises)):
        return ('invalid', 'consistency_conflict_premises_missing')
    for index, premise in enumerate(premises):
        if not isinstance(premise, dict) or set(premise) != {'text', 'origin', 'locator', 'source_sha256'} or premise.get('origin') not in {'spec', 'case'} or (not isinstance(premise.get('text'), str)) or (not str(premise.get('text') or '').strip()) or (not isinstance(premise.get('locator'), str)) or (not str(premise.get('locator') or '').strip()) or (not isinstance(premise.get('source_sha256'), str)) or (_SHA256_RE.fullmatch(str(premise.get('source_sha256') or '')) is None):
            return ('invalid', premise_stamp_failure(index, 'shape_invalid'))
        expected_digest = sha256_bytes(_norm_ws(str(premise['text'])).encode('utf-8'))
        if str(premise['source_sha256']) != expected_digest:
            return ('invalid', premise_stamp_failure(index, 'digest_invalid'))
    verdict = str(proposal['verdict'])
    if 'consistency' in case:
        coverage_failure = clause_coverage_failure(str(proposal['spec_quote']), proposal.get('spec_clauses'))
        if coverage_failure:
            return ('invalid', coverage_failure)
        return (verdict, '')
    clause_failure = _scenario1_clause_failure(str(proposal['spec_quote']), proposal.get('spec_clauses'))
    if verdict == 'conflict':
        if clause_failure:
            return ('invalid', clause_failure)
    elif clause_failure != 'scenario1_clause_consistent_branch':
        return ('invalid', 'consistency_clause_support_missing')
    return (verdict, '')

def fill_mechanical_fields(data: dict[str, Any], mindmap_text: str) -> list[str]:
    anchors = _mindmap_anchor_map(mindmap_text)
    repaired: list[str] = []
    for case in data.get('cases') or []:
        if not isinstance(case, dict):
            continue
        autoid = str(case.get('autoid') or '')
        case_anchors = anchors.get(autoid)
        if not case_anchors:
            continue
        before = json.dumps([case.get('group_path'), case.get('steps'), case.get('expectations_by_step'), case.get('origin')], ensure_ascii=False, sort_keys=True, default=str)
        case['group_path'] = [value for value in case_anchors.get('__group_path__', []) if str(value).strip()]
        case['steps'] = [{'n': label, 'text': text} for label, text in zip(case_anchors.get('__step_label__', []), case_anchors.get('__step_text__', []))]
        authored: list[tuple[str, str, list[str]]] = []
        for anchor_origin, values in case_anchors.items():
            match = _ORIGIN_EXPECT_RE.fullmatch(anchor_origin)
            if match is None:
                continue
            label = match.group(1)
            allowed_steps = [label] if label.isdigit() else [str(x) for x in case_anchors.get(_expectation_step_anchor(label)) or []]
            for value in values:
                authored.append((anchor_origin, value, allowed_steps))
        if authored:
            machine = [item for item in case.get('expectations_by_step') or [] if isinstance(item, dict)]
            prior_author = [item for item in machine if _ORIGIN_EXPECT_RE.fullmatch(str(item.get('origin') or '').strip())]
            external = [item for item in machine if item not in prior_author]
            rebuilt: list[dict[str, Any]] = []
            for index, (anchor_origin, value, allowed_steps) in enumerate(authored):
                step = allowed_steps[index] if index < len(allowed_steps) else allowed_steps[0] if allowed_steps else ''
                carried = dict(prior_author[index]) if len(prior_author) == len(authored) else {}
                carried.update({'n': step, 'origin': anchor_origin, 'text': value})
                carried.setdefault('assertion', None)
                rebuilt.append(carried)
            case['expectations_by_step'] = rebuilt + external
        origin = case.get('origin')
        contract = case.get('contract')
        if isinstance(origin, dict) and isinstance(contract, dict):
            for field in ('intent', 'verification_method', 'expectation'):
                declared = str(origin.get(field) or '')
                if declared.startswith(('spec:', 'defect:')):
                    continue
                candidates = _verbatim_candidates(str(contract.get(field) or ''))
                if not candidates:
                    continue
                if any((candidate == form for candidate in candidates for value in case_anchors.get(declared) or [] for form in _source_atom_forms(value, declared))):
                    continue
                hits = [anchor_origin for anchor_origin in public_case_locators(case_anchors) if any((candidate == form for candidate in candidates for value in case_anchors.get(anchor_origin) or [] for form in _source_atom_forms(value, anchor_origin)))]
                if len(set(hits)) == 1:
                    origin[field] = hits[0]
        after = json.dumps([case.get('group_path'), case.get('steps'), case.get('expectations_by_step'), case.get('origin')], ensure_ascii=False, sort_keys=True, default=str)
        declared_status = case.get('source_status')
        derived_status = _derived_source_status(case)
        if declared_status != derived_status:
            case['source_status'] = derived_status
        if before != after or declared_status != derived_status:
            repaired.append(autoid)
    return repaired

def verbatim_failures(data: dict[str, Any], mindmap_text: str, spec_text: str | None, *, governing_spec: str | None=None, governing_spec_status: str | None=None, defect_spec_receipt: dict[str, Any] | None=None, defect_spec_status: str | None=None, defect_spec_receipt_sha256: str | None=None) -> dict[str, list[str]]:
    anchors = _mindmap_anchor_map(mindmap_text)
    accepted_spec = governing_spec
    if accepted_spec is None:
        accepted_spec = str(data.get('governing_spec') or '').strip() or None
    resolved_spec_status = governing_spec_status
    if resolved_spec_status is None and governing_spec is not None:
        resolved_spec_status = 'bound' if governing_spec else 'no_governing_spec'
    bad: dict[str, list[str]] = {}
    for case in data.get('cases') or []:
        if not isinstance(case, dict):
            continue
        autoid = str(case.get('autoid') or '')
        scenario2_unresolved = bool(_scenario2_incomplete_reason(case, governing_spec_status=resolved_spec_status, defect_spec_status=defect_spec_status if defect_spec_status is not None else str(data.get('defect_spec_status') or '') or None, defect_spec_receipt_sha256=defect_spec_receipt_sha256 if defect_spec_receipt_sha256 is not None else str(data.get('defect_spec_receipt_sha256') or '') or None))
        contract = case.get('contract') or {}
        origin = case.get('origin') or {}
        case_anchors = anchors.get(autoid, {})
        authored_groups = [_norm_ws(value) for value in case_anchors.get('__group_path__', [])]
        machine_groups = [_norm_ws(value) for value in case.get('group_path') or [] if _norm_ws(value)]
        if machine_groups != authored_groups:
            bad.setdefault(autoid, []).append('group_path')
        raw_machine_steps = case.get('steps')
        step_labels = list(case_anchors.get('__step_label__', []))
        step_texts = list(case_anchors.get('__step_text__', []))
        authored_steps = list(zip(step_labels, step_texts))
        steps_invalid = not isinstance(raw_machine_steps, list) or len(raw_machine_steps) != len(authored_steps)
        if not steps_invalid:
            for item, (expected_label, expected_text) in zip(raw_machine_steps, authored_steps):
                if not isinstance(item, dict):
                    steps_invalid = True
                    break
                candidates = _verbatim_candidates(str(item.get('text') or ''))
                source_forms = _verbatim_candidates(expected_text)
                if str(item.get('n') or '').strip() != expected_label or not candidates or (not any((candidate == source for candidate in candidates for source in source_forms))):
                    steps_invalid = True
                    break
        if steps_invalid:
            bad.setdefault(autoid, []).append('steps')
        for field in ('intent', 'verification_method', 'expectation'):
            candidates = _verbatim_candidates(str(contract.get(field) or ''))
            if not candidates:
                continue
            field_origin = str(origin.get(field) or '')
            external_forms = _external_origin_forms(field_origin, governing_spec=accepted_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
            anchor_values = case_anchors.get(field_origin) or []
            source_forms = external_forms if external_forms is not None else [form for value in anchor_values for form in _source_atom_forms(value, field_origin)]
            if not source_forms or not any((candidate == source for candidate in candidates for source in source_forms)):
                bad.setdefault(autoid, []).append(field)
        machine_expectations = [item for item in case.get('expectations_by_step') or [] if isinstance(item, dict)]
        authored_expectations: list[tuple[str, str, list[str]]] = []
        for anchor_origin, values in case_anchors.items():
            match = _ORIGIN_EXPECT_RE.fullmatch(anchor_origin)
            if match is None:
                continue
            label = match.group(1)
            allowed_steps = [label] if label.isdigit() else list(case_anchors.get(_expectation_step_anchor(label)) or [])
            for value in values:
                authored_expectations.append((anchor_origin, value, allowed_steps))
        machine_authored_expectations: list[dict[str, Any]] = []
        seen_external = False
        expectation_set_invalid = False
        for item in machine_expectations:
            item_origin = str(item.get('origin') or '').strip()
            if item_origin.startswith(('spec:', 'defect:')):
                seen_external = True
                continue
            if seen_external:
                expectation_set_invalid = True
            if _ORIGIN_EXPECT_RE.fullmatch(item_origin):
                machine_authored_expectations.append(item)
        if len(machine_authored_expectations) != len(authored_expectations):
            expectation_set_invalid = True
        else:
            for item, (expected_origin, source_value, allowed_steps) in zip(machine_authored_expectations, authored_expectations):
                candidates = _verbatim_candidates(str(item.get('text') or ''))
                if str(item.get('origin') or '').strip() != expected_origin or str(item.get('n') or '').strip() not in allowed_steps or (not any((candidate == source for candidate in candidates for source in _source_atom_forms(source_value, expected_origin)))):
                    expectation_set_invalid = True
                    break
        if expectation_set_invalid:
            bad.setdefault(autoid, []).append('expectations_by_step')
        for index, item in enumerate(machine_expectations):
            if not isinstance(item, dict):
                continue
            candidates = _verbatim_candidates(str(item.get('text') or ''))
            if not candidates:
                continue
            item_origin = str(item.get('origin') or '')
            external_forms = _external_origin_forms(item_origin, governing_spec=accepted_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
            anchor_values = case_anchors.get(item_origin) or []
            source_forms = external_forms if external_forms is not None else [form for value in anchor_values for form in _source_atom_forms(value, item_origin)]
            if not source_forms or not any((candidate == source for candidate in candidates for source in source_forms)):
                bad.setdefault(autoid, []).append(f'expectations_by_step[{index}]')
                continue
            assertion = item.get('assertion')
            explicit_unresolved_assertion = 'assertion' in item and assertion is None and (scenario2_unresolved or (_derived_source_status(case) == 'complete' and _derived_typed_assertion_status(case) == 'pending'))
            if not explicit_unresolved_assertion:
                raw_assertion_value = assertion.get('value') if isinstance(assertion, dict) else None
                raw_assertion_operator = assertion.get('operator') if isinstance(assertion, dict) else None
                assertion_value_valid = isinstance(raw_assertion_value, str) and bool(raw_assertion_value)
                assertion_operator_valid = isinstance(raw_assertion_operator, str) and bool(raw_assertion_operator.strip())
                value_candidates = _verbatim_candidates(raw_assertion_value) if assertion_value_valid else []
                assertion_source_forms = external_forms if external_forms is not None else [form for value in anchor_values for form in _assertion_source_forms(value, item_origin)]
                if not assertion_operator_valid or not value_candidates or (not any((candidate == source for candidate in value_candidates for source in assertion_source_forms))):
                    bad.setdefault(autoid, []).append(f'expectations_by_step[{index}].assertion.value')
            step_number = str(item.get('n') or '').strip()
            if item_origin.startswith('expectation:'):
                expectation_label = item_origin.split(':', 1)[1]
                allowed_steps = [expectation_label] if expectation_label.isdigit() else case_anchors.get(_expectation_step_anchor(expectation_label)) or []
            else:
                allowed_steps = [step_number] if case_anchors.get(f'step:{step_number}') else []
            if step_number not in allowed_steps:
                bad.setdefault(autoid, []).append(f'expectations_by_step[{index}].n')
        authored_case_text = [form for value in case_anchors.get('__case_text__', []) for form in _source_atom_forms(value, '')]
        authored_case_atoms = {form for locator, values in case_anchors.items() for value in values for form in _source_atom_forms(value, locator)}
        authored_case_atoms.update(authored_case_text)
        for index, note in enumerate(case.get('adaptation_notes') or []):
            candidates = _verbatim_candidates(str(note or ''))
            if candidates and (not any((candidate in authored_case_atoms for candidate in candidates))):
                bad.setdefault(autoid, []).append(f'adaptation_notes[{index}]')
        dependency = str(case.get('depends_on') or '').strip()
        source_previous = case_anchors.get('__previous_sibling__', [])
        explicit_dependencies = [previous for previous in source_previous if any((previous in source for source in authored_case_text))]
        if explicit_dependencies:
            if dependency != explicit_dependencies[-1]:
                bad.setdefault(autoid, []).append('depends_on')
        elif dependency:
            bad.setdefault(autoid, []).append('depends_on')
    return bad
_EVIDENCE_FIELD_RE = re.compile('^expectations_by_step\\[(\\d+)\\](?:\\.(assertion\\.value|n))?$')

def _unfolded_atom(canonical: str, source_text: str) -> str:
    if not canonical:
        return canonical
    pattern = _whitespace_tolerant_pattern(canonical)
    if pattern is None:
        return canonical
    match = pattern.search(str(source_text or ''))
    return match.group(0) if match is not None else canonical

def verbatim_source_evidence(case: Mapping[str, Any], field: str, *, mindmap_text: str, governing_spec: str | None=None, spec_text: str | None=None, defect_spec_receipt: dict[str, Any] | None=None) -> dict[str, Any]:
    autoid = str(case.get('autoid') or '')
    case_anchors = _mindmap_anchor_map(mindmap_text).get(autoid, {})
    raw_origin = case.get('origin')
    origin_map = raw_origin if isinstance(raw_origin, Mapping) else {}
    expectations = [item for item in case.get('expectations_by_step') or [] if isinstance(item, dict)]

    def _anchored(origin: object, *, assertion: bool=False) -> dict[str, Any]:
        text = str(origin or '')
        external = _external_origin_forms(text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
        if external is not None:
            raw = _external_origin_raw_text(text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
            return {'origin': text, 'external': True, 'atoms': [_unfolded_atom(form, raw) for form in external[:1]], 'kind': 'anchored'}
        forms = _assertion_source_forms if assertion else _source_atom_forms
        atoms: list[str] = []
        canonical_seen: set[str] = set()
        for value in case_anchors.get(text) or []:
            candidates = forms(value, text)
            if not candidates or candidates[0] in canonical_seen:
                continue
            canonical_seen.add(candidates[0])
            atoms.append(_unfolded_atom(candidates[0], value))
        return {'origin': text, 'external': False, 'atoms': atoms, 'kind': 'anchored'}

    def _structural(origin: object='') -> dict[str, Any]:
        return {'origin': str(origin or ''), 'external': False, 'atoms': [], 'kind': 'structural'}
    if field in ('intent', 'verification_method', 'expectation'):
        return _anchored(origin_map.get(field))
    match = _EVIDENCE_FIELD_RE.fullmatch(str(field or ''))
    if match is not None:
        index = int(match.group(1))
        item = expectations[index] if index < len(expectations) else {}
        item_origin = item.get('origin') if isinstance(item, dict) else ''
        if match.group(2) == 'n':
            return _structural(item_origin)
        return _anchored(item_origin, assertion=match.group(2) == 'assertion.value')
    if str(field or '').startswith('adaptation_notes['):
        return {'origin': '', 'external': False, 'atoms': [], 'kind': 'case_atoms'}
    return _structural()

def _is_disclosure_ref(value: Any) -> bool:
    return isinstance(value, Mapping) and set(value.keys()) == _DISCLOSURE_REF_KEYS and isinstance(value.get('autoid'), str) and isinstance(value.get('expectation_id'), str)

def _disclosure_items_as_contract_refs(items: list[dict[str, Any]], contract_sha256_by_autoid: Mapping[str, str]) -> tuple[list[dict[str, Any]], int]:
    projected: list[dict[str, Any]] = []
    converted = 0
    for item in items:
        autoid = str(item.get('autoid') or '')
        expectation_id = str(item.get('expectation_id') or '')
        if not any((field in item for field in _DISCLOSURE_REF_FIELDS)) or not autoid or (not expectation_id) or (autoid not in contract_sha256_by_autoid):
            projected.append(item)
            continue
        ref = {'autoid': autoid, 'expectation_id': expectation_id}
        projected.append({key: dict(ref) if key in _DISCLOSURE_REF_FIELDS else value for key, value in item.items()})
        converted += 1
    return (projected, converted)

def _sealed_disclosure_payload(payload: dict[str, Any], contract_sha256_by_autoid: Mapping[str, str]) -> dict[str, Any]:
    encoded = encode_json_atomic(payload)
    tokens, depth = scan_json_budget(encoded)
    if len(encoded) <= _PROJECTION_JSON_MAX_BYTES and tokens <= _PROJECTION_JSON_MAX_TOKENS and (depth <= _PROJECTION_JSON_MAX_DEPTH):
        return payload
    projected, converted = _disclosure_items_as_contract_refs(list(payload.get('items') or []), contract_sha256_by_autoid)
    if not converted:
        return payload
    return {**payload, 'items': projected, 'storage_format': DISCLOSURE_STORAGE_CONTRACT_REFS}

def project_machine_mindmap(batch_dir: Path, quarantine: dict[str, list[str]] | None=None, structure_quarantine: Mapping[str, list[str]] | None=None, criterion_unavailable: Mapping[str, str] | None=None, missing_autoids: list[str] | None=None, manifest_cases: list[dict[str, Any]] | None=None, expected_machine_sha256: str | None=None, previously_owned_autoids: list[str] | None=None, resolved_governing_spec: str | None=None, resolved_governing_spec_status: str | None=None, mindmap_source_sha256: str | None=None, resolved_defect_spec_status: str | None=None, resolved_defect_spec_receipt_sha256: str | None=None, resolved_defect_spec_receipt: dict[str, Any] | None=None, mindmap_text: str | None=None, spec_text: str | None=None, criterion_version_family: str='', criterion_manual_version: str='', criterion_rule_records: Mapping[tuple[str, str], Mapping[str, Any]] | None=None) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
    mm_path = batch_dir / 'machine_mindmap.json'
    data, machine_sha256 = load_machine_mindmap(mm_path)
    if expected_machine_sha256 and machine_sha256 != expected_machine_sha256:
        raise MachineMindmapError('machine mindmap changed after verbatim verification')
    raw_cases = data.get('cases')
    if not isinstance(raw_cases, list) or any((not isinstance(case, dict) for case in raw_cases)):
        raise MachineMindmapError('machine mindmap cases must be an object array')
    cases = list(raw_cases)
    declared_count = data.get('case_count')
    autoids = [str(case.get('autoid') or '').strip() for case in cases]
    if isinstance(declared_count, bool) or not isinstance(declared_count, int) or declared_count != len(cases):
        raise MachineMindmapError('machine mindmap case_count does not match cases')
    if any((not re.fullmatch(_LOCATOR_TOKEN, autoid) for autoid in autoids)):
        raise MachineMindmapError('machine mindmap autoid is missing or invalid')
    if len(set(autoids)) != len(autoids):
        raise MachineMindmapError('machine mindmap autoid values must be unique')
    missing_ids = [str(autoid or '').strip() for autoid in missing_autoids or []]
    if any((not re.fullmatch(_LOCATOR_TOKEN, autoid) for autoid in missing_ids)) or len(set(missing_ids)) != len(missing_ids) or set(missing_ids).intersection(autoids):
        raise MachineMindmapError('missing manifest autoid values are invalid or overlap')
    manifest_case_by_autoid: dict[str, dict[str, Any]] = {}
    if manifest_cases is not None:
        if not isinstance(manifest_cases, list) or any((not isinstance(case, dict) for case in manifest_cases)):
            raise MachineMindmapError('manifest cases must be an object array')
        for manifest_case in manifest_cases:
            manifest_autoid = str(manifest_case.get('autoid') or '').strip()
            if not re.fullmatch(_LOCATOR_TOKEN, manifest_autoid) or manifest_autoid in manifest_case_by_autoid:
                raise MachineMindmapError('manifest case autoid values are invalid or duplicate')
            manifest_case_by_autoid[manifest_autoid] = manifest_case
        if any((autoid not in manifest_case_by_autoid for autoid in missing_ids)):
            raise MachineMindmapError('missing autoid has no manifest source case')
        if missing_ids and _SHA256_RE.fullmatch(str(mindmap_source_sha256 or '')) is None:
            raise MachineMindmapError('manifest fallback requires the sealed mindmap source SHA256')
    artifact_spec = str(data.get('governing_spec') or '').strip() or None
    spec_identity_closed = bool(resolved_governing_spec_status in {'no_governing_spec', 'ambiguous'} and resolved_governing_spec is None and (artifact_spec is None) or (resolved_governing_spec_status == 'bound' and resolved_governing_spec is not None and (artifact_spec == resolved_governing_spec)))
    scenario2_spec_status = resolved_governing_spec_status if spec_identity_closed else None
    from cex_core.engine.ist_core.compile_engine.conflict_chain import CompletenessOutcome, SpecValue, classify_completeness, evaluate_spec
    from cex_core.engine.ist_core.tools.device.recompose_parts import MACHINE_MINDMAP_BUCKETS
    if resolved_governing_spec_status is None:
        spec_evaluation = evaluate_spec('no_governing_spec', 'no_ticket_reference')
    else:
        spec_evaluation = evaluate_spec(resolved_governing_spec_status, resolved_defect_spec_status, ticket_eligible=resolved_defect_spec_receipt.get('eligible') is True if isinstance(resolved_defect_spec_receipt, dict) else None)
    quarantine = quarantine or {}
    structure_quarantine = dict(structure_quarantine or {})
    criterion_unavailable = criterion_unavailable or {}
    written: list[str] = []
    needs_decision: list[dict[str, Any]] = []
    disclosures: list[dict[str, Any]] = [{'autoid': str(autoid), 'code': 'mindmap_gap_disclosure', 'message': '机械脑图没写到这份人工脑图，本轮退回，不编写', 'reason_code': 'recompose_missing_case', 'fallback_allowed': True} for autoid in missing_ids if manifest_cases is None]
    quarantined: list[dict[str, str]] = []
    bucket_counts: dict[str, int] = {}
    contracts_dir = batch_dir / 'contracts'
    batch_fd = open_directory_nofollow(batch_dir, error_type=MachineMindmapError, invalid_message='batch directory path is invalid', unavailable_message='batch directory is unavailable')
    try:
        try:
            os.unlink(MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME, dir_fd=batch_fd)
        except FileNotFoundError:
            pass
    finally:
        os.close(batch_fd)
    current_autoids = {str(case.get('autoid') or '') for case in cases} | set(missing_ids) | {str(autoid) for autoid in previously_owned_autoids or []}
    contracts_fd = open_directory_nofollow(contracts_dir, error_type=MachineMindmapError, invalid_message='contracts directory path is invalid', unavailable_message='contracts directory is unavailable', create_missing=True)
    try:
        for autoid in current_autoids:
            if not re.fullmatch(_LOCATOR_TOKEN, autoid):
                continue
            name = f'{autoid}.json'
            try:
                info = os.stat(name, dir_fd=contracts_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode):
                raise MachineMindmapError('machine contract must be a regular file')
            if info.st_nlink != 1:
                raise MachineMindmapError('machine contract must have one link')
            os.unlink(name, dir_fd=contracts_fd)
        os.fsync(contracts_fd)
    finally:
        os.close(contracts_fd)
    contract_sha256_by_autoid: dict[str, str] = {}
    from cex_core.engine.case_compiler.step_structure import object_kind_closed_set as _object_kind_closed_set
    from cex_core.engine.ist_core.display_lexicon import step_structure_quarantine_disclosure_cn, step_structure_quarantine_error_cn
    object_kinds_available = _object_kind_closed_set() is not None
    criterion_disclosures: list[dict[str, Any]] = []
    criterion_pending: list[dict[str, Any]] = []
    typed_pending: list[str] = []
    typed_ready: list[str] = []
    source_status_counts = {'complete': 0, 'incomplete': 0}
    if manifest_cases is not None:
        for autoid in missing_ids:
            try:
                raw = _project_manifest_fallback_case(manifest_case_by_autoid[autoid], mindmap_source_sha256=str(mindmap_source_sha256 or ''))
                normalized = normalize_contract(dict(raw), f'{autoid}.json')
                panel = build_warning_panel([normalized])
                build_validation_cards([normalized], warning_panel=panel)
            except (ContractError, ValueError) as exc:
                quarantined.append({'autoid': autoid, 'error': '按人工脑图原文铸卡没过，本轮退回，不编写', 'reason_code': 'recompose_missing_case_contract_invalid', 'detail': f'{type(exc).__name__}: {str(exc)[:240]}'})
                disclosures.append({'autoid': autoid, 'code': 'mindmap_gap_disclosure', 'message': '机械脑图没写到这份人工脑图，按人工脑图原文铸卡也没过，本轮退回，不编写', 'reason_code': 'recompose_missing_case_contract_invalid', 'fallback_allowed': False})
                continue
            contract_sha256_by_autoid[autoid] = write_json_atomic(contracts_dir / f'{autoid}.json', raw)
            written.append(autoid)
            typed_pending.append(autoid)
            source_status_counts['complete'] += 1
            bucket_counts['step_recipe'] = bucket_counts.get('step_recipe', 0) + 1
            disclosures.append({'autoid': autoid, 'code': 'mindmap_gap_disclosure', 'message': '机械脑图没写到这份人工脑图，已按人工脑图原文出卡，本轮仍编写', 'reason_code': 'recompose_missing_case', 'fallback_allowed': True})
    for case in cases:
        autoid = str(case.get('autoid') or '')
        raw_bucket = case.get('bucket')
        bucket = raw_bucket if isinstance(raw_bucket, str) else ''
        bucket_closed = bucket in MACHINE_MINDMAP_BUCKETS
        if bucket_closed:
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        source_status = _derived_source_status(case)
        source_status_counts[source_status] += 1
        if not bucket_closed:
            quarantined.append({'autoid': autoid, 'error': '机器稿作废：bucket 不在闭集内（exp_recipe / step_recipe / true_gap）', 'reason_code': 'recompose_bucket_missing', 'detail': 'bucket is outside the closed set: ' + (f'{bucket[:40]!r}' if bucket else 'absent or not a string')})
            disclosures.append({'autoid': autoid or 'unknown', 'code': 'mindmap_gap_disclosure', 'message': '机器稿没给这份用例定分类（可出配方 / 源缺口），本轮退回，不编写', 'reason_code': 'recompose_bucket_missing', 'fallback_allowed': False})
            continue
        if autoid in criterion_unavailable:
            reason = str(criterion_unavailable[autoid] or '')[:300]
            quarantined.append({'autoid': autoid, 'error': '归类预期试了一次还是没结果，本轮退回，不编写', 'reason_code': 'adjudication_unavailable', 'detail': reason})
            disclosures.append({'autoid': autoid or 'unknown', 'code': 'adjudication_unavailable', 'message': '归类预期试了一次还是没结果。这份机械脑图本轮不出卡、不编写，其余继续。', 'reason': reason, 'reason_code': 'adjudication_unavailable', 'fallback_allowed': False})
            continue
        if autoid in structure_quarantine:
            codes = [str(code) for code in structure_quarantine[autoid] or []]
            quarantined.append({'autoid': autoid, 'error': step_structure_quarantine_error_cn(codes), 'reason_code': 'recompose_step_structure_invalid', 'detail': '、'.join(codes)[:300]})
            disclosures.append({'autoid': autoid or 'unknown', 'code': 'mindmap_gap_disclosure', 'message': step_structure_quarantine_disclosure_cn(codes), 'reason_code': 'recompose_step_structure_invalid', 'codes': codes[:12], 'fallback_allowed': False})
            continue
        if autoid in quarantine:
            fields = '、'.join(quarantine[autoid])
            quarantined.append({'autoid': autoid, 'error': _verbatim_quarantine_error(fields), 'reason_code': 'recompose_verbatim_mismatch', 'detail': fields})
            disclosures.append({'autoid': autoid or 'unknown', 'code': 'mindmap_gap_disclosure', 'message': _verbatim_quarantine_disclosure(fields), 'reason_code': 'recompose_verbatim_mismatch', 'fallback_allowed': False})
            continue
        case_spec_value = spec_evaluation.value
        case_complete = source_status == 'complete'
        outcome = classify_completeness(case_spec_value, case_complete)
        if outcome is CompletenessOutcome.WAIT_SPEC_RETRY:
            decision = {'autoid': autoid, 'conflict_scenario': 'spec_unknown', 'reason_code': 'spec_lookup_unknown', 'missing_fields': _decision_missing_fields(case), 'options': ['retry_spec_lookup', 'continue_without_spec'], **({'defer_until_static_discovery': True} if case_complete else {})}
            needs_decision.append(decision)
            disclosures.append({**decision, 'code': 'mindmap_gap_disclosure', 'message': '规格书没查成，引擎已自动重试一次，按规格书缺失继续', 'terminal': False, 'fallback_allowed': False})
            if not case_complete:
                continue
        if outcome is CompletenessOutcome.SCENARIO_1:
            if mindmap_text is not None and _source_missing_fields(case, mindmap_text) != _case_missing_fields(case):
                quarantined.append({'autoid': autoid, 'error': '说人工脑图没写完，但和人工脑图原文对不上，本轮退回，不编写', 'reason_code': 'recompose_contract_invalid', 'detail': 'source completeness differs from the recomposed case'})
                disclosures.append({'autoid': autoid or 'unknown', 'code': 'mindmap_gap_disclosure', 'message': '说人工脑图没写完，但和人工脑图原文对不上，不能当成「你的人工脑图没写完」', 'reason_code': 'recompose_contract_invalid', 'fallback_allowed': False})
                continue
            decision = {'autoid': autoid, 'conflict_scenario': 'scenario_1', 'reason_code': 'scenario1_case_incomplete', 'missing_fields': _decision_missing_fields(case), 'options': ['abandon_generation']}
            needs_decision.append(decision)
            disclosures.append({**decision, 'code': 'mindmap_gap_disclosure', 'message': '规格书在，但人工脑图的描述、步骤或预期没写完', 'terminal': False, 'fallback_allowed': False})
            continue
        if outcome is CompletenessOutcome.SCENARIO_2:
            incomplete_reason = _scenario2_incomplete_reason(case, governing_spec_status=scenario2_spec_status, defect_spec_status=resolved_defect_spec_status, defect_spec_receipt_sha256=resolved_defect_spec_receipt_sha256, mindmap_text=mindmap_text)
            if incomplete_reason:
                decision = {'autoid': autoid, 'conflict_scenario': 'scenario_2', 'reason_code': 'scenario2_incomplete_case', 'missing_fields': _decision_missing_fields(case), 'options': ['abandon_generation']}
                needs_decision.append(decision)
                disclosures.append({**decision, 'code': 'mindmap_gap_disclosure', 'message': incomplete_reason, 'terminal': False, 'fallback_allowed': False})
            else:
                quarantined.append({'autoid': autoid, 'error': '说来源缺席，但机械复查没过，本轮退回，不编写', 'reason_code': 'recompose_contract_invalid', 'detail': 'scenario-2 source absence did not pass source recheck'})
                disclosures.append({'autoid': autoid or 'unknown', 'code': 'mindmap_gap_disclosure', 'message': '说来源缺席，但机械复查没过，不能进入放弃', 'reason_code': 'recompose_contract_invalid', 'fallback_allowed': False})
            continue
        ok, why = _eligible(case, mindmap_text=mindmap_text, governing_spec=resolved_governing_spec, spec_text=spec_text, defect_spec_receipt=resolved_defect_spec_receipt)
        if not ok:
            invalid_error, invalid_message = _invalid_contract_user_text(str(why))
            quarantined.append({'autoid': autoid, 'error': invalid_error, 'reason_code': 'recompose_contract_invalid', 'detail': str(why)[:300]})
            disclosures.append({'autoid': autoid or 'unknown', 'code': 'mindmap_gap_disclosure', 'message': invalid_message, 'reason_code': 'recompose_contract_invalid', 'fallback_allowed': False})
            continue
        typed_status = _derived_typed_assertion_status(case)
        try:
            raw = _project_case(case, mindmap_source_sha256=str(mindmap_source_sha256 or machine_sha256), defect_spec_receipt=resolved_defect_spec_receipt, mindmap_text=mindmap_text, resource=(manifest_case_by_autoid.get(autoid) or {}).get('resource'), criterion_version_family=criterion_version_family, criterion_manual_version=criterion_manual_version, criterion_rule_records=criterion_rule_records)
            normalized = normalize_contract(dict(raw), f'{autoid}.json')
            panel = build_warning_panel([normalized])
            build_validation_cards([normalized], warning_panel=panel)
            case_disclosures = _step_structure_disclosures(autoid, raw, object_kinds_available=object_kinds_available, tiers=raw.get('device_disclosure') or [])
            case_disclosures.extend(_author_algorithm_mentions_disclosures(autoid, raw))
        except (ContractError, ValueError, KeyError, TypeError, MemoryError, OverflowError, RecursionError) as exc:
            quarantined.append({'autoid': autoid, 'error': '机械脑图没过复查，本轮退回，不编写', 'reason_code': 'recompose_contract_invalid', 'detail': f'{type(exc).__name__}: {str(exc)[:240]}'})
            disclosures.append({'autoid': autoid or 'unknown', 'code': 'mindmap_gap_disclosure', 'message': '机械脑图没过复查，本轮退回，不编写', 'reason_code': 'recompose_contract_invalid', 'fallback_allowed': False})
            continue
        contract_sha256_by_autoid[autoid] = write_json_atomic(contracts_dir / f'{autoid}.json', raw)
        disclosures.extend(case_disclosures)
        for item in raw.get('expectations') or []:
            if not isinstance(item, dict):
                continue
            normalized_claim = item.get('normalized_claim')
            if not isinstance(normalized_claim, dict):
                continue
            status = str(normalized_claim.get('status') or 'unmatched')
            disclosure = {'autoid': autoid, 'code': 'criterion_normalization_disclosure', 'message': _criterion_disclosure_message(normalized_claim), 'expectation_id': str(normalized_claim.get('expectation_id') or ''), 'shape_key': str(normalized_claim.get('shape_key') or ''), 'version_family': str(normalized_claim.get('version_family') or ''), 'algorithm_classes': list(normalized_claim.get('algorithm_classes') or []), 'status': status, 'criterion_type': normalized_claim.get('criterion_type'), 'rule_id': normalized_claim.get('rule_id'), 'authored_step': normalized_claim.get('authored_step'), 'authored_step_cause': normalized_claim.get('authored_step_cause'), 'source_span': normalized_claim.get('source_span'), 'evidence_chain': normalized_claim.get('evidence_chain'), 'rule_identity': normalized_claim.get('rule_identity'), 'author_veto': normalized_claim.get('author_veto'), 'supersede_cause': normalized_claim.get('supersede_cause'), 'mode': normalized_claim.get('mode'), 'fixture_policy': normalized_claim.get('fixture_policy')}
            criterion_disclosures.append(disclosure)
            disclosures.append(disclosure)
            if status != 'matched':
                criterion_pending.append({**disclosure, 'original_text': str(item.get('text') or ''), 'semantic_key': str(normalized_claim.get('semantic_key') or '')})
        if bucket == 'true_gap':
            disclosures.append({'autoid': autoid or 'unknown', 'code': 'true_gap_card_bucket_disclosure', 'message': '机器稿把这份用例判为没有可用判据，出卡按「判据来自步骤」处理，请据作者原文核对', 'reason_code': 'true_gap_card_bucket', 'fallback_allowed': True})
        disclosures.extend(_enhancement_disclosures_for_case(case))
        written.append(autoid)
        (typed_pending if typed_status == 'pending' else typed_ready).append(autoid)
    if mindmap_text is not None:
        disclosures.extend(_verbatim_duplicate_disclosures(mindmap_text))
    if not written:
        try:
            contracts_dir.rmdir()
        except (FileNotFoundError, OSError):
            pass
    abandoned: list[str] = []
    for item in quarantined:
        item.setdefault('reason_code', 'recompose_contract_invalid')
        item.setdefault('detail', '')
        item.setdefault('user_message', str(item.get('error') or ''))
    summary = {'source': mm_path.name, 'machine_mindmap_sha256': machine_sha256, 'written': written, 'abandoned': abandoned, 'needs_decision': needs_decision, 'spec_value': spec_evaluation.value.value, 'spec_reason': spec_evaluation.reason, 'disclosures': disclosures, 'quarantined': quarantined, 'bucket_counts': bucket_counts, 'source_status_counts': source_status_counts, 'typed_pending': typed_pending, 'typed_ready': typed_ready, 'provisional_spec_unknown_autoids': sorted({str(item.get('autoid') or '') for item in needs_decision if item.get('defer_until_static_discovery') is True and str(item.get('autoid') or '') in written}), 'contract_sha256_by_autoid': contract_sha256_by_autoid, 'criterion_disclosures': criterion_disclosures, 'criterion_pending': criterion_pending}
    disclosure_sha256 = write_json_atomic(batch_dir / MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME, _sealed_disclosure_payload({'schema': 'ist.mindmap.disclosures', 'machine_mindmap_sha256': machine_sha256, 'written_autoids': written, 'contract_sha256_by_autoid': contract_sha256_by_autoid, 'items': disclosures, 'quarantined': quarantined}, contract_sha256_by_autoid))
    summary['disclosure_sha256'] = disclosure_sha256
    return summary

def _index_contract_claims(raw: bytes, autoid: str, index: dict[tuple[str, str], Mapping[str, Any]]) -> str:
    try:
        validate_json_budget(raw, error_type=MachineMindmapError, message='machine contract exceeds the JSON structure budget', max_tokens=_PROJECTION_JSON_MAX_TOKENS, max_depth=_PROJECTION_JSON_MAX_DEPTH)
    except MachineMindmapError:
        return 'structure_budget_exceeded'
    try:
        contract = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError):
        return 'json_invalid'
    if not isinstance(contract, dict):
        return 'json_invalid'
    for item in contract.get('expectations') or []:
        claim = item.get('normalized_claim') if isinstance(item, Mapping) else None
        if not isinstance(claim, Mapping):
            continue
        expectation_id = str(claim.get('expectation_id') or '')
        if not expectation_id:
            continue
        key = (autoid, expectation_id)
        if key in index:
            return 'ref_invalid'
        index[key] = claim
    return ''

def _restore_disclosure_refs(items: list[Any], index: Mapping[tuple[str, str], Mapping[str, Any]]) -> tuple[list[Any] | None, str]:
    restored: list[Any] = []
    for item in items:
        if not isinstance(item, Mapping):
            restored.append(item)
            continue
        present = [field for field in _DISCLOSURE_REF_FIELDS if field in item]
        refs = [field for field in present if _is_disclosure_ref(item.get(field))]
        if not refs:
            restored.append(item)
            continue
        if len(refs) != len(present):
            return (None, 'ref_invalid')
        keys = {(str(item[field]['autoid']), str(item[field]['expectation_id'])) for field in refs}
        if len(keys) != 1:
            return (None, 'ref_invalid')
        key = next(iter(keys))
        if key[0] != str(item.get('autoid') or ''):
            return (None, 'ref_invalid')
        claim = index.get(key)
        if claim is None:
            return (None, 'ref_invalid')
        restored.append({field: claim.get(field) if field in refs else value for field, value in item.items()})
    return (restored, '')

def _projection_load(batch_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    limits = {'max_bytes': _PROJECTION_JSON_MAX_BYTES, 'max_tokens': _PROJECTION_JSON_MAX_TOKENS, 'max_depth': _PROJECTION_JSON_MAX_DEPTH}

    def _fail(reason: str, **diagnostic: Any) -> dict[str, Any]:
        return {'payload': None, 'reason': reason, 'diagnostic': dict(diagnostic)}
    if not isinstance(receipt, dict) or receipt.get('ev') != 'recompose_done':
        return _fail('digest_mismatch')
    path = Path(batch_dir) / MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME
    try:
        probe_identity = stat_regular_nofollow(path, error_type=MachineMindmapError, invalid_message='projection receipt path is invalid', directory_message='projection receipt directory is unavailable', open_message='projection receipt is unavailable', bounds_message='projection receipt is not a sealed regular file', min_bytes=1)
    except (OSError, MachineMindmapError):
        return _fail('sealed_read_failed')
    measured_bytes = int(probe_identity[2])
    if measured_bytes > _PROJECTION_JSON_MAX_BYTES:
        return _fail('bytes_over_limit', bytes=int(measured_bytes), max_bytes=_PROJECTION_JSON_MAX_BYTES)
    try:
        encoded_result = read_regular_nofollow(path, error_type=MachineMindmapError, invalid_message='projection receipt path is invalid', directory_message='projection receipt directory is unavailable', open_message='projection receipt is unavailable', bounds_message='projection receipt exceeds its sealed size boundary', changed_message='projection receipt changed while being read', max_bytes=_PROJECTION_JSON_MAX_BYTES, min_bytes=1, return_identity=True)
        assert isinstance(encoded_result, tuple)
        encoded, sidecar_identity = encoded_result
    except (OSError, MachineMindmapError):
        return _fail('sealed_read_failed')
    tokens, depth = scan_json_budget(encoded)
    measured = {'bytes': len(encoded), 'tokens': tokens, 'depth': depth, **limits}
    if tokens > _PROJECTION_JSON_MAX_TOKENS or depth > _PROJECTION_JSON_MAX_DEPTH:
        return _fail('structure_budget_exceeded', **measured)
    try:
        payload = json.loads(encoded.decode('utf-8'))
    except (ValueError, UnicodeError):
        return _fail('json_invalid', **measured)
    expected_contracts = receipt.get('contract_sha256_by_autoid')
    if not isinstance(payload, dict) or not isinstance(expected_contracts, dict):
        return _fail('digest_mismatch', **measured)
    written = [str(value) for value in receipt.get('written_autoids') or []]
    if not accepts_schema(payload.get('schema'), 'ist.mindmap.disclosures') or sha256_bytes(encoded) != receipt.get('disclosure_sha256') or payload.get('machine_mindmap_sha256') != receipt.get('machine_mindmap_sha256') or (payload.get('written_autoids') != written) or (payload.get('contract_sha256_by_autoid') != expected_contracts) or (set(expected_contracts) != set(written)):
        return _fail('digest_mismatch', **measured)
    storage_format = payload.get('storage_format')
    if storage_format is not None and storage_format != DISCLOSURE_STORAGE_CONTRACT_REFS:
        return _fail('ref_invalid', **measured)
    stores_refs = storage_format == DISCLOSURE_STORAGE_CONTRACT_REFS
    payload_items = payload.get('items')
    if not stores_refs and isinstance(payload_items, list) and any((_is_disclosure_ref(item.get(field)) for item in payload_items if isinstance(item, Mapping) for field in _DISCLOSURE_REF_FIELDS)):
        return _fail('ref_invalid', **measured)
    claim_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    contract_identities: dict[str, Any] = {}
    contracts_dir = Path(batch_dir) / 'contracts'
    if expected_contracts or contracts_dir.exists():
        contracts_fd: int | None = None
        try:
            contracts_fd = open_directory_nofollow(contracts_dir, error_type=MachineMindmapError, invalid_message='contracts directory path is invalid', unavailable_message='contracts directory is unavailable')
            for autoid, expected_sha in expected_contracts.items():
                if not re.fullmatch(_LOCATOR_TOKEN, str(autoid)):
                    return _fail('digest_mismatch', **measured)
                contract_result = read_regular_at_nofollow(contracts_fd, f'{autoid}.json', error_type=MachineMindmapError, open_message='machine contract is unavailable', bounds_message='machine contract exceeds its sealed size boundary', changed_message='machine contract changed while being read', max_bytes=CONTRACT_CARD_MAX_BYTES, min_bytes=1, return_identity=True)
                assert isinstance(contract_result, tuple)
                raw, contract_identity = contract_result
                if sha256_bytes(raw) != expected_sha:
                    return _fail('digest_mismatch', **measured)
                contract_identities[str(autoid)] = contract_identity
                if stores_refs:
                    failure = _index_contract_claims(raw, str(autoid), claim_index)
                    if failure:
                        return _fail(failure, **measured)
            for name in os.listdir(contracts_fd):
                if not name.endswith('.json') or name[:-5] in expected_contracts:
                    continue
                try:
                    raw = read_regular_at_nofollow(contracts_fd, name, error_type=MachineMindmapError, open_message='contract is unavailable', bounds_message='contract exceeds its sealed size boundary', changed_message='contract changed while being read', max_bytes=CONTRACT_CARD_MAX_BYTES, min_bytes=1)
                    validate_json_budget(raw, error_type=MachineMindmapError, message='contract exceeds the JSON structure budget', max_tokens=_PROJECTION_JSON_MAX_TOKENS, max_depth=_PROJECTION_JSON_MAX_DEPTH)
                    other = json.loads(raw.decode('utf-8'))
                except Exception:
                    continue
                if isinstance(other, dict) and other.get('contract_class') == 'mindmap_verbatim':
                    return _fail('digest_mismatch', **measured)
        except Exception:
            return _fail('sealed_read_failed', **measured)
        finally:
            if contracts_fd is not None:
                os.close(contracts_fd)
    try:
        current_identity = stat_regular_nofollow(path, error_type=MachineMindmapError, invalid_message='projection receipt path is invalid', directory_message='projection receipt directory is unavailable', open_message='projection receipt is unavailable', bounds_message='projection receipt exceeds its sealed size boundary', max_bytes=_PROJECTION_JSON_MAX_BYTES, min_bytes=1)
    except (OSError, MachineMindmapError):
        return _fail('sealed_read_failed', **measured)
    if current_identity != sidecar_identity:
        return _fail('digest_mismatch', **measured)
    if stores_refs:
        if not isinstance(payload_items, list):
            return _fail('ref_invalid', **measured)
        restored, failure = _restore_disclosure_refs(payload_items, claim_index)
        if failure:
            return _fail(failure, **measured)
        payload = {**payload, 'items': restored}
    return {'payload': payload, 'reason': '', 'diagnostic': dict(measured), 'sidecar_identity': sidecar_identity, 'contract_identities': dict(contract_identities)}

def _projection_payload(batch_dir: Path, receipt: dict[str, Any]) -> dict[str, Any] | None:
    return _projection_load(Path(batch_dir), receipt)['payload']

def projection_receipt_valid(batch_dir: Path, receipt: dict[str, Any]) -> bool:
    return _projection_payload(Path(batch_dir), receipt) is not None

def load_disclosure_projection(batch_dir: Path, receipt: dict[str, Any] | None=None) -> dict[str, Any]:
    result = _projection_load(Path(batch_dir), receipt or {})
    payload = result['payload']
    if payload is None:
        return {'schema': DISCLOSURE_LOAD_SCHEMA, 'status': 'invalid', 'items': [], 'reason': result['reason'], 'diagnostic': dict(result['diagnostic']), 'sidecar_identity': None, 'contract_identities': {}}
    items = payload.get('items')
    if not isinstance(items, list) or any((not isinstance(item, dict) for item in items)):
        return {'schema': DISCLOSURE_LOAD_SCHEMA, 'status': 'invalid', 'items': [], 'reason': 'json_invalid', 'diagnostic': dict(result['diagnostic']), 'sidecar_identity': None, 'contract_identities': {}}
    return {'schema': DISCLOSURE_LOAD_SCHEMA, 'status': 'valid', 'items': [dict(item) for item in items], 'sidecar_identity': result.get('sidecar_identity'), 'contract_identities': dict(result.get('contract_identities') or {})}

def load_disclosure_items_status(batch_dir: Path, receipt: dict[str, Any] | None=None) -> dict[str, Any]:
    record = load_disclosure_projection(batch_dir, receipt)
    if record['status'] != 'valid':
        return {'schema': DISCLOSURE_LOAD_SCHEMA, 'status': 'invalid', 'items': [], 'reason': record['reason'], 'diagnostic': dict(record['diagnostic'])}
    return {'schema': DISCLOSURE_LOAD_SCHEMA, 'status': 'valid', 'items': list(record['items'])}

def load_disclosure_items(batch_dir: Path, receipt: dict[str, Any] | None=None) -> list[dict[str, Any]]:
    result = load_disclosure_items_status(batch_dir, receipt)
    return list(result['items']) if result['status'] == 'valid' else []
