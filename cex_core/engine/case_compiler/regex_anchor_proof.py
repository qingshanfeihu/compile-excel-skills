# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/regex_anchor_proof.py（sha256 fc983e340167d998）。不在这里手改。
from __future__ import annotations
import re
from dataclasses import dataclass

class RegexAnchorAnalysisUnavailable(ValueError):
    pass

@dataclass(frozen=True)
class RegexAnchorAnalysis:
    contradiction: str = ''
    window_boundary_dependent: bool = False

def analyze_regex_anchors(pattern: str, flags: int=re.DOTALL) -> RegexAnchorAnalysis:
    try:
        from re import _constants as codes, _parser as parser
    except ImportError as exc:
        raise RegexAnchorAnalysisUnavailable('Python regex parser is unavailable') from exc
    try:
        tree = parser.parse(pattern, flags)
    except re.error:
        return RegexAnchorAnalysis()
    except (RecursionError, OverflowError) as exc:
        raise RegexAnchorAnalysisUnavailable('regex parse exceeds the analysis boundary') from exc
    visited = 0
    boundary_dependent = False

    def prove(nodes, effective_flags: int, before: int, after: int, depth: int) -> str:
        nonlocal visited, boundary_dependent
        visited += len(nodes)
        if visited > 4096 or depth > 128:
            raise RegexAnchorAnalysisUnavailable('regex tree exceeds the analysis boundary')
        try:
            widths = [parser.SubPattern(nodes.state, [item]).getwidth()[0] for item in nodes]
        except (RecursionError, OverflowError, KeyError, TypeError) as exc:
            raise RegexAnchorAnalysisUnavailable('regex minimum width is unavailable') from exc
        remaining = sum(widths)
        prefix = before
        for (op, value), width in zip(nodes, widths):
            remaining -= width
            suffix = after + remaining
            proof = ''
            if op is codes.AT:
                start = value is codes.AT_BEGINNING_STRING or (value is codes.AT_BEGINNING and (not effective_flags & re.MULTILINE))
                absolute_end = value is codes.AT_END_STRING
                soft_end = value is codes.AT_END and (not effective_flags & re.MULTILINE)
                boundary_dependent |= start or absolute_end or soft_end
                if start and prefix > 0:
                    proof = 'a string-start anchor follows a mandatory non-empty prefix'
                elif absolute_end and suffix > 0:
                    proof = 'a mandatory non-empty suffix follows a string-end anchor'
                elif soft_end and suffix > 1:
                    proof = 'more than one mandatory character follows an end anchor'
            elif op is codes.SUBPATTERN:
                _group, added, removed, child = value
                proof = prove(child, (effective_flags | added) & ~removed, prefix, suffix, depth + 1)
            elif op is codes.ATOMIC_GROUP:
                proof = prove(value, effective_flags, prefix, suffix, depth + 1)
            elif op is codes.BRANCH:
                branches = [prove(child, effective_flags, prefix, suffix, depth + 1) for child in value[1]]
                if branches and all(branches):
                    proof = 'every alternative contains an incompatible string-boundary anchor'
            elif op in {codes.MAX_REPEAT, codes.MIN_REPEAT, codes.POSSESSIVE_REPEAT}:
                minimum, _maximum, child = value
                if minimum > 0:
                    proof = prove(child, effective_flags, prefix, suffix, depth + 1)
            if proof:
                return proof
            prefix += width
        return ''
    contradiction = prove(tree, int(tree.state.flags), 0, 0, 0)
    return RegexAnchorAnalysis(contradiction, boundary_dependent)
