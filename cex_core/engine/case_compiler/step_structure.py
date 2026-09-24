# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/step_structure.py（sha256 c3b6fc9549b1cc6d）。不在这里手改。
from __future__ import annotations
import difflib
import ipaddress
import logging
import re
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence
logger = logging.getLogger(__name__)
STEP_STRUCTURE_KEY = 'step_structure'
ENGINE_SLOTS_KEY = 'engine_slots'
ADAPTED_STEPS_KEY = 'adapted_steps'
ADAPTED_STEP_KEYS = frozenset({'n', 'text', 'basis'})
STRUCTURE_OBJECT_ROLES: tuple[str, ...] = ('created', 'configured', 'observed', 'deleted', 'referenced')
STRUCTURE_CONDITION_KINDS: tuple[str, ...] = ('algorithm', 'type', 'attribute', 'count', 'order', 'weight', 'other')
STRUCTURE_ENTRY_KEYS: frozenset[str] = frozenset({'n', 'objects', 'operations', 'stated_conditions', 'free_slots'})
ENGINE_SLOT_SOURCE = 'engine_rule'
SAMPLING_DISCLOSURE_SLOT = 'sampling_disclosure'
EFFECTIVE_WEIGHTS_SLOT = 'effective_weights'
SLOT_REASON_CODES: tuple[str, ...] = ('ok', 'pairing_ambiguous')
STEP_ORDER_UNAVAILABLE_BASIS = 'engine_step_order_unavailable'
_CONCRETIZATION_REF_RE = re.compile('^concretizations\\[(\\d{1,6})\\]$')
_SLOT_REF_RE = re.compile(f'^{ENGINE_SLOTS_KEY}\\[(\\d{{1,6}})\\]$')
_VALUE_SPLIT_RE = re.compile('[\\s,，、:：/]+')
MAX_OBJECT_COUNT = 1000
MAX_KIND_CHARS = 200
MAX_VIOLATION_PAYLOAD_CHARS = 20000
MAX_VALUE_CHARS = 400
MAX_CONDITION_TEXT_CHARS = 2000
MAX_COUNT_DIGITS = 9
MAX_STRUCTURE_ENTRIES = 200
MAX_ENTRY_ARRAY_ITEMS = 200
MAX_KNOWN_HEADS_SHOWN = 12
MAX_TRUNCATED_LOCI_SHOWN = 12
_OBJECT_KIND_CACHE: dict[str, frozenset[str]] = {}

def _norm_head_tokens(command: Any) -> tuple[str, ...]:
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    return tuple(norm_command_tokens(str(command or '')))

def _verbatim_forms(value: Any) -> list[str]:
    from cex_core.engine.case_compiler.mindmap_contract_projector import verbatim_candidates
    return verbatim_candidates(str(value or ''))

def _display_form(value: Any, limit: int=MAX_CONDITION_TEXT_CHARS) -> str:
    forms = _verbatim_forms(value)
    form = forms[0] if forms else ''
    return form[:limit] if limit and len(form) > limit else form

def _grammar() -> Mapping[str, Any] | None:
    try:
        from cex_core.engine.case_compiler.domain_grammar import load_grammar
        grammar = load_grammar()
    except Exception:
        logger.warning('domain grammar unavailable for step structure', exc_info=True)
        return None
    return grammar if isinstance(grammar, Mapping) else None

def _grammar_verbs(class_ids: Sequence[str]) -> frozenset[str]:
    grammar = _grammar()
    classes = (grammar or {}).get('verb_classes') or {}
    words: set[str] = set()
    for class_id in class_ids:
        spec = classes.get(class_id) if isinstance(classes, Mapping) else None
        if isinstance(spec, Mapping):
            words.update((str(verb).strip().casefold() for verb in spec.get('verbs') or [] if str(verb).strip()))
    return frozenset(words)

def _leading_operator_words() -> frozenset[str]:
    return _grammar_verbs(('observe_leading', 'mutating'))

def _probe_verbs() -> frozenset[str]:
    return _grammar_verbs(('behavior_probes',))

def object_kind_closed_set() -> frozenset[str] | None:
    from cex_core.engine.case_compiler.vendor_stdlib import load_vendor_stdlib
    inventory = load_vendor_stdlib()
    if not isinstance(inventory, dict):
        return None
    headers = inventory.get('headers')
    if not isinstance(headers, dict) or not headers:
        return None
    operators = _leading_operator_words()
    if not operators:
        return None
    cache_key = '{}:{}:{}:{}'.format(str(inventory.get('version') or ''), str(inventory.get('device_os_build') or ''), len(headers), len(operators))
    cached = _OBJECT_KIND_CACHE.get(cache_key)
    if cached is not None:
        return cached
    kinds: set[str] = set()
    for entry in headers.values():
        if not isinstance(entry, Mapping):
            continue
        src = str(entry.get('src') or '')
        path = src.split(':', 2)[-1] if src.count(':') >= 2 else ''
        segments = [part for part in path.split('/') if part]
        if segments and segments[0] == 'global':
            segments = segments[1:]
        while segments and segments[0].casefold() in operators:
            segments = segments[1:]
        if len(segments) >= 2:
            kinds.add('/'.join(segments[:-1]))
    if not kinds:
        return None
    frozen = frozenset(kinds)
    _OBJECT_KIND_CACHE[cache_key] = frozen
    return frozen

def clear_object_kind_cache() -> None:
    _OBJECT_KIND_CACHE.clear()
    _COMMAND_ROLE_CACHE.clear()
    _near_kinds.cache_clear()
ROLE_COMMAND_CLASSES: Mapping[str, frozenset[str]] = {'created': frozenset({'write'}), 'configured': frozenset({'write'}), 'observed': frozenset({'observation'}), 'deleted': frozenset({'teardown'}), 'referenced': frozenset({'write', 'observation', 'teardown'})}
_COMMAND_ROLE_CACHE: dict[str, 'CommandRoleAtlas'] = {}

class CommandRoleAtlas:
    __slots__ = ('_forward', '_inverse_of', '_operators', '_observe', '_max_head')

    def __init__(self, forward: frozenset[tuple[str, ...]], inverse_of: Mapping[tuple[str, ...], frozenset[tuple[str, ...]]], operators: frozenset[str], observe: frozenset[str]) -> None:
        from cex_core.engine.case_compiler.vendor_stdlib import _MAX_HEAD_TOKENS
        self._forward = forward
        self._inverse_of = dict(inverse_of)
        self._operators = operators
        self._observe = observe
        self._max_head = int(_MAX_HEAD_TOKENS)

    @property
    def teardown_operators(self) -> frozenset[str]:
        return self._operators

    @property
    def observe_verbs(self) -> frozenset[str]:
        return self._observe

    def _known_head_length(self, tokens: Sequence[str]) -> int:
        limit = min(len(tokens), self._max_head)
        for size in range(limit, 0, -1):
            prefix = tuple(tokens[:size])
            if prefix in self._forward or prefix in self._inverse_of:
                return size
        return 0

    def command_class(self, tokens: Sequence[str]) -> str:
        if not tokens:
            return ''
        lead = str(tokens[0]).casefold()
        if lead in self._operators:
            return 'teardown'
        size = self._known_head_length(tokens)
        if size and tuple(tokens[:size]) in self._inverse_of:
            return 'teardown'
        if lead in self._observe:
            return 'observation'
        return 'write'

    def undone_heads(self, tokens: Sequence[str]) -> frozenset[tuple[str, ...]]:
        size = self._known_head_length(tokens)
        if not size:
            return frozenset()
        return self._inverse_of.get(tuple(tokens[:size]), frozenset())

    def instance_name(self, tokens: Sequence[str], segments: Sequence[str], offset: int) -> str:
        size = self._known_head_length(tokens)
        if not size and tokens and (str(tokens[0]).casefold() in self._operators):
            inner = self._known_head_length(tokens[1:])
            size = inner + 1 if inner else 0
        if not size:
            size = offset + len(segments) if offset >= 0 else 0
        if 0 < size < len(tokens):
            return str(tokens[size])
        return ''

