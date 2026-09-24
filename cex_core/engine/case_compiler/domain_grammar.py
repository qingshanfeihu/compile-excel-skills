# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/domain_grammar.py（sha256 24511cf4fb9489ab）。不在这里手改。
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from cex_core.engine.knowledge_paths import KNOWLEDGE_DATA_ROOT
GRAMMAR_PATH = KNOWLEDGE_DATA_ROOT / 'compile_ref' / 'domain_grammar.json'
_cache: dict = {}

@dataclass(frozen=True)
class CleanupFamily:
    rule_order: int
    matched_prefix: str
    module: str

@dataclass(frozen=True)
class RestoreGateGrammar:
    observe_leading: frozenset[str]
    mutating: frozenset[str]
    local_disk_patterns: tuple[re.Pattern[str], ...]
    cleanup_rules: tuple[dict, ...]

def load_grammar() -> dict:
    try:
        mtime = GRAMMAR_PATH.stat().st_mtime_ns
    except OSError as exc:
        raise FileNotFoundError(f'领域文法数据缺失: {GRAMMAR_PATH}') from exc
    if _cache.get('mtime') == mtime:
        return _cache['data']
    data = json.loads(GRAMMAR_PATH.read_text(encoding='utf-8'))
    compiled = {sid: re.compile(s['pattern'], re.IGNORECASE) for sid, s in data.get('statements', {}).items()}
    _cache.update(mtime=mtime, data=data, compiled=compiled)
    return data

def stmt_re(stmt_id: str) -> re.Pattern:
    load_grammar()
    return _cache['compiled'][stmt_id]

def verbs(class_name: str) -> tuple[str, ...]:
    vc = load_grammar()['verb_classes'][class_name]
    return tuple(vc.get('verbs') or vc.get('words') or ())

def restore_gate_grammar() -> RestoreGateGrammar:
    data = load_grammar()
    verb_classes = data.get('verb_classes')
    persistence = data.get('persistence_channels')
    framework = data.get('framework_cleanup_rules')
    if not all((isinstance(value, dict) for value in (verb_classes, persistence, framework))):
        raise ValueError('restore-gate grammar sections are missing')

    def _verbs(name: str) -> frozenset[str]:
        section = verb_classes.get(name)
        values = section.get('verbs') if isinstance(section, dict) else None
        if not isinstance(values, list) or not values:
            raise ValueError(f'restore-gate verb class is missing: {name}')
        normalized = frozenset((str(value).strip().casefold() for value in values if str(value).strip()))
        if not normalized:
            raise ValueError(f'restore-gate verb class is empty: {name}')
        return normalized
    local_disk = persistence.get('local_disk')
    raw_patterns = local_disk.get('patterns') if isinstance(local_disk, dict) else None
    if not isinstance(raw_patterns, list) or not raw_patterns:
        raise ValueError('restore-gate local_disk patterns are missing')
    patterns = tuple((re.compile(str(pattern), re.IGNORECASE) for pattern in raw_patterns))
    raw_rules = framework.get('rules')
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError('restore-gate framework cleanup rules are missing')
    rules: list[dict] = []
    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, dict):
            raise ValueError('restore-gate cleanup rule must be an object')
        prefixes = rule.get('prefixes')
        order = rule.get('order')
        if isinstance(order, bool) or not isinstance(order, int) or (not isinstance(prefixes, list)) or (not prefixes) or any((not isinstance(prefix, str) or not prefix for prefix in prefixes)):
            raise ValueError(f'restore-gate cleanup rule is invalid: {index}')
        rules.append({'order': order, 'prefixes': tuple(prefixes)})
    return RestoreGateGrammar(observe_leading=_verbs('observe_leading'), mutating=_verbs('mutating'), local_disk_patterns=patterns, cleanup_rules=tuple(rules))

def cleanup_family(command: str, grammar: RestoreGateGrammar, *, strip_mutating_verb: bool=False) -> CleanupFamily | None:
    normalized = str(command or '').strip().casefold()
    if not normalized:
        return None
    if strip_mutating_verb:
        first, separator, remainder = normalized.partition(' ')
        if first not in grammar.mutating or not separator or (not remainder.strip()):
            return None
        normalized = remainder.strip()
    for rule in grammar.cleanup_rules:
        for prefix in rule['prefixes']:
            folded = prefix.casefold()
            if normalized.startswith(folded):
                return CleanupFamily(rule_order=int(rule['order']), matched_prefix=prefix, module=folded.split()[0])
    return None

def is_object_config_command(command: str, grammar: RestoreGateGrammar) -> bool:
    normalized = str(command or '').strip()
    first = normalized.split(None, 1)[0].casefold() if normalized else ''
    if not first or first in grammar.observe_leading or first in grammar.mutating:
        return False
    return not any((pattern.search(normalized) for pattern in grammar.local_disk_patterns))

def probe_tool_transport_failure_codes() -> dict[str, tuple[int, ...]]:
    table = (load_grammar().get('probe_tools') or {}).get('transport_failure_exit_codes') or {}
    out: dict[str, tuple[int, ...]] = {}
    for tool, row in table.items():
        codes = row.get('codes') if isinstance(row, dict) else None
        if not isinstance(codes, list):
            continue
        cleaned = tuple(sorted({int(c) for c in codes if isinstance(c, int) and (not isinstance(c, bool)) and (c > 0)}))
        if cleaned:
            out[str(tool).strip().lower()] = cleaned
    return out

def distribution_methods() -> tuple[str, ...]:
    return tuple(load_grammar()['algorithm_classes']['distribution']['methods'])

