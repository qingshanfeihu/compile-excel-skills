# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/observe_ops.py（sha256 564cee8606a51ed9）。不在这里手改。
from __future__ import annotations
import re
from cex_core.engine.case_compiler import domain_grammar as _dg
MUTATING_VERBS = _dg.verbs('mutating')
_LEADING_OPS = MUTATING_VERBS + _dg.verbs('observe_leading')
_BEHAVIOR_PROBES_RE = re.compile('\\b(' + '|'.join(_dg.verbs('behavior_probes')) + ')\\b')
_CONFIG_QUERY_RE = re.compile('\\b(' + '|'.join(_dg.verbs('config_query_probes')) + ')\\b')
_RUNTIME_STATE_RE = re.compile('\\b(' + '|'.join(_dg.verbs('runtime_state_words')) + ')\\b')

def object_tokens(text: str) -> list[str]:
    toks = (text or '').strip().split()
    objs: list[str] = []
    leading = True
    for t in toks:
        if t in {'|', '||', '&&', ';'}:
            break
        tl = t.strip().strip('"\'').lower()
        if not re.fullmatch('[a-z][a-z0-9_-]*', tl):
            leading = False
            continue
        if leading and tl in _LEADING_OPS:
            continue
        leading = False
        objs.append(tl)
    return objs

def observe_kind(cmd: str) -> str:
    c = (cmd or '').lower()
    if not c.strip():
        return ''
    if _BEHAVIOR_PROBES_RE.search(c):
        return 'behavior'
    if _CONFIG_QUERY_RE.search(c):
        if _RUNTIME_STATE_RE.search(c):
            return 'behavior'
        return 'config_query'
    return ''

def is_observe_command(cmd: str) -> bool:
    return bool(observe_kind(cmd))

def config_existence_check(observe_cmd: str, expect: str, config_context: list[str], method: str='found') -> tuple[bool, str]:
    qset = set(object_tokens(expect))
    if not qset or observe_kind(observe_cmd) != 'config_query':
        return (False, '')
    matched = ''
    for c in config_context:
        if qset <= set(object_tokens(c)):
            matched = c
            break
    if not matched:
        return (False, '')
    if (method or 'found').strip().lower() != 'found':
        return (False, matched)
    return (True, matched)