def command_role_atlas() -> CommandRoleAtlas | None:
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import configured_device_os_build, device_os_build_suffix
        from cex_core.engine.scripts.gen_command_teardown_atlas import load_command_teardown_atlas, verify_atlas_source_identity
        build = str(configured_device_os_build() or '').strip()
        build = device_os_build_suffix(build) or build
        if not build:
            raise ValueError('device build is unavailable for the command role atlas')
        atlas = load_command_teardown_atlas(expected_build=build)
        verify_atlas_source_identity(atlas)
        identity = atlas.get('identity') if isinstance(atlas, Mapping) else None
        fingerprint = str((identity or {}).get('sha256') or '').strip()
        if not fingerprint:
            raise ValueError('the command role atlas carries no source identity')
    except Exception:
        logger.warning('command teardown atlas unavailable for step structure', exc_info=True)
        return None
    commands = atlas.get('commands') if isinstance(atlas, Mapping) else None
    if not isinstance(commands, Mapping) or not commands:
        return None
    observe = _grammar_verbs(('observe_leading',))
    if not observe:
        return None
    cache_key = '{}:{}'.format(fingerprint, ','.join(sorted(observe)))
    cached = _COMMAND_ROLE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    policy = atlas.get('policy') if isinstance(atlas.get('policy'), Mapping) else {}
    selection = policy.get('configuration_write_selection')
    excluded = {str(root).strip().casefold() for root in (selection or {}).get('excluded_roots') or () if str(root).strip()}
    forward: set[tuple[str, ...]] = set()
    inverse_of: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    inverse_leading: set[str] = set()
    for head, record in commands.items():
        tokens = _norm_head_tokens(head)
        if not tokens:
            continue
        forward.add(tokens)
        teardown = record.get('teardown') if isinstance(record, Mapping) else None
        for form in (teardown or {}).get('suggested_inverses') or ():
            inverse = _norm_head_tokens(form)
            if not inverse:
                continue
            inverse_of.setdefault(inverse, set()).add(tokens)
            inverse_leading.add(inverse[0])
    operators = frozenset(excluded & inverse_leading)
    if not operators or not forward:
        return None
    built = CommandRoleAtlas(frozenset(forward), {key: frozenset(value) for key, value in inverse_of.items()}, operators, observe)
    _COMMAND_ROLE_CACHE[cache_key] = built
    return built
_LEGAL_FORM_ENTRY = 'step_structure: [{"n": "<the step number, byte-for-byte from steps[].n>", "objects": [{"kind": "<command-tree object path>", "role": "created|configured|observed|deleted|referenced", "count": <int or null>}], "operations": [{"head": "<a command head already in this case\'s command_check>", "ref": "step:<n>"}], "stated_conditions": [{"text": "<verbatim substring of steps[n].text>", "kind": "algorithm|type|attribute|count|order|weight|other", "value": "<the literal the author wrote>"}], "free_slots": [{"slot": "<name>", "ref": "concretizations[<i>]"}]}]'
LEGAL_FORM_ENTRY = _LEGAL_FORM_ENTRY
_LEGAL_FORM_CONDITION = '{"text": "<a substring of the adapted step text (of steps[n].text when the case carries no adaptation)", "kind": "algorithm|type|attribute|count|order|weight|other", "value": "<the literal the adaptation states, e.g. rr, 3, or the bucket weights 3 2 1>", "author_text": "<the span of the author\'s original text this condition corresponds to; required when the step was adapted, may be omitted when the step is unchanged; the engine grounds it against the sealed steps[n].text with whitespace runs normalized>"}'
_LEGAL_FORM_OPERATION = '{"head": "<one of the command heads this case already carries in command_check[].command>", "ref": "step:<n>"}'
_LEGAL_FORM_OBJECT = f'{{"kind": "<a command-tree object path such as the path segments of the head that creates or configures it>", "role": "created|configured|observed|deleted|referenced", "count": <int or null, at most {MAX_OBJECT_COUNT}>}}'
_LEGAL_FORM_SLOT = '{"slot": "<name>", "ref": "concretizations[<i>]"} — the ref must resolve to an entry that already exists in this case; the value lives there once and is never duplicated into the slot.'
VIOLATION_CODES: tuple[str, ...] = ('step_structure_missing', 'step_structure_condition_not_verbatim', 'step_structure_operation_head_unknown', 'step_structure_object_kind_unknown', 'step_structure_slot_ref_unresolved', 'step_structure_count_out_of_range', 'step_structure_adaptation_invalid')

def _violation(code: str, locus: str, detail: str, legal_form: str) -> dict[str, str]:
    return {'code': code, 'locus': locus, 'detail': detail, 'legal_form': legal_form}

def _locus_list(loci: Sequence[str]) -> str:
    """locus 清单按上限截断，剩下的报个数——清单本身撑爆载荷就本末倒置了。"""
    shown = list(loci[:MAX_TRUNCATED_LOCI_SHOWN])
    rest = len(loci) - len(shown)
    return ', '.join(shown) + (f', and {rest} more' if rest else '')

def _budget_cut_note(kind: str, loci: Sequence[str]) -> str:
    """被截条目**已全部判过**时的说法：条数精确，locus 逐个点名。

    「还有一些没渲染」不够写手用：不知道还有几条、在哪儿，就判不出改完上面这批
    值不值得再交一次，也无从预判下一轮会被同一批违例再拒。
    """
    return f'{len(loci)} further {kind}s are not rendered; the rejection payload reached its budget. They are at: {_locus_list(loci)}. Repair the ones above and submit again; the rest are reported then.'

def _budget_stop_note(kind: str, *, rendered: int, stopped_at: str, unjudged: Sequence[str]) -> str:
    """边判边渲染的循环到顶时的说法：判到哪儿停的，哪些 locus 这份载荷没覆盖。

    与 `_budget_cut_note` 的差别是**不报被截违例的条数**——到顶就不再往下判，那个
    数字没算过。报出来的都是算过的：渲染了几条、停在哪个 locus、剩下哪些条目这份
    载荷没说话。编个「还有 N 条」比不说更坏。
    """
    return f'{rendered} {kind}s are rendered above, and the rejection payload reached its budget at {stopped_at}: judging stopped there. These {len(unjudged)} loci are not covered by this payload: {_locus_list(unjudged)}. Repair the ones above and submit again; whatever is left is judged and reported then.'

def budget_violations(violations: Sequence[Mapping[str, str]], *, max_chars: int=MAX_VIOLATION_PAYLOAD_CHARS) -> list[dict[str, str]]:
    """按码去重合法形态、收住载荷，并给每个被截的码补一条「截了几条、在哪儿」。

    入参是**已经判完**的整份清单，所以被截那些条目的 locus 与条数都是现成的：
    通知因此报精确数字（`_budget_cut_note`），不说「还有一些」。

    截断通知不计入 `max_chars`：预算的钱该花在违例上，让某个码的通知去挤掉**另一个
    码**的违例是把话说少了。整份载荷因此是 `max_chars` 加每个被截码一条通知，
    locus 清单按 `MAX_TRUNCATED_LOCI_SHOWN` 收口、条数照实报。
    """
    emitted_codes: set[str] = set()
    out: list[dict[str, str]] = []
    cut: dict[str, list[str]] = {}
    notice_slot: dict[str, int] = {}
    spent = 0
    for item in violations:
        row = {str(key): str(value) for key, value in dict(item).items()}
        code = row.get('code', '')
        legal_form = row.get('legal_form', '')
        if code in emitted_codes:
            row['legal_form'] = f'see the first {code} violation above'
        size = sum((len(key) + len(value) for key, value in row.items()))
        if spent + size > max_chars and out:
            if code not in cut:
                notice_slot[code] = len(out)
                out.append({'code': code, 'locus': row.get('locus', ''), 'detail': '', 'legal_form': f'see the first {code} violation above' if code in emitted_codes else legal_form})
                emitted_codes.add(code)
            cut.setdefault(code, []).append(row.get('locus', ''))
            continue
        emitted_codes.add(code)
        spent += size
        out.append(row)
    for code, loci in cut.items():
        out[notice_slot[code]]['detail'] = _budget_cut_note(f'{code} violation', loci)
    return out