def uniform_rotation_methods() -> tuple[str, ...]:
    return tuple(((load_grammar().get('algorithm_classes') or {}).get('uniform_rotation') or {}).get('methods') or ())

def vk_derivation_grammar() -> dict:
    section = load_grammar().get('vk_derivation') or {}
    return dict(section) if isinstance(section, dict) else {}

def deterministic_mapping_methods() -> tuple[str, ...]:
    return tuple(((load_grammar().get('algorithm_classes') or {}).get('deterministic_mapping') or {}).get('methods') or ())

def count_field_words() -> tuple[str, ...]:
    return tuple(load_grammar()['count_field_words']['words'])

def rejection_hints() -> tuple[str, ...]:
    return tuple(load_grammar()['rejection_semantics']['hints'])

def dns_record_types() -> tuple[str, ...]:
    return tuple(load_grammar()['dns_record_types']['words'])

def persistence_patterns() -> tuple[str, ...]:
    chans = load_grammar().get('persistence_channels') or {}
    out: list[str] = []
    for key, ch in chans.items():
        if key.startswith('_') or not isinstance(ch, dict):
            continue
        out.extend((str(p) for p in ch.get('patterns') or []))
    return tuple(out)

def l23_write_patterns() -> tuple[str, ...]:
    return tuple((load_grammar().get('bed_l23_write_forms') or {}).get('patterns') or ())

def occupancy_semantics() -> tuple[tuple[str, ...], tuple[str, ...]]:
    oc = load_grammar().get('occupancy_semantics') or {}
    return (tuple(oc.get('patterns') or ()), tuple(oc.get('negations') or ()))

def forbidden_mechanism_intents() -> tuple[tuple[str, tuple[str, ...]], ...]:
    fm = load_grammar().get('forbidden_mechanism_intents') or {}
    return tuple(((str(f.get('family') or ''), tuple(f.get('patterns') or ())) for f in fm.get('families') or []))

def reference_closures() -> list[dict]:
    return list(load_grammar().get('reference_closures', []))

def anchoring_chains() -> list[dict]:
    return list(load_grammar().get('anchoring_chains', []))

def co_required_params() -> list[dict]:
    return list((load_grammar().get('co_required_params') or {}).get('rules') or [])

def missing_co_required(rules: list[dict], lines: list[str]) -> list[dict]:
    out: list[dict] = []
    for rule in rules or []:
        req_pat = str(rule.get('requires_pattern') or '')
        if not req_pat:
            continue
        try:
            trig = stmt_re(str(rule.get('trigger_statement') or ''))
            req = re.compile(req_pat, re.IGNORECASE)
        except (KeyError, re.error):
            continue
        cond = rule.get('condition') or {}
        values = {str(v).lower() for v in cond.get('values') or []}
        param = str(cond.get('param') or '')
        for line in lines:
            m = trig.search(line)
            if not m:
                continue
            gd = m.groupdict()
            val = str(gd.get(param) or gd.get('name') or '').lower()
            if values and val not in values:
                continue
            if not req.search(line):
                out.append({'rule_id': str(rule.get('id') or ''), 'line': line, 'provenance': rule.get('provenance') or {}})
    return out

def _leading_verb(line: str) -> str:
    toks = (line or '').strip().split()
    return toks[0].strip().strip('"\'').lower() if toks else ''

def _norm_name(name: str, how: str) -> str:
    if how == 'dns_name':
        return name.rstrip('.').lower()
    return name

def dangling_references(closure: dict, lines: list[str]) -> list[str]:
    skip = tuple(closure.get('skip_leading_verbs') or ())
    def_res = [stmt_re(sid) for sid in closure.get('defines', [])]
    ref_res = [stmt_re(sid) for sid in closure.get('references', [])]
    norm = closure.get('normalize', '')
    defined: set[str] = set()
    referenced: list[str] = []
    for line in lines:
        if skip and _leading_verb(line) in skip:
            continue
        matched = False
        for r in def_res:
            m = r.search(line)
            if m:
                defined.add(_norm_name(m.group('name'), norm))
                matched = True
                break
        if matched:
            continue
        for r in ref_res:
            m = r.search(line)
            if m:
                referenced.append(m.group('name'))
                break
    out: list[str] = []
    seen: set[str] = set()
    for name in referenced:
        n = _norm_name(name, norm)
        if n not in defined and n not in seen:
            seen.add(n)
            out.append(name)
    return out

def unanchored_bound_objects(chain: dict, lines: list[str], line_rows: list[int], first_cp_row, expects: list[str], value_pattern) -> list[str]:
    if first_cp_row is None:
        return []
    bind_re = stmt_re(chain['bind'])
    member_re = stmt_re(chain['member_edge'])
    resolve_re = stmt_re(chain['resolve'])
    members: dict[str, list[str]] = {}
    values: dict[str, str] = {}
    first_bind_row: dict[str, int] = {}
    for line, row_idx in zip(lines, line_rows):
        m = member_re.search(line)
        if m:
            members.setdefault(m.group('from'), []).append(m.group('to'))
            continue
        m = resolve_re.search(line)
        if m:
            values.setdefault(m.group('name'), m.group('value'))
            continue
        m = bind_re.search(line)
        if m:
            name = m.group('name')
            if name not in first_bind_row:
                first_bind_row[name] = row_idx
    unanchored: list[str] = []
    for obj, bind_row in first_bind_row.items():
        if bind_row <= first_cp_row:
            continue
        vals = [values[mm] for mm in members.get(obj, []) if mm in values]
        if not vals:
            continue
        anchored = any((re.search(value_pattern(v), expect) for v in vals for expect in expects))
        if not anchored:
            unanchored.append(obj)
    return unanchored