def _step_index(case: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in case.get('steps') or ():
        if not isinstance(item, Mapping):
            continue
        number = str(item.get('n') or '').strip()
        if number:
            out[number] = str(item.get('text') or '')
    return out
_IP_LITERAL_RE = re.compile('(?<![0-9A-Za-z:.])((?:\\d{1,3}\\.){3}\\d{1,3}|(?=[0-9A-Fa-f]*:)[0-9A-Fa-f:]{2,39})(%[\\w.-]+)?(/\\d{1,3})?(?![0-9A-Za-z:.])')
MAX_ADAPTED_STEP_CHARS = 4000
MAX_ADAPTED_BASIS_CHARS = 2000

def _ip_address(token: Any) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """IP 形态字面解析出的地址对象；不是 IP 形态就 `None`。

    规范键与地址族共用这一次解析——族信息本来就在解析结果里，再解析一遍只会多出
    一条判不出来的 `except`。
    """
    text = str(token or '').strip()
    match = _IP_LITERAL_RE.fullmatch(text)
    if match is None:
        return None
    try:
        return ipaddress.ip_address(match.group(1))
    except ValueError:
        return None

def _ip_key(token: Any) -> str | None:
    """IP 形态字面的规范键：去掉 %zone 与 /prefix，v4/v6 都按 ipaddress 规范串。"""
    address = _ip_address(token)
    return None if address is None else str(address)

def _ip_literals(text: Any) -> set[str]:
    out: set[str] = set()
    for match in _IP_LITERAL_RE.finditer(str(text or '')):
        key = _ip_key(match.group(0))
        if key:
            out.add(key)
    return out

def _adaptation_tokens(text: str) -> list[str]:
    """对齐用记号流：IP 字面整段一个记号，其余逐字符。"""
    out: list[str] = []
    pos = 0
    for match in _IP_LITERAL_RE.finditer(text):
        if _ip_key(match.group(0)) is None:
            continue
        out.extend(text[pos:match.start()])
        out.append(match.group(0))
        pos = match.end()
    out.extend(text[pos:])
    return out

def _adaptation_literal_map(authored: str, adapted: str) -> tuple[dict[str, set[str]], bool]:
    """作者 IP 字面 → 适配后取值的逐字面映射（按序列对齐，不按集合计数）。

    返回 (mapping, aligned)：mapping[作者字面] = {替换值…}；某段替换里作者侧
    与适配侧 IP 个数对不齐、或作者字面被整段删除时 aligned=False，调用方退回
    按步的基数下界。
    """
    a_tokens = _adaptation_tokens(authored)
    b_tokens = _adaptation_tokens(adapted)
    matcher = difflib.SequenceMatcher(None, a_tokens, b_tokens, autojunk=False)
    mapping: dict[str, set[str]] = {}
    aligned = True
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for token in a_tokens[i1:i2]:
                key = _ip_key(token)
                if key:
                    mapping.setdefault(key, set()).add(key)
        elif tag == 'replace':
            gone = [k for k in (_ip_key(t) for t in a_tokens[i1:i2]) if k]
            came = [k for k in (_ip_key(t) for t in b_tokens[j1:j2]) if k]
            if not gone:
                continue
            for old, new in zip(gone, came):
                mapping.setdefault(old, set()).add(new)
            if len(gone) > len(came):
                aligned = False
        elif tag == 'delete':
            if any((_ip_key(t) for t in a_tokens[i1:i2])):
                aligned = False
    return (mapping, aligned)
SUBSTITUTION_BASIS_UNREACHABLE_ADDRESS = 'unreachable_address'
SUBSTITUTION_BASIS_BED_ROLE = 'bed_role'
_CONDITION_ATOM_RE = re.compile('[A-Za-z0-9_][A-Za-z0-9_.:%-]*')

def _condition_atoms(text: Any) -> list[str]:
    """条件文本里的记号流：拉丁/数字连写段。中文散文不进这一格。"""
    return [match.group(0) for match in _CONDITION_ATOM_RE.finditer(str(text or ''))]

def _atom_in_text(atom: str, text: Any) -> bool:
    if not atom:
        return False
    pattern = '(?<![A-Za-z0-9_])' + re.escape(atom) + '(?![A-Za-z0-9_])'
    return re.search(pattern, str(text or ''), re.IGNORECASE) is not None
_ORDINAL_MARKER_RE = re.compile('^\\d{1,3}\\.(?=.)')

def _atom_is_head_token(atom: str, token: str) -> bool:
    """记号是不是这个命令头 token——容作者写在命令前面的序号标记。

    语料里的步骤原文常写成 `2.slb virtual addrlists "addlist1" …`：序号和命令之间
    只有一个点，记号流因此把 `2.slb` 连成一个。不容这一形态，带序号的那些步一条
    命令头都接不上，整格恒空。只剥纯数字前缀，`www.test.com` 不受影响。
    """
    if atom == token:
        return True
    stripped = _ORDINAL_MARKER_RE.sub('', atom, count=1)
    return stripped != atom and stripped == token

def _argument_atoms(text: Any, grounded_heads: Sequence[tuple[str, tuple[str, ...]]]) -> set[str]:
    """落在某条已接地命令头之后的记号集——「实参位」。

    与比对器判 `stated_conditions[].value` 用的是同一条纪律（14 章 §7「实参＝头/
    对象路径之后的 token」）：一个词只在某条命令的实参里才是一个**取值**，散文里的
    同一个词不是。命令头取每案自己 `command_check` 里已接地的那批，代码不写死任何
    命令；一条头都接不上时这一格恒空，规则据此不判。
    """
    atoms = [atom.lower() for atom in _condition_atoms(text)]
    out: set[str] = set()
    for _command, head in grounded_heads:
        tokens = [str(token).lower() for token in head]
        if not tokens or len(tokens) > len(atoms):
            continue
        width = len(tokens)
        for start in range(len(atoms) - width + 1):
            window = atoms[start:start + width]
            if not _atom_is_head_token(window[0], tokens[0]):
                continue
            if window[1:] == tokens[1:]:
                out.update(atoms[start + width:])
    return out

def _atom_replacements(before: Any, after: Any) -> list[tuple[str, str]]:
    """两段文本按记号流对齐后 1:1 的替换对；长度不等的替换段整段跳过。

    只收 1:1 是故意的：`a b → c` 这种不等长替换说不出「谁换成了谁」，硬配对等于
    引擎替模型猜对应关系。
    """
    a = [atom.lower() for atom in _condition_atoms(before)]
    b = [atom.lower() for atom in _condition_atoms(after)]
    out: list[tuple[str, str]] = []
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace' and i2 - i1 == j2 - j1:
            out.extend(((a[i1 + k], b[j1 + k]) for k in range(i2 - i1)))
    return out

def adaptation_value_substitutions(*, author_text: Any, text: Any, value: Any, sealed_step: Any, adapted_step: Any, grounded_heads: Sequence[tuple[str, tuple[str, ...]]]) -> list[tuple[str, str]]:
    """「适配把作者写在命令实参位上的 stated 取值换成了另一个字面」逐条挑出来。

    四条同时成立才算一次换值；任一条不成立就不是这一格的事，宁可少判：

    1. `author_text` → `text` 对齐后有一对 1:1 的记号替换（旧 → 新）；
    2. 旧记号在整条适配文本里已经不在了——还在就是措辞变了，不是取值被换了；
    3. 新记号属本条件声明的 `value`、旧记号不属。`value` 是引擎带下游的那一个
       （契约卡、编写侧信封、比对器实参比对都读它），两侧都不动它的替换改变不了
       引擎认定的作者取值；
    4. 旧记号在**密封原文**里、新记号在**适配文本**里，都落在某条已接地命令头的
       实参位上。散文里的同一个词不是取值——记法归一（作者写 `v4`、适配写
       `IPv4`）正是从这一条出去的。

    返回 (旧记号, 新记号) 列表，全部小写。判定零领域词表：命令头来自本案
    `command_check`，取值切分与比对器共用 `stated_value_tokens`。
    """
    value_atoms = {token.lower() for token in stated_value_tokens(value) if token}
    if not value_atoms:
        return []
    sealed_args = _argument_atoms(sealed_step, grounded_heads)
    adapted_args = _argument_atoms(adapted_step, grounded_heads)
    if not sealed_args or not adapted_args:
        return []
    out: list[tuple[str, str]] = []
    for old, new in _atom_replacements(author_text, text):
        if new not in value_atoms or old in value_atoms:
            continue
        if _atom_in_text(old, adapted_step):
            continue
        if old not in sealed_args or new not in adapted_args:
            continue
        if (old, new) not in out:
            out.append((old, new))
    return out

def _bed_facts() -> Any:
    """床事实取不到就抛（批入口已排除，见 `env_facts.require_env_facts`）。"""
    from cex_core.engine.ist_core.tools._shared.env_facts import require_env_facts
    return require_env_facts()

def _address_unreachable_on_bed(facts: Any, literal: str) -> bool | None:
    if _ip_key(literal) is None:
        return None
    try:
        return bool(facts.unreachable_ipv4s(literal) or facts.unreachable_ipv6s(literal))
    except Exception:
        logger.warning('bed reachability unavailable for %r', literal, exc_info=True)
        return None

def _address_family(literal: Any) -> int | None:
    """地址族，与 `_ip_key` 同一次解析。"""
    address = _ip_address(literal)
    return None if address is None else address.version

def recomputable_substitution_basis(old_atom: str, new_atom: str) -> str | None:
    """这次换值有没有**引擎可重算**的依据；`None` 表示没有，规则据此拒。

    两条依据都只对床事实投影重算，不含任何领域词表——它们对应的正是重组孔被要求
    做的两件事（`agents/mindmap-recompose.md` 的适配规则）：

    - `unreachable_address`：作者字面是这张床**不可达**的地址、适配字面可达，**且两
      者同地址族**。条款原话是「他床字面改转为同地址族的自动化取值」
      （`docs/engine/02_decision_space.md` §2.27 改写制）：不可达才是「他床字面」，
      同族才是「改转」——v4 换成 v6 不是重绑，是换了测试点。
    - `bed_role`：**作者那个原子不是地址字面**，而适配字面是床事实里点得出的东西
      （设备名，或这张床可达的地址）。作者写角色、适配落到这张床上的具体值，落点在
      不在床上是引擎算得出的。算法名、协议词、权重、次数都不在床事实里，借不到这条。

    **作者写的就是地址字面时只有上面第一条路**：本床已经连得上的地址被换掉，换的是
    测试点本身，不是重绑——`<case>` 的 dig 目标串段正是这类。重组孔虽拿不到床事实，
    但经 concretizations/manual 见证仍可能撞上床可达值，所以这道口不能留。

    床事实取不到就抛（批入口已排除，见 `env_facts.require_env_facts`）：「判不出依据
    在不在」既不是「没有依据」（那会误拒），也不能当「有依据」放行——放行正是把重组孔
    换掉的作者取值当成引擎认可的取值签下去。
    """
    facts = _bed_facts()
    old_unreachable = _address_unreachable_on_bed(facts, old_atom)
    new_unreachable = _address_unreachable_on_bed(facts, new_atom)
    if old_unreachable is True and new_unreachable is False and (_address_family(old_atom) == _address_family(new_atom)):
        return SUBSTITUTION_BASIS_UNREACHABLE_ADDRESS
    if _ip_key(old_atom) is not None:
        return None
    if new_unreachable is False:
        return SUBSTITUTION_BASIS_BED_ROLE
    names = {str(device.get('name') or '').strip().lower() for device in facts.devices if isinstance(device, Mapping)}
    names.discard('')
    if str(new_atom or '').strip().lower() in names:
        return SUBSTITUTION_BASIS_BED_ROLE
    return None

def _normalized_step_text(text: Any) -> str:
    return re.sub('\\s+', ' ', str(text or '').replace('\xa0', ' ')).strip()

def step_is_adapted(authored_text: Any, adapted_text: Any) -> bool:
    """「这一步有没有适配」只有这一份判据：空白归一后不相等才算适配。

    三个消费方（提交口校验、比对器/审计短路、契约卡披露）都调它，避免
    一边 strip 一边不 strip、一边看 2000 字截断视图一边看全文的分叉。
    """
    return _normalized_step_text(authored_text) != _normalized_step_text(adapted_text)

def adapted_step_texts(case: Mapping[str, Any]) -> dict[str, str] | None:
    """适配步索引；未提交或形状不可用返回 None（消费方回退密封原文）。"""
    raw = case.get(ADAPTED_STEPS_KEY)
    if not isinstance(raw, list):
        return None
    out: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            return None
        number = str(item.get('n') or '').strip()
        text = str(item.get('text') or '')
        if not number or not text.strip():
            return None
        out[number] = text
    return out or None

def case_has_adaptation(case: Mapping[str, Any]) -> bool:
    adapted = adapted_step_texts(case)
    if adapted is None:
        return False
    steps = _step_index(case)
    if set(adapted) != set(steps):
        return True
    return any((step_is_adapted(text, adapted.get(number)) for number, text in steps.items()))
_LEGAL_FORM_ADAPTED = '[{"n": "<step number, same set and order as steps[]>", "text": "<the adapted step text>", "basis": "<why this adaptation preserves the authored scenario; may be empty when a step needed no change>"}] — one entry per authored step, same order; steps[] stays sealed and the author\'s original text stays in it.'

def adapted_steps_violations(case: Mapping[str, Any], *, autoid: str, index: int) -> list[dict[str, str]]:
    """改写制旁列的提交口校验：形状、整案一致、字面映射关系。

    机械只守 100% 可判的关系：同一作者 IP 字面在适配里只能换成一个值（同字面
    同值）、不同作者 IP 字面不得换成同一个值（不同字面不同值）、`load_bearing`
    牌照的 IP 字面必须留在适配文本里。非 IP 字面（角色词、权重、主机名）不在
    机械面上，只经披露（adapted_step_disclosure）交人看。
    """
    raw = case.get(ADAPTED_STEPS_KEY)
    if raw is None:
        return []
    steps = _step_index(case)
    field_root = f'cases[{index}].{ADAPTED_STEPS_KEY}'
    if not isinstance(raw, list):
        return [_violation('step_structure_adaptation_invalid', field_root, f'case {autoid} {ADAPTED_STEPS_KEY} must be an array beside the sealed steps; got a JSON {type(raw).__name__}.', _LEGAL_FORM_ADAPTED)]
    if len(raw) > MAX_STRUCTURE_ENTRIES:
        return [_violation('step_structure_count_out_of_range', field_root, f'case {autoid} carries {len(raw)} adapted steps; at most {MAX_STRUCTURE_ENTRIES} are judged. There is one entry per authored step, and no authored procedure has that many.', _LEGAL_FORM_ADAPTED)]
    step_order = list(steps)
    violations: list[dict[str, str]] = []
    adapted_order: list[str] = []
    spent = 0
    for position, item in enumerate(raw):
        if spent > MAX_VIOLATION_PAYLOAD_CHARS:
            violations.append(_violation('step_structure_adaptation_invalid', field_root, f'case {autoid}: ' + _budget_stop_note('adapted-step violation', rendered=len(violations), stopped_at=f'{field_root}[{position}]', unjudged=[f'{field_root}[{index_}]' for index_ in range(position, len(raw))]), _LEGAL_FORM_ADAPTED))
            break
        before = len(violations)
        field = f'{field_root}[{position}]'
        if not isinstance(item, Mapping) or set(item) != set(ADAPTED_STEP_KEYS):
            violations.append(_violation('step_structure_adaptation_invalid', field, f'case {autoid}: each adapted step is exactly `n`, `text` and `basis`; got ' + (', '.join(sorted((str(k)[:80] for k in item))[:24]) if isinstance(item, Mapping) else f'a JSON {type(item).__name__}') + '.', _LEGAL_FORM_ADAPTED))
        else:
            number = str(item.get('n') or '').strip()
            text = item.get('text')
            basis = item.get('basis')
            if not isinstance(text, str) or not text.strip():
                violations.append(_violation('step_structure_adaptation_invalid', f'{field}.text', f'case {autoid}: adapted step {number!r} carries no text.', _LEGAL_FORM_ADAPTED))
            elif len(text) > MAX_ADAPTED_STEP_CHARS:
                violations.append(_violation('step_structure_adaptation_invalid', f'{field}.text', f'case {autoid}: adapted step {number!r} text is {len(text)} characters; at most {MAX_ADAPTED_STEP_CHARS} are judged. It is the step in executable form, not an explanation of it.', _LEGAL_FORM_ADAPTED))
            elif basis is not None and (not isinstance(basis, str)):
                violations.append(_violation('step_structure_adaptation_invalid', f'{field}.basis', f'case {autoid}: adapted step {number!r} `basis` must be a string; got a JSON {type(basis).__name__}.', _LEGAL_FORM_ADAPTED))
            elif isinstance(basis, str) and len(basis) > MAX_ADAPTED_BASIS_CHARS:
                violations.append(_violation('step_structure_adaptation_invalid', f'{field}.basis', f'case {autoid}: adapted step {number!r} `basis` is {len(basis)} characters; at most {MAX_ADAPTED_BASIS_CHARS} are judged.', _LEGAL_FORM_ADAPTED))
            elif number not in steps:
                violations.append(_violation('step_structure_adaptation_invalid', f'{field}.n', f"case {autoid}: adapted step {number!r} is not one of the authored step numbers ({', '.join(step_order) or 'none'}).", _LEGAL_FORM_ADAPTED))
            else:
                adapted_order.append(number)
        for row in violations[before:]:
            spent += sum((len(str(v)) for v in row.values()))
    if violations:
        return violations
    if adapted_order != step_order:
        return [_violation('step_structure_adaptation_invalid', field_root, f'case {autoid}: {ADAPTED_STEPS_KEY} must carry one entry per authored step in the same order as steps[]; got {adapted_order} where steps[] reads {step_order}.', _LEGAL_FORM_ADAPTED)]
    adapted = adapted_step_texts(case) or {}
    load_bearing: set[str] = set()
    for license_ in case.get('rebind_licenses') or ():
        if not isinstance(license_, Mapping):
            continue
        if str(license_.get('verdict') or '') != 'load_bearing':
            continue
        key = _ip_key(str(license_.get('author_literal') or '').strip())
        if key:
            load_bearing.add(key)
    mapping: dict[str, set[str]] = {}
    for number, authored_text in steps.items():
        adapted_text = adapted.get(number, '')
        step_map, aligned = _adaptation_literal_map(authored_text, adapted_text)
        for key, values in step_map.items():
            mapping.setdefault(key, set()).update(values)
        if aligned:
            continue
        authored_keys = _ip_literals(authored_text)
        adapted_keys = _ip_literals(adapted_text)
        gone = authored_keys - adapted_keys
        fresh = adapted_keys - authored_keys
        if len(gone) >= 2 and len(fresh) < len(gone):
            violations.append(_violation('step_structure_adaptation_invalid', f'{field_root}[{step_order.index(number)}].text', f'case {autoid} step {number}: {len(gone)} distinct author address literals were replaced but only {len(fresh)} fresh address literal(s) appeared. Distinct author literals must not collapse onto one setup value; keep each authored address on its own adapted value.', _LEGAL_FORM_ADAPTED))
    for key in sorted(mapping):
        values = mapping[key]
        if len(values) > 1:
            violations.append(_violation('step_structure_adaptation_invalid', field_root, f"case {autoid}: the author literal {key} is adapted to {len(values)} different values ({', '.join(sorted(values))}). The same author literal keeps one value everywhere (same-literal equality).", _LEGAL_FORM_ADAPTED))
    by_value: dict[str, set[str]] = {}
    for key, values in mapping.items():
        for value in values:
            by_value.setdefault(value, set()).add(key)
    for value in sorted(by_value):
        sources = by_value[value]
        if len(sources) > 1:
            violations.append(_violation('step_structure_adaptation_invalid', field_root, f"case {autoid}: distinct author literals {', '.join(sorted(sources))} are adapted onto the same value {value}. Different author literals stay different (different-literal inequality); collapsing them changes the test point.", _LEGAL_FORM_ADAPTED))
    adapted_all = _ip_literals('\n'.join(adapted.values()))
    for key in sorted(load_bearing):
        if key not in adapted_all:
            violations.append(_violation('step_structure_adaptation_invalid', field_root, f'case {autoid}: the load-bearing author literal {key} is missing from the adapted steps. A load_bearing license means the literal itself is the test point; adaptation keeps it and the unreachability is disclosed, not rewritten.', _LEGAL_FORM_ADAPTED))
    violations.extend(_stated_value_substitution_violations(case, autoid=autoid, index=index, steps=steps, adapted=adapted))
    return violations

def _stated_value_substitution_violations(case: Mapping[str, Any], *, autoid: str, index: int, steps: Mapping[str, str], adapted: Mapping[str, str]) -> list[dict[str, str]]:
    """适配改动 stated 条件字面，必须有引擎可重算的依据，否则拒。

    机械面原先只守地址字面（同字面同值、不同字面不同值、load_bearing 必留），
    「非 IP 字面（角色词、权重、主机名）不在机械面上，只经披露」。<case> 证明了
    那道口太窄：作者步骤写 `method hostname wrr`、权重配 30/20/10，重组孔把命令
    实参位上的算法词改成 `ga` 再往下走，条件的 `value` 因此签成 `ga`——引擎从此
    把适配的取值当作者的取值带进契约卡、编写侧信封与保真比对，而作者两处表面互斥
    这件事一个字都没被声明。

    判据在 `adaptation_value_substitutions`（四条同时成立才算换值，见那里）；
    可重算依据在 `recomputable_substitution_basis`（不可达地址 / 床事实角色）。
    床事实取不到即抛，不在这一层折叠成放行或误拒（见 `recomputable_substitution_basis`）。

    这条规则不判「哪一边是对的」：谁是笔误是权威裁决，重组孔没有这个授权，
    拒绝文案把它指向案内互斥出口 `consistency.authored_conflict`。
    """
    structure = case.get(STEP_STRUCTURE_KEY)
    if not isinstance(structure, list) or not structure:
        return []
    grounded = _grounded_heads(case)
    if not grounded:
        return []
    out: list[dict[str, str]] = []
    spent = 0
    for position, entry in enumerate(structure[:MAX_STRUCTURE_ENTRIES]):
        if not isinstance(entry, Mapping):
            continue
        number = str(entry.get('n') or '').strip()
        sealed_step = steps.get(number)
        if sealed_step is None:
            continue
        adapted_step = adapted.get(number) or sealed_step
        conditions = entry.get('stated_conditions')
        if not isinstance(conditions, list):
            continue
        for slot, condition in enumerate(conditions[:MAX_ENTRY_ARRAY_ITEMS]):
            if not isinstance(condition, Mapping):
                continue
            author_text = condition.get('author_text')
            text = condition.get('text')
            if not isinstance(author_text, str) or not isinstance(text, str):
                continue
            substitutions = adaptation_value_substitutions(author_text=author_text, text=text, value=condition.get('value'), sealed_step=sealed_step, adapted_step=adapted_step, grounded_heads=grounded)
            for old, new in substitutions:
                basis = recomputable_substitution_basis(old, new)
                if basis is not None:
                    continue
                if spent > MAX_VIOLATION_PAYLOAD_CHARS:
                    judged = structure[:MAX_STRUCTURE_ENTRIES]
                    out.append(_violation('step_structure_adaptation_invalid', f'cases[{index}].{STEP_STRUCTURE_KEY}', f'case {autoid}: ' + _budget_stop_note('adapted-value violation', rendered=len(out), stopped_at=f'cases[{index}].{STEP_STRUCTURE_KEY}[{position}].stated_conditions[{slot}]', unjudged=[f'cases[{index}].{STEP_STRUCTURE_KEY}[{other}]' for other in range(position, len(judged))]), _LEGAL_FORM_ADAPTED))
                    return out
                out.append(_violation('step_structure_adaptation_invalid', f'cases[{index}].{STEP_STRUCTURE_KEY}[{position}].stated_conditions[{slot}]', f"case {autoid} step {number}: the adapted step states {new!r} in the same command argument slot where the author's own words state {old!r}, and {old!r} occurs nowhere in the adapted step. This condition's `value` therefore carries {new!r} downstream as the author's stated value, which it is not. An adaptation may re-word a condition, and it may fill a value the author left open; replacing a value the author did state needs a basis the engine can recompute — an address this bed cannot reach, or a role the bed facts resolve to a machine on it. Neither holds here. If the author's own surfaces disagree (a title or grouping naming one behaviour while a step configures another, and the authored expectation following from only one), that contradiction is the author's to settle: deciding which side is the slip is an authority call this stage does not hold. Leave the authored words in the adapted step and declare it under `consistency.authored_conflict`, quoting each authored surface verbatim by its own locator.", _LEGAL_FORM_ADAPTED))
                spent += sum((len(str(value)) for value in out[-1].values()))
    return out

def _grounded_heads(case: Mapping[str, Any]) -> list[tuple[str, tuple[str, ...]]]:
    out: list[tuple[str, tuple[str, ...]]] = []
    for item in case.get('command_check') or ():
        if not isinstance(item, Mapping):
            continue
        command = str(item.get('command') or '').strip()
        tokens = _norm_head_tokens(command)
        if command and tokens:
            out.append((command, tokens))
    return out

def _head_is_grounded(head: str, grounded: Sequence[tuple[str, tuple[str, ...]]]) -> bool:
    tokens = _norm_head_tokens(head)
    if not tokens:
        return False
    for _command, candidate in grounded:
        if tokens == candidate:
            return True
        if len(tokens) < len(candidate) and candidate[:len(tokens)] == tokens:
            return True
    return False

def _ref_index(ref: str, pattern: re.Pattern[str]) -> int | None:
    match = pattern.match(ref)
    if match is None:
        return None
    digits = match.group(1)
    if not (digits.isascii() and digits.isdecimal()):
        return None
    return int(digits)

def step_structure_violations(case: Mapping[str, Any], *, index: int, object_kinds: frozenset[str] | None) -> list[dict[str, str]]:
    autoid = str(case.get('autoid') or '')
    steps = _step_index(case)
    structure = case.get(STEP_STRUCTURE_KEY)
    if not steps:
        return []
    adapted = adapted_step_texts(case)
    violations: list[dict[str, str]] = []
    violations.extend(adapted_steps_violations(case, autoid=autoid, index=index))
    if not isinstance(structure, list):
        observed = 'the key is absent' if STEP_STRUCTURE_KEY not in case else f'got a JSON {type(structure).__name__}'
        violations.append(_violation('step_structure_missing', f'cases[{index}].{STEP_STRUCTURE_KEY}', f'case {autoid} must carry `{STEP_STRUCTURE_KEY}`, one entry per authored step, beside the verbatim steps; {observed}. The verbatim steps stay the authority — the structure is the projection next to them, and the engine does not derive it.', _LEGAL_FORM_ENTRY))
        return violations
    if len(structure) > MAX_STRUCTURE_ENTRIES:
        violations.append(_violation('step_structure_count_out_of_range', f'cases[{index}].{STEP_STRUCTURE_KEY}', f'case {autoid} carries {len(structure)} structure entries; at most {MAX_STRUCTURE_ENTRIES} are judged. There is one entry per authored step, and no authored procedure has that many.', _LEGAL_FORM_ENTRY))
        return violations
    seen: dict[str, int] = {}
    concretizations = case.get('concretizations')
    concretization_count = len(concretizations) if isinstance(concretizations, list) else 0
    grounded = _grounded_heads(case)
    known_heads = _known_heads_note(grounded)
    spent = 0
    stopped_early = False
    for position, entry in enumerate(structure):
        if spent > MAX_VIOLATION_PAYLOAD_CHARS:
            stopped_early = True
            violations.append(_violation('step_structure_missing', f'cases[{index}].{STEP_STRUCTURE_KEY}', f'case {autoid}: ' + _budget_stop_note('structure-entry violation', rendered=len(violations), stopped_at=f'cases[{index}].{STEP_STRUCTURE_KEY}[{position}]', unjudged=[f'cases[{index}].{STEP_STRUCTURE_KEY}[{other}]' for other in range(position, len(structure))]), _LEGAL_FORM_ENTRY))
            break
        before = len(violations)
        locus = f'cases[{index}].{STEP_STRUCTURE_KEY}[{position}]'
        if not isinstance(entry, Mapping):
            violations.append(_violation('step_structure_missing', locus, f'case {autoid} {STEP_STRUCTURE_KEY}[{position}] must be a JSON object keyed by the authored step number; got a JSON {type(entry).__name__}.', _LEGAL_FORM_ENTRY))
            continue
        number = str(entry.get('n') or '').strip()
        if number not in steps:
            violations.append(_violation('step_structure_missing', f'{locus}.n', f"case {autoid} {STEP_STRUCTURE_KEY}[{position}] names step {number!r}, which is not one of the authored step numbers ({', '.join(sorted(steps)) or 'none'}). One entry per authored step, and the step number is copied from steps[].n.", _LEGAL_FORM_ENTRY))
            continue
        if number in seen:
            violations.append(_violation('step_structure_missing', f'{locus}.n', f'case {autoid} declares step {number} twice in {STEP_STRUCTURE_KEY} (first at {STEP_STRUCTURE_KEY}[{seen[number]}]). One entry per authored step; merge the two entries.', _LEGAL_FORM_ENTRY))
            continue
        seen[number] = position
        unknown_keys = sorted(set(entry) - STRUCTURE_ENTRY_KEYS)
        if unknown_keys:
            violations.append(_violation('step_structure_missing', locus, f"case {autoid} structure entry for step {number} carries fields outside the closed set: {', '.join(unknown_keys)}.", _LEGAL_FORM_ENTRY))
            continue
        violations.extend(_object_violations(entry, autoid=autoid, locus=locus, number=number, object_kinds=object_kinds))
        violations.extend(_operation_violations(entry, autoid=autoid, locus=locus, number=number, grounded=grounded, known_heads=known_heads))
        violations.extend(_condition_violations(entry, autoid=autoid, locus=locus, number=number, step_text=steps[number], adapted_text=adapted.get(number) if adapted is not None else None))
        violations.extend(_slot_violations(entry, autoid=autoid, locus=locus, number=number, concretization_count=concretization_count))
        spent += sum((len(row.get('code', '')) + len(row.get('locus', '')) + len(row.get('detail', '')) for row in violations[before:]))
    missing = [] if stopped_early else sorted(set(steps) - set(seen))
    if missing:
        violations.append(_violation('step_structure_missing', f'cases[{index}].{STEP_STRUCTURE_KEY}', f"case {autoid} has no structure entry for authored step{('s' if len(missing) > 1 else '')} {', '.join(missing)}. Every authored step needs one entry; a step whose structure you cannot state still needs its entry with empty arrays, so the gap is visible instead of silent.", _LEGAL_FORM_ENTRY))
    return violations

def sealed_structure_failures(case: Mapping[str, Any], *, object_kinds: frozenset[str] | None) -> list[str]:
    structure = case.get(STEP_STRUCTURE_KEY)
    if not isinstance(structure, list) or not structure:
        if case.get(ADAPTED_STEPS_KEY) is None:
            return []
        rows = adapted_steps_violations(case, autoid=str(case.get('autoid') or ''), index=0)
    else:
        rows = step_structure_violations(case, index=0, object_kinds=object_kinds)
    codes: list[str] = []
    for item in rows:
        code = str(item.get('code') or '')
        if code and code not in codes:
            codes.append(code)
    return codes

def _object_violations(entry: Mapping[str, Any], *, autoid: str, locus: str, number: str, object_kinds: frozenset[str] | None) -> list[dict[str, str]]:
    objects = entry.get('objects')
    if objects is None:
        objects = []
    if not isinstance(objects, list):
        return [_violation('step_structure_object_kind_unknown', f'{locus}.objects', f'case {autoid} step {number}: `objects` must be an array; got a JSON {type(objects).__name__}.', _LEGAL_FORM_OBJECT)]
    capped = _array_over_cap(objects, autoid=autoid, field=f'{locus}.objects', number=number, legal_form=_LEGAL_FORM_OBJECT)
    if capped is not None:
        return [capped]
    out: list[dict[str, str]] = []
    for position, item in enumerate(objects):
        field = f'{locus}.objects[{position}]'
        if not isinstance(item, Mapping) or set(item) != {'kind', 'role', 'count'}:
            out.append(_violation('step_structure_object_kind_unknown', field, f'case {autoid} step {number}: each object is exactly `kind`, `role` and `count`; got ' + (', '.join(sorted(item)) if isinstance(item, Mapping) else f'a JSON {type(item).__name__}') + '.', _LEGAL_FORM_OBJECT))
            continue
        role = item.get('role')
        if role not in STRUCTURE_OBJECT_ROLES:
            out.append(_violation('step_structure_object_kind_unknown', f'{field}.role', f"case {autoid} step {number}: `role` is one of {', '.join(STRUCTURE_OBJECT_ROLES)}; got {role!r}.", _LEGAL_FORM_OBJECT))
            continue
        count = item.get('count')
        if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 0):
            out.append(_violation('step_structure_object_kind_unknown', f'{field}.count', f'case {autoid} step {number}: `count` is a non-negative integer or null; got {count!r}.', _LEGAL_FORM_OBJECT))
            continue
        if isinstance(count, int) and (not isinstance(count, bool)) and (count > MAX_OBJECT_COUNT):
            out.append(_violation('step_structure_count_out_of_range', f'{field}.count', f'case {autoid} step {number}: `count` is at most {MAX_OBJECT_COUNT}; got {count}. The engine carries this number into the records, disclosures and reports it builds from the structure, so a value beyond the bound is refused instead of being materialized. State the number the authored step actually names.', _LEGAL_FORM_OBJECT))
            continue
        kind = item.get('kind')
        if not isinstance(kind, str) or not kind.strip():
            out.append(_violation('step_structure_object_kind_unknown', f'{field}.kind', f'case {autoid} step {number}: `kind` must be a non-empty command-tree object path; got {kind!r}.', _LEGAL_FORM_OBJECT))
            continue
        if len(kind) > MAX_KIND_CHARS:
            out.append(_violation('step_structure_count_out_of_range', f'{field}.kind', f'case {autoid} step {number}: `kind` is at most {MAX_KIND_CHARS} characters; got {len(kind)}. An object path is a few command-tree segments, not a sentence.', _LEGAL_FORM_OBJECT))
            continue
        if object_kinds is None:
            continue
        if kind not in object_kinds:
            near = _near_kinds(kind, object_kinds)
            out.append(_violation('step_structure_object_kind_unknown', f'{field}.kind', f"case {autoid} step {number}: {kind!r} is not an object path in this build's command tree. The path is the command-tree location of the head that creates or configures the object, with the leading operator word and the trailing action segment removed" + (f"; near paths in this tree: {', '.join(near)}" if near else '') + '.', _LEGAL_FORM_OBJECT))
    return out

@lru_cache(maxsize=256)
def _near_kinds(kind: str, object_kinds: frozenset[str]) -> tuple[str, ...]:
    from difflib import SequenceMatcher
    target = str(kind or '').casefold()[:MAX_KIND_CHARS]
    if not target:
        return ()
    scored = sorted(((-SequenceMatcher(None, target, candidate.casefold()).ratio(), candidate) for candidate in object_kinds))
    return tuple((candidate for _ratio, candidate in scored[:5]))

def _known_heads_note(grounded: Sequence[tuple[str, tuple[str, ...]]]) -> str:
    if not grounded:
        return 'none'
    shown = [command for command, _tokens in grounded[:MAX_KNOWN_HEADS_SHOWN]]
    rest = len(grounded) - len(shown)
    return ', '.join(shown) + (f', and {rest} more this case already grounded' if rest > 0 else '')

def _array_over_cap(items: list[Any], *, autoid: str, field: str, number: str, legal_form: str) -> dict[str, str] | None:
    if len(items) <= MAX_ENTRY_ARRAY_ITEMS:
        return None
    return _violation('step_structure_count_out_of_range', field, f'case {autoid} step {number}: this array carries {len(items)} entries; at most {MAX_ENTRY_ARRAY_ITEMS} are judged. State what the authored step names, not every form it could take.', legal_form)

def _operation_violations(entry: Mapping[str, Any], *, autoid: str, locus: str, number: str, grounded: Sequence[tuple[str, tuple[str, ...]]], known_heads: str='') -> list[dict[str, str]]:
    operations = entry.get('operations')
    if operations is None:
        operations = []
    if not isinstance(operations, list):
        return [_violation('step_structure_operation_head_unknown', f'{locus}.operations', f'case {autoid} step {number}: `operations` must be an array; got a JSON {type(operations).__name__}.', _LEGAL_FORM_OPERATION)]
    capped = _array_over_cap(operations, autoid=autoid, field=f'{locus}.operations', number=number, legal_form=_LEGAL_FORM_OPERATION)
    if capped is not None:
        return [capped]
    out: list[dict[str, str]] = []
    for position, item in enumerate(operations):
        field = f'{locus}.operations[{position}]'
        if not isinstance(item, Mapping) or set(item) != {'head', 'ref'}:
            out.append(_violation('step_structure_operation_head_unknown', field, f'case {autoid} step {number}: each operation is exactly `head` and `ref`; got ' + (', '.join(sorted(item)) if isinstance(item, Mapping) else f'a JSON {type(item).__name__}') + '.', _LEGAL_FORM_OPERATION))
            continue
        head = item.get('head')
        if not isinstance(head, str) or not _head_is_grounded(head, grounded):
            known = known_heads or _known_heads_note(grounded)
            out.append(_violation('step_structure_operation_head_unknown', f'{field}.head', f'case {autoid} step {number}: {_display_form(head, MAX_KIND_CHARS)!r} is not one of the command heads this case already grounded in command_check ({known}). Reuse a head you checked; inventing one here would put an unchecked command into the structure.', _LEGAL_FORM_OPERATION))
            continue
        ref = item.get('ref')
        if not isinstance(ref, str) or not ref.strip():
            out.append(_violation('step_structure_operation_head_unknown', f'{field}.ref', f'case {autoid} step {number}: `ref` names where this operation comes from; got {ref!r}.', _LEGAL_FORM_OPERATION))
    return out

def _condition_violations(entry: Mapping[str, Any], *, autoid: str, locus: str, number: str, step_text: str, adapted_text: str | None) -> list[dict[str, str]]:
    conditions = entry.get('stated_conditions')
    if conditions is None:
        conditions = []
    if not isinstance(conditions, list):
        return [_violation('step_structure_condition_not_verbatim', f'{locus}.stated_conditions', f'case {autoid} step {number}: `stated_conditions` must be an array; got a JSON {type(conditions).__name__}.', _LEGAL_FORM_CONDITION)]
    capped = _array_over_cap(conditions, autoid=autoid, field=f'{locus}.stated_conditions', number=number, legal_form=_LEGAL_FORM_CONDITION)
    if capped is not None:
        return [capped]
    from cex_core.engine.case_compiler.mindmap_contract_projector import ground_condition_author_text
    basis_text = adapted_text if adapted_text is not None else step_text
    basis_forms = _verbatim_forms(basis_text)
    out: list[dict[str, str]] = []
    for position, item in enumerate(conditions):
        field = f'{locus}.stated_conditions[{position}]'
        if not isinstance(item, Mapping) or set(item) not in ({'text', 'kind', 'value', 'author_text'}, {'text', 'kind', 'value'}):
            out.append(_violation('step_structure_condition_not_verbatim', field, f"case {autoid} step {number}: each stated condition is exactly `text`, `kind`, `value` and `author_text` (`author_text` may be omitted only for a step that needed no adaptation, where `text` already is the author's words); got " + (', '.join(sorted(item)) if isinstance(item, Mapping) else f'a JSON {type(item).__name__}') + '.', _LEGAL_FORM_CONDITION))
            continue
        kind = item.get('kind')
        if kind not in STRUCTURE_CONDITION_KINDS:
            out.append(_violation('step_structure_condition_not_verbatim', f'{field}.kind', f"case {autoid} step {number}: `kind` is one of {', '.join(STRUCTURE_CONDITION_KINDS)}; got {kind!r}.", _LEGAL_FORM_CONDITION))
            continue
        text = item.get('text')
        if not isinstance(text, str) or not text.strip():
            out.append(_violation('step_structure_condition_not_verbatim', f'{field}.text', f'case {autoid} step {number}: `text` must be a non-empty substring of the adapted step; got {_display_form(text, 200)!r}.', _LEGAL_FORM_CONDITION))
            continue
        if len(text) > MAX_CONDITION_TEXT_CHARS:
            out.append(_violation('step_structure_count_out_of_range', f'{field}.text', f'case {autoid} step {number}: `text` is at most {MAX_CONDITION_TEXT_CHARS} characters; got {len(text)}. It is the clause the adaptation states, not the step itself.', _LEGAL_FORM_CONDITION))
            continue
        if not any((form in step_form for form in _verbatim_forms(text) for step_form in basis_forms)):
            out.append(_violation('step_structure_condition_not_verbatim', f'{field}.text', f"case {autoid} step {number}: {_display_form(text)!r} does not occur in the adapted step. The adapted step reads {_display_form(basis_text)!r}. State the condition out of the adapted text; the author's original words belong in `author_text`.", _LEGAL_FORM_CONDITION))
            continue
        author_text = item.get('author_text')
        step_adapted = adapted_text is not None and step_is_adapted(step_text, adapted_text)
        if 'author_text' not in item and (not step_adapted):
            author_text = text
        if not isinstance(author_text, str) or not author_text.strip():
            out.append(_violation('step_structure_condition_not_verbatim', f'{field}.author_text', f"case {autoid} step {number}: this step was adapted, so `author_text` must name the span of the author's original text this condition corresponds to; got {_display_form(author_text, 200)!r}.", _LEGAL_FORM_CONDITION))
            continue
        if len(author_text) > MAX_CONDITION_TEXT_CHARS:
            out.append(_violation('step_structure_count_out_of_range', f'{field}.author_text', f'case {autoid} step {number}: `author_text` is at most {MAX_CONDITION_TEXT_CHARS} characters; got {len(author_text)}. It points at a clause of one authored step, not a passage.', _LEGAL_FORM_CONDITION))
            continue
        span = ground_condition_author_text(author_text, step_text)
        if span is None:
            out.append(_violation('step_structure_condition_not_verbatim', f'{field}.author_text', f"case {autoid} step {number}: `author_text` {_display_form(author_text)!r} does not occur in the sealed author step, even with whitespace runs normalized. The authored step reads {_display_form(step_text)!r}. Point at the author's actual words, not a retelling of them; the engine grounds this span, so small whitespace differences are corrected rather than rejected.", _LEGAL_FORM_CONDITION))
            continue
        value = item.get('value')
        if value is not None and (not isinstance(value, (str, int, float))):
            out.append(_violation('step_structure_condition_not_verbatim', f'{field}.value', f'case {autoid} step {number}: `value` is the literal the adaptation states, as a JSON string or number; got a JSON {type(value).__name__}.', _LEGAL_FORM_CONDITION))
            continue
        if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
            out.append(_violation('step_structure_count_out_of_range', f'{field}.value', f'case {autoid} step {number}: `value` is at most {MAX_VALUE_CHARS} characters; got {len(value)}. It is the literal the adaptation states — an algorithm name, a number, a bucket ratio — not a passage.', _LEGAL_FORM_CONDITION))
    return out

def _slot_violations(entry: Mapping[str, Any], *, autoid: str, locus: str, number: str, concretization_count: int) -> list[dict[str, str]]:
    slots = entry.get('free_slots')
    if slots is None:
        slots = []
    if not isinstance(slots, list):
        return [_violation('step_structure_slot_ref_unresolved', f'{locus}.free_slots', f'case {autoid} step {number}: `free_slots` must be an array; got a JSON {type(slots).__name__}.', _LEGAL_FORM_SLOT)]
    capped = _array_over_cap(slots, autoid=autoid, field=f'{locus}.free_slots', number=number, legal_form=_LEGAL_FORM_SLOT)
    if capped is not None:
        return [capped]
    out: list[dict[str, str]] = []
    for position, item in enumerate(slots):
        field = f'{locus}.free_slots[{position}]'
        if not isinstance(item, Mapping) or set(item) != {'slot', 'ref'}:
            out.append(_violation('step_structure_slot_ref_unresolved', field, f'case {autoid} step {number}: each free slot is exactly `slot` and `ref`; got ' + (', '.join(sorted(item)) if isinstance(item, Mapping) else f'a JSON {type(item).__name__}') + '. The value itself lives once at the target of `ref`.', _LEGAL_FORM_SLOT))
            continue
        slot = item.get('slot')
        if not isinstance(slot, str) or not slot.strip():
            out.append(_violation('step_structure_slot_ref_unresolved', f'{field}.slot', f'case {autoid} step {number}: `slot` names the free variable; got {slot!r}.', _LEGAL_FORM_SLOT))
            continue
        ref = str(item.get('ref') or '')
        resolved = _ref_index(ref, _CONCRETIZATION_REF_RE)
        if resolved is not None:
            if resolved < concretization_count:
                continue
            out.append(_violation('step_structure_slot_ref_unresolved', f'{field}.ref', f'case {autoid} step {number}: {ref} points past the end of `concretizations`, which has {concretization_count} entries. Record the witness there first, then point at its index.', _LEGAL_FORM_SLOT))
            continue
        out.append(_violation('step_structure_slot_ref_unresolved', f'{field}.ref', f'case {autoid} step {number}: {ref!r} is not a resolvable reference. Use `concretizations[<i>]` for a witness you recorded. `{ENGINE_SLOTS_KEY}` is engine-owned and carries no value a slot could point at.', _LEGAL_FORM_SLOT))
    return out

def stated_value_tokens(value: Any) -> list[str]:
    from cex_core.engine.case_compiler.vendor_stdlib import strip_token_quotes
    return [strip_token_quotes(token) for token in _VALUE_SPLIT_RE.split(str(value or '')) if token]

def stated_count_integers(value: Any) -> list[int]:
    tokens = stated_value_tokens(value)
    if not tokens or not all((token.isascii() and token.isdecimal() and (len(token) <= MAX_COUNT_DIGITS) for token in tokens)):
        return []
    return [int(token) for token in tokens]

def is_observation_step_entry(entry: Mapping[str, Any]) -> bool:
    roles = {str(item.get('role') or '') for item in entry.get('objects') or () if isinstance(item, Mapping)}
    if 'observed' in roles and (not roles & {'created', 'configured'}):
        return True
    probes = _probe_verbs()
    if not probes:
        return False
    for item in entry.get('operations') or ():
        if not isinstance(item, Mapping):
            continue
        tokens = _norm_head_tokens(item.get('head'))
        if tokens and tokens[0].casefold() in probes:
            return True
    return False

def engine_step_order(case: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for item in case.get('steps') or ():
        if not isinstance(item, Mapping):
            continue
        number = str(item.get('n') or '').strip()
        if number and number not in out:
            out.append(number)
    return out

def order_structure_entries(structure: Sequence[Mapping[str, Any]], order: Sequence[str]=()) -> list[Mapping[str, Any]]:
    entries = [entry for entry in structure if isinstance(entry, Mapping)]
    if not order:
        return entries
    rank = {number: index for index, number in enumerate(order)}
    tail = len(rank)
    return [entry for _key, entry in sorted((((rank.get(str(entry.get('n') or '').strip(), tail), position), entry) for position, entry in enumerate(entries)), key=lambda pair: pair[0])]

def observation_step_numbers(structure: Sequence[Mapping[str, Any]], *, order: Sequence[str]=()) -> list[str]:
    return [str(entry.get('n') or '').strip() for entry in order_structure_entries(structure, order) if str(entry.get('n') or '').strip() and is_observation_step_entry(entry)]

def concretized_weights(case: Mapping[str, Any], entry: Mapping[str, Any]) -> list[int]:
    concretizations = case.get('concretizations')
    if not isinstance(concretizations, list):
        return []
    for slot in entry.get('free_slots') or ():
        if not isinstance(slot, Mapping):
            continue
        if str(slot.get('slot') or '') != EFFECTIVE_WEIGHTS_SLOT:
            continue
        position = _ref_index(str(slot.get('ref') or ''), _CONCRETIZATION_REF_RE)
        if position is None or position >= len(concretizations):
            continue
        record = concretizations[position]
        if not isinstance(record, Mapping):
            continue
        if str(record.get('slot') or '') != EFFECTIVE_WEIGHTS_SLOT:
            continue
        weights = stated_count_integers(record.get('value'))
        if weights:
            return weights
    return []

def stated_weights(entry: Mapping[str, Any]) -> list[int]:
    for item in entry.get('stated_conditions') or ():
        if not isinstance(item, Mapping) or item.get('kind') != 'weight':
            continue
        weights = stated_count_integers(item.get('value'))
        if weights:
            return weights
    return []

def distribution_criterion_bindings(expectations: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in expectations or ():
        if not isinstance(item, Mapping):
            continue
        claim = item.get('normalized_claim')
        if not isinstance(claim, Mapping):
            continue
        if str(claim.get('criterion_type') or '') != 'distribution':
            continue
        out.append({'expectation_id': str(claim.get('expectation_id') or ''), 'semantic_key': str(claim.get('semantic_key') or ''), 'criterion_type': 'distribution', 'criterion_rule_id': str(claim.get('rule_id') or ''), 'shape_key': str(claim.get('shape_key') or '')})
    return out

def _slot_reason(*, paired: bool, ordered: bool=True) -> str:
    if not ordered or not paired:
        return 'pairing_ambiguous'
    return 'ok'

def apply_engine_slots(case: dict[str, Any], bindings: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    structure = case.get(STEP_STRUCTURE_KEY)
    if not isinstance(structure, list) or not bindings:
        return case
    order = engine_step_order(case)
    listed = [item for item in structure if isinstance(item, dict)]
    ordered = bool(order) or not listed
    entries = [entry for entry in order_structure_entries(listed, order) if isinstance(entry, dict)] if ordered else []
    records = case.get(ENGINE_SLOTS_KEY)
    if not isinstance(records, list):
        records = []
    signed = {(str(record.get('slot') or ''), str((record.get('claim') or {}).get('expectation_id') or '')) for record in records if isinstance(record, Mapping)}
    observations = observation_step_numbers(entries)
    paired = len(observations) == len(list(bindings))
    for position, binding in enumerate(bindings):
        key = (SAMPLING_DISCLOSURE_SLOT, str(binding.get('expectation_id') or ''))
        if key in signed:
            continue
        signed.add(key)
        observation_step = observations[position] if paired else ''
        if not ordered:
            basis = STEP_ORDER_UNAVAILABLE_BASIS
        elif paired and observation_step:
            basis = f'observation_pairing@step:{observation_step}'
        else:
            basis = 'observation_pairing_unavailable'
        records.append({'slot': SAMPLING_DISCLOSURE_SLOT, 'source': ENGINE_SLOT_SOURCE, 'claim': dict(binding), 'reason_code': _slot_reason(paired=paired, ordered=ordered), 'basis': basis, 'applies_to_steps': [observation_step] if paired and observation_step else []})
    if records:
        case[ENGINE_SLOTS_KEY] = records
    return case

def strip_engine_slots(case: dict[str, Any]) -> dict[str, Any]:
    case.pop(ENGINE_SLOTS_KEY, None)
    for entry in case.get(STEP_STRUCTURE_KEY) or ():
        if not isinstance(entry, dict):
            continue
        slots = entry.get('free_slots')
        if not isinstance(slots, list):
            continue
        entry['free_slots'] = [slot for slot in slots if not (isinstance(slot, Mapping) and _SLOT_REF_RE.match(str(slot.get('ref') or '')))]
    return case

def engine_sampling_records(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(record) for record in case.get(ENGINE_SLOTS_KEY) or () if isinstance(record, Mapping) and str(record.get('slot') or '') == SAMPLING_DISCLOSURE_SLOT]

def normalized_expectations_for_case(case: Mapping[str, Any], *, mindmap_text: str, mindmap_source_sha256: str='', defect_spec_receipt: Mapping[str, Any] | None=None, projection: Mapping[str, Any] | None=None) -> list[dict[str, Any]]:
    try:
        from cex_core.engine.case_compiler.criterion_normalization import normalize_case_expectations
        from cex_core.engine.case_compiler.mindmap_contract_projector import _expectations
        projected = _expectations(case, mindmap_source_sha256=str(mindmap_source_sha256 or ''), defect_spec_receipt=dict(defect_spec_receipt) if defect_spec_receipt else None)
        result = normalize_case_expectations(case=case, expectations=projected, mindmap_text=str(mindmap_text or ''), projection=projection)
        return [dict(item) for item in result.expectations]
    except Exception:
        logger.warning('criterion normalization unavailable for engine slots', exc_info=True)
        return []
__all__ = ['step_is_adapted', 'ADAPTED_STEPS_KEY', 'ADAPTED_STEP_KEYS', 'EFFECTIVE_WEIGHTS_SLOT', 'ENGINE_SLOTS_KEY', 'ENGINE_SLOT_SOURCE', 'MAX_CONDITION_TEXT_CHARS', 'MAX_COUNT_DIGITS', 'MAX_ENTRY_ARRAY_ITEMS', 'MAX_KIND_CHARS', 'MAX_OBJECT_COUNT', 'MAX_STRUCTURE_ENTRIES', 'MAX_VALUE_CHARS', 'MAX_VIOLATION_PAYLOAD_CHARS', 'ROLE_COMMAND_CLASSES', 'SAMPLING_DISCLOSURE_SLOT', 'SLOT_REASON_CODES', 'SUBSTITUTION_BASIS_BED_ROLE', 'SUBSTITUTION_BASIS_UNREACHABLE_ADDRESS', 'STEP_ORDER_UNAVAILABLE_BASIS', 'STEP_STRUCTURE_KEY', 'STRUCTURE_CONDITION_KINDS', 'STRUCTURE_ENTRY_KEYS', 'STRUCTURE_OBJECT_ROLES', 'LEGAL_FORM_ENTRY', 'VIOLATION_CODES', 'CommandRoleAtlas', 'adaptation_value_substitutions', 'adapted_step_texts', 'adapted_steps_violations', 'apply_engine_slots', 'budget_violations', 'case_has_adaptation', 'clear_object_kind_cache', 'command_role_atlas', 'distribution_criterion_bindings', 'concretized_weights', 'engine_sampling_records', 'engine_step_order', 'is_observation_step_entry', 'normalized_expectations_for_case', 'object_kind_closed_set', 'observation_step_numbers', 'order_structure_entries', 'recomputable_substitution_basis', 'stated_weights', 'sealed_structure_failures', 'stated_count_integers', 'stated_value_tokens', 'step_structure_violations', 'strip_engine_slots']
