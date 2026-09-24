# 生成：tools/extract_engine.py ← InfoTest scripts/gen_command_teardown_atlas.py（sha256 e8ccb7977d045ebc）。不在这里手改。
"""Generate the build-bound command teardown atlas.

The projection is intentionally generated from two executable authorities only:

* the active vendor command-tree XML for a device build;
* ``get_clear_list.CMD_RULES`` in the mirrored framework ``clear.py``;

Framework code is parsed with :mod:`ast`; it is never imported or executed. The
same run converges ``framework_cleanup_rules`` in ``domain_grammar.json`` (and
removes retired hand-authored domain sections), the atlas, and the clear.py
backfill report. Content-equivalent outputs are reused; incompatible outputs are
atomically replaced. ``--check`` verifies all outputs.

Regeneration (build 585)::

    ~/.venvs/infotest-engine/bin/python       scripts/gen_command_teardown_atlas.py --device-build 585 --version 10.5

The command is byte-stable on repeated runs.
"""
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import argparse
import ast
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
ROOT = _cex_data_path('')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cex_core.engine.common.schema_identity import accepts_schema
DEFAULT_COMMAND_TREE_ROOT = ROOT / 'runtime/command_tree/products/APV/platforms/HG-K/builds'
DEFAULT_CLEAR_PY = ROOT / 'knowledge/framework/mirror/lib/apv/clear.py'
DEFAULT_DOMAIN_GRAMMAR = ROOT / 'knowledge/data/compile_ref/domain_grammar.json'
DEFAULT_OUTPUT = ROOT / 'knowledge/data/compile_ref/command_teardown_atlas.json'
DEFAULT_BACKFILL_OUTPUT = ROOT / 'workspace/outputs/clear_py_backfill_candidates.md'
ATLAS_SCHEMA = 'ist.command-teardown-atlas'
FRAMEWORK_CLEANUP_RULES_SCHEMA = 'ist.framework-cleanup-rules'
ACTIVE_SCHEMA = 'ist.command-tree.active'
MANIFEST_SCHEMA = 'ist.command-tree.generation'
TOKEN_RE = re.compile('^[A-Za-z0-9_.-]+$')
SAFE_COMPONENT_RE = re.compile('^[A-Za-z0-9_.-]+$')
SHA256_RE = re.compile('^[0-9a-f]{64}$')
SWITCH_STATES = frozenset({'on', 'off', 'enable', 'disable'})
CLASS_NAMES = ('C1', 'C2', 'C2b', 'C3')
NON_WRITE_ROOTS = frozenset({'no', 'clear', 'show'})

class TeardownAtlasError(ValueError):
    pass

@dataclass(frozen=True)
class CommandTreeSource:
    version: str
    device_build: str
    partition: Path
    generation_id: str
    generation_root: Path
    xml_path: Path
    xml_sha256: str
    xml_size: int
    manifest_path: Path
    manifest_sha256: str

@dataclass(frozen=True)
class ClearRule:
    order: int
    line: int
    prefixes: tuple[str, ...]
    cleanup_commands: tuple[str, ...]

    def as_dict(self, source_path: str) -> dict[str, Any]:
        return {'order': self.order, 'prefixes': list(self.prefixes), 'cleanup_commands': list(self.cleanup_commands), 'source': f'{source_path}:{self.line}', 'line': self.line}

@dataclass(frozen=True)
class XmlCommandNode:
    head: str
    tokens: tuple[str, ...]
    tag: str
    user_level: str
    src: str
    parent_head: str
    origin: str = 'vendor_xml'
    argument_count: int = 0

@dataclass(frozen=True)
class XmlProjection:
    nodes: tuple[XmlCommandNode, ...]
    tag_counts: Mapping[str, int]
    user_level_counts: Mapping[str, int]
    token_valid_node_count: int

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))

def _read_regular(path: Path, *, label: str, max_bytes: int) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise TeardownAtlasError(f'{label} is unavailable: {path}') from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise TeardownAtlasError(f'{label} must be a real regular file: {path}')
    if before.st_size <= 0 or before.st_size > max_bytes:
        raise TeardownAtlasError(f'{label} size is outside the parser budget')
    try:
        data = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise TeardownAtlasError(f'{label} cannot be read: {path}') from exc
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or len(data) != before.st_size:
        raise TeardownAtlasError(f'{label} changed while it was being read')
    return data

def _reject_duplicate_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TeardownAtlasError(f'JSON contains duplicate key: {key}')
        result[key] = value
    return result

def _load_json_bytes(raw: bytes, *, label: str) -> Any:
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TeardownAtlasError(f'{label} is not valid UTF-8 JSON') from exc

def _relative(path: Path, root: Path=ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()

def _validated_component(value: str, *, label: str) -> str:
    text = str(value or '').strip()
    if not text or not SAFE_COMPONENT_RE.fullmatch(text):
        raise TeardownAtlasError(f'{label} contains an unsafe path component')
    return text

def locate_active_command_tree(device_build: str, *, version: str | None=None, command_tree_root: Path=DEFAULT_COMMAND_TREE_ROOT) -> CommandTreeSource:
    build = _validated_component(device_build, label='device build')
    root = command_tree_root.resolve()
    try:
        root_info = root.lstat()
    except OSError as exc:
        raise TeardownAtlasError(f'command-tree root is unavailable: {root}') from exc
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise TeardownAtlasError('command-tree root must be a real directory')
    if version is not None:
        ver = _validated_component(version, label='version')
        partitions = [root / f'{ver}_{build}']
    else:
        partitions = sorted((path for path in root.glob(f'*_{build}') if path.is_dir()))
    partitions = [path for path in partitions if path.is_dir()]
    if len(partitions) != 1:
        raise TeardownAtlasError(f'device build {build} resolves to {len(partitions)} build partitions')
    partition = partitions[0]
    suffix = f'_{build}'
    if not partition.name.endswith(suffix):
        raise TeardownAtlasError('build partition name does not bind the requested build')
    resolved_version = partition.name[:-len(suffix)]
    _validated_component(resolved_version, label='resolved version')
    active_path = partition / 'active.json'
    active_raw = _read_regular(active_path, label='command-tree active pointer', max_bytes=64 * 1024)
    active = _load_json_bytes(active_raw, label='command-tree active pointer')
    if not isinstance(active, dict) or not accepts_schema(active.get('schema'), ACTIVE_SCHEMA):
        raise TeardownAtlasError('command-tree active pointer has an unsupported schema')
    generation_id = _validated_component(active.get('generation_id'), label='generation id')
    declared_manifest_sha = str(active.get('manifest_sha256') or '')
    if not SHA256_RE.fullmatch(declared_manifest_sha):
        raise TeardownAtlasError('command-tree active pointer has an invalid manifest digest')
    generation_root = partition / 'generations' / generation_id
    try:
        generation_info = generation_root.lstat()
    except OSError as exc:
        raise TeardownAtlasError('active command-tree generation is unavailable') from exc
    if stat.S_ISLNK(generation_info.st_mode) or not stat.S_ISDIR(generation_info.st_mode):
        raise TeardownAtlasError('active command-tree generation must be a real directory')
    manifest_path = generation_root / 'manifest.json'
    manifest_raw = _read_regular(manifest_path, label='command-tree generation manifest', max_bytes=512 * 1024)
    manifest_sha = _sha256_bytes(manifest_raw)
    if manifest_sha != declared_manifest_sha:
        raise TeardownAtlasError('active pointer does not bind the generation manifest')
    manifest = _load_json_bytes(manifest_raw, label='command-tree generation manifest')
    if not isinstance(manifest, dict) or not accepts_schema(manifest.get('schema'), MANIFEST_SCHEMA):
        raise TeardownAtlasError('command-tree generation manifest has an unsupported schema')
    if str(manifest.get('generation_id') or '') != generation_id:
        raise TeardownAtlasError('generation manifest id does not match active pointer')
    if str(manifest.get('device_build') or '') != build:
        raise TeardownAtlasError('generation manifest does not bind the requested build')
    if str(manifest.get('version') or '') != resolved_version:
        raise TeardownAtlasError('generation manifest does not bind the resolved version')
    xml_name = f'cmdtree_{build}.xml'
    artifacts = manifest.get('artifacts')
    declaration = artifacts.get(xml_name) if isinstance(artifacts, dict) else None
    if not isinstance(declaration, dict):
        raise TeardownAtlasError('generation manifest does not declare the command-tree XML')
    declared_xml_sha = str(declaration.get('sha256') or '')
    declared_xml_size = declaration.get('size')
    if not SHA256_RE.fullmatch(declared_xml_sha):
        raise TeardownAtlasError('generation manifest has an invalid XML digest')
    if not isinstance(declared_xml_size, int) or declared_xml_size <= 0:
        raise TeardownAtlasError('generation manifest has an invalid XML size')
    xml_path = generation_root / xml_name
    xml_raw = _read_regular(xml_path, label='vendor command-tree XML', max_bytes=32 * 1024 * 1024)
    if len(xml_raw) != declared_xml_size or _sha256_bytes(xml_raw) != declared_xml_sha:
        raise TeardownAtlasError('vendor command-tree XML does not match its manifest')
    active_xmls = sorted(generation_root.glob(f'cmdtree_{build}.xml'))
    if active_xmls != [xml_path]:
        raise TeardownAtlasError('active generation has an ambiguous command-tree XML')
    return CommandTreeSource(version=resolved_version, device_build=build, partition=partition, generation_id=generation_id, generation_root=generation_root, xml_path=xml_path, xml_sha256=declared_xml_sha, xml_size=declared_xml_size, manifest_path=manifest_path, manifest_sha256=manifest_sha)

def _parse_startswith_expression(node: ast.AST, *, argument_name: str) -> tuple[str, ...]:
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        prefixes: list[str] = []
        for value in node.values:
            prefixes.extend(_parse_startswith_expression(value, argument_name=argument_name))
        return tuple(prefixes)
    if not (isinstance(node, ast.Call) and (not node.keywords) and (len(node.args) == 1) and isinstance(node.func, ast.Attribute) and (node.func.attr == 'startswith') and isinstance(node.func.value, ast.Name) and (node.func.value.id == argument_name) and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and node.args[0].value):
        raise TeardownAtlasError('CMD_RULES predicate must be an OR of literal cmd.startswith(...) calls')
    return (node.args[0].value,)

def parse_clear_rules_bytes(source: bytes, *, filename: str='clear.py') -> tuple[ClearRule, ...]:
    try:
        text = source.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise TeardownAtlasError(f'{filename} is not UTF-8') from exc
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError as exc:
        raise TeardownAtlasError(f'{filename} cannot be parsed') from exc
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'get_clear_list']
    if len(functions) != 1 or not isinstance(functions[0], ast.FunctionDef):
        raise TeardownAtlasError('clear.py must contain exactly one synchronous get_clear_list')
    function = functions[0]
    assignments = [node for node in function.body if isinstance(node, (ast.Assign, ast.AnnAssign)) and (any((isinstance(target, ast.Name) and target.id == 'CMD_RULES' for target in node.targets)) if isinstance(node, ast.Assign) else isinstance(node.target, ast.Name) and node.target.id == 'CMD_RULES')]
    if len(assignments) != 1:
        raise TeardownAtlasError('get_clear_list must contain exactly one direct CMD_RULES assignment')
    assignment = assignments[0]
    value = assignment.value
    if not isinstance(value, (ast.List, ast.Tuple)):
        raise TeardownAtlasError('CMD_RULES must be a literal ordered list')
    rules: list[ClearRule] = []
    for order, element in enumerate(value.elts):
        if not isinstance(element, (ast.Tuple, ast.List)) or len(element.elts) != 2:
            raise TeardownAtlasError('each CMD_RULES entry must be a two-item tuple')
        predicate, cleanup_expr = element.elts
        if not isinstance(predicate, ast.Lambda):
            raise TeardownAtlasError('each CMD_RULES predicate must be a lambda')
        args = predicate.args
        if len(args.args) != 1 or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults or args.kw_defaults:
            raise TeardownAtlasError('CMD_RULES lambda must accept exactly one plain argument')
        argument_name = args.args[0].arg
        prefixes = _parse_startswith_expression(predicate.body, argument_name=argument_name)
        if len(set(prefixes)) != len(prefixes):
            raise TeardownAtlasError('CMD_RULES predicate repeats a startswith prefix')
        try:
            cleanup_value = ast.literal_eval(cleanup_expr)
        except (ValueError, TypeError, SyntaxError) as exc:
            raise TeardownAtlasError('CMD_RULES cleanup commands must be literal strings') from exc
        if not (isinstance(cleanup_value, (list, tuple)) and cleanup_value and all((isinstance(item, str) and item for item in cleanup_value))):
            raise TeardownAtlasError('CMD_RULES cleanup commands must be a non-empty string list')
        rules.append(ClearRule(order=order, line=element.lineno, prefixes=prefixes, cleanup_commands=tuple(cleanup_value)))
    if not rules:
        raise TeardownAtlasError('CMD_RULES cannot be empty')
    return tuple(rules)

def parse_clear_rules(clear_py: Path=DEFAULT_CLEAR_PY) -> tuple[ClearRule, ...]:
    raw = _read_regular(clear_py, label='framework clear.py', max_bytes=4 * 1024 * 1024)
    return parse_clear_rules_bytes(raw, filename=str(clear_py))

def first_matching_clear_rule(head: str, rules: Sequence[ClearRule]) -> ClearRule | None:
    for rule in rules:
        if any((head.startswith(prefix) for prefix in rule.prefixes)):
            return rule
    return None

def parse_command_tree_bytes(source: bytes, *, device_build: str) -> XmlProjection:
    if b'<!DOCTYPE' in source.upper() or b'<!ENTITY' in source.upper():
        raise TeardownAtlasError('vendor command-tree XML cannot contain DTD/entity declarations')
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise TeardownAtlasError('vendor command-tree XML cannot be parsed') from exc
    if root.tag != 'commands':
        raise TeardownAtlasError('vendor command-tree XML root must be <commands>')
    nodes: list[XmlCommandNode] = []
    tags: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    valid_tokens = 0
    seen_elements = 0

    def walk(parent: ET.Element, head_tokens: tuple[str, ...], src_parts: tuple[str, ...], depth: int) -> None:
        nonlocal seen_elements, valid_tokens
        if depth > 96:
            raise TeardownAtlasError('vendor command-tree XML exceeds the depth budget')
        for child in parent:
            seen_elements += 1
            if seen_elements > 250000:
                raise TeardownAtlasError('vendor command-tree XML exceeds the node budget')
            if child.tag == 'scope':
                label = str(child.get('name') or child.get('type') or '').strip()
                if not label:
                    raise TeardownAtlasError('vendor XML scope is missing its name/type')
                walk(child, head_tokens, src_parts + (label.lower(),), depth + 1)
                continue
            if child.tag not in {'menu', 'item'}:
                continue
            raw_name = str(child.get('name') or '').strip()
            if not raw_name:
                raise TeardownAtlasError(f'vendor XML {child.tag} is missing its name')
            token = raw_name.lower()
            tokens = head_tokens + (token,)
            src_tokens = src_parts + (token,)
            head = ' '.join(tokens)
            parent_head = ' '.join(head_tokens)
            user_level = str(child.get('user_level') or '').strip()
            if not user_level:
                raise TeardownAtlasError(f'vendor XML command node lacks user_level: {head}')
            src = f"vendor_xml:{device_build}:{'/'.join(src_tokens)}"
            node = XmlCommandNode(head=head, tokens=tokens, tag=child.tag, user_level=user_level, src=src, parent_head=parent_head, argument_count=sum((len(block.findall('arg')) for block in child.findall('arguments'))))
            nodes.append(node)
            tags[child.tag] += 1
            levels[user_level] += 1
            if all((TOKEN_RE.fullmatch(item) for item in tokens)):
                valid_tokens += 1
            if child.tag == 'menu':
                walk(child, tokens, src_tokens, depth + 1)
    walk(root, (), (), 1)
    if not nodes:
        raise TeardownAtlasError('vendor command-tree XML contains no command nodes')
    return XmlProjection(nodes=tuple(nodes), tag_counts=dict(sorted(tags.items())), user_level_counts=dict(sorted(levels.items())), token_valid_node_count=valid_tokens)

def parse_command_tree(source: CommandTreeSource) -> XmlProjection:
    raw = _read_regular(source.xml_path, label='vendor command-tree XML', max_bytes=32 * 1024 * 1024)
    if _sha256_bytes(raw) != source.xml_sha256 or len(raw) != source.xml_size:
        raise TeardownAtlasError('vendor command-tree XML identity changed after resolution')
    return parse_command_tree_bytes(raw, device_build=source.device_build)

def _normalize_direction_sources(value: Any, *, base: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise TeardownAtlasError(f'switch direction {base!r} sources must be a list')
    normalized: list[Mapping[str, Any]] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append({'ref': item.strip()})
        elif isinstance(item, dict) and isinstance(item.get('ref'), str) and item['ref'].strip():
            normalized.append(dict(sorted(item.items())))
        else:
            raise TeardownAtlasError(f'switch direction {base!r} has an invalid source')
    return tuple(normalized)

def framework_cleanup_rules_section(atlas: Mapping[str, Any]) -> dict[str, Any]:
    validate_atlas(atlas)
    rules = list(atlas.get('clear_rules') or [])
    identity = atlas['identity']
    return {'schema': FRAMEWORK_CLEANUP_RULES_SCHEMA, '_provenance': "Generated mechanically from command_teardown_atlas.clear_rules; source order and first-match semantics are authoritative. Do not reduce this table to first-token module scopes. WHAT THIS IS: the prefixes the test framework already resets between cases, in first-match order. It answers 'does the framework clean this up for me' — it is NOT a menu of teardown steps to write into a case. The concrete reset commands are deliberately omitted here: many are module-wide (`clear <module> all`) whose blast radius far exceeds the one object a case created, and handing those to a case author is the exact accident this project already paid for (a suggested `clear slb all` was escalated to `clear config all` and killed two device beds). Object-scoped teardown for your own case must be derived from the command tree (`lang_query`), not copied from this table.", 'source_identity': {'atlas_schema': atlas['schema'], 'atlas_identity_sha256': identity['sha256'], 'device_build': atlas['device_build'], 'version': atlas['version'], 'xml_sha256': identity['xml']['sha256'], 'clear_py_path': identity['clear_py']['path'], 'clear_py_sha256': identity['clear_py']['sha256'], 'generator': atlas['generator']}, 'rule_count': len(rules), 'ordered_prefix_count': sum((len(rule.get('prefixes') or []) for rule in rules)), 'rules': [{'order': rule.get('order'), 'prefixes': list(rule.get('prefixes') or []), 'cleanup_command_count': len(rule.get('cleanup_commands') or []), 'source': rule.get('source'), 'line': rule.get('line')} for rule in rules]}

def _xml_evidence(nodes: Iterable[XmlCommandNode]) -> dict[str, Any]:
    material = tuple(nodes)
    tags = sorted({node.tag for node in material}, key=lambda value: (value != 'item', value))
    return {'src': sorted({node.src for node in material}), 'node_tags': tags, 'user_levels': sorted({node.user_level for node in material}), 'executable_item': 'item' in tags}
RUNNING_CONFIG_SHOW_HEAD = 'show running'
_REGEX_METACHARACTERS = frozenset('\\^$.|?*+()[]{}')

def _running_config_filter(head: str) -> str:
    return ''.join((f'\\{char}' if char in _REGEX_METACHARACTERS else char for char in str(head or '')))

def _observation_for_head(head: str, node_index: Mapping[str, Sequence[XmlCommandNode]]) -> dict[str, Any]:
    tokens = head.split()

    def executable(candidate: str) -> dict[str, Any] | None:
        nodes = node_index.get(candidate) or ()
        evidence = _xml_evidence(nodes) if nodes else None
        return evidence if evidence and evidence.get('executable_item') else None
    candidates: list[tuple[str, str]] = [('exact_head', f'show {head}')]
    if tokens and tokens[-1] in SWITCH_STATES and (len(tokens) > 1):
        candidates.append(('switch_base', 'show ' + ' '.join(tokens[:-1])))
    for size in range(len(tokens), 0, -1):
        prefix = ' '.join(tokens[:size])
        candidates.append(('aggregate_ancestor', f'show {prefix} all'))
    for size in range(len(tokens) - 1, 0, -1):
        prefix = ' '.join(tokens[:size])
        candidates.append(('exact_ancestor', f'show {prefix}'))
    seen: set[str] = set()
    for derivation, candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        evidence = executable(candidate)
        if evidence:
            return {'status': 'mapped', 'derivation': derivation, 'show_head': candidate, 'xml_evidence': evidence, 'expected_clean': {'mode': 'no_forward_head_line', 'forward_head': head, 'comparison': 'token_prefix'}}
    executable_heads = sorted((candidate for candidate, nodes in node_index.items() if candidate.startswith('show ') and _xml_evidence(nodes).get('executable_item')))
    ambiguous: list[str] = []
    for size in range(len(tokens), 0, -1):
        prefix = 'show ' + ' '.join(tokens[:size]) + ' '
        descendants = [candidate for candidate in executable_heads if candidate.startswith(prefix)]
        if len(descendants) == 1:
            candidate = descendants[0]
            return {'status': 'mapped', 'derivation': 'unique_descendant', 'show_head': candidate, 'xml_evidence': _xml_evidence(node_index[candidate]), 'expected_clean': {'mode': 'no_forward_head_line', 'forward_head': head, 'comparison': 'token_prefix'}}
        if descendants and (not ambiguous):
            ambiguous = descendants
    running_evidence = executable(RUNNING_CONFIG_SHOW_HEAD)
    accepts_filter = any((node.argument_count > 0 for node in node_index.get(RUNNING_CONFIG_SHOW_HEAD) or ()))
    if running_evidence and accepts_filter:
        return {'status': 'mapped', 'derivation': 'running_config_fallback', 'show_head': RUNNING_CONFIG_SHOW_HEAD, 'show_args': [_running_config_filter(head)], 'candidate_show_heads': ambiguous, 'xml_evidence': running_evidence, 'expected_clean': {'mode': 'no_forward_head_line', 'forward_head': head, 'comparison': 'token_prefix'}}
    return {'status': 'atlas_gap', 'derivation': 'unresolved_or_ambiguous', 'show_head': None, 'candidate_show_heads': ambiguous, 'expected_clean': {'mode': 'unavailable', 'forward_head': head, 'comparison': 'none'}}

def build_atlas(source: CommandTreeSource, xml: XmlProjection, clear_rules: Sequence[ClearRule], *, clear_py_path: Path=DEFAULT_CLEAR_PY, clear_py_sha256: str | None=None, direction_source: Mapping[str, Any] | None=None) -> dict[str, Any]:
    if clear_py_sha256 is None:
        clear_raw = _read_regular(clear_py_path, label='framework clear.py', max_bytes=4 * 1024 * 1024)
        clear_py_sha256 = _sha256_bytes(clear_raw)
    if not SHA256_RE.fullmatch(clear_py_sha256):
        raise TeardownAtlasError('clear.py SHA256 is invalid')
    node_index: dict[str, list[XmlCommandNode]] = defaultdict(list)
    for node in xml.nodes:
        node_index[node.head].append(node)
    clean_items: dict[str, list[XmlCommandNode]] = defaultdict(list)
    config_item_rows = 0
    valid_config_item_rows = 0
    for node in xml.nodes:
        if node.origin != 'vendor_xml' or node.tag != 'item':
            continue
        if node.user_level != 'CLI_LEVEL_CONFIG':
            continue
        config_item_rows += 1
        if not all((TOKEN_RE.fullmatch(token) for token in node.tokens)):
            continue
        valid_config_item_rows += 1
        clean_items[node.head].append(node)
    configuration_writes = {head: nodes for head, nodes in clean_items.items() if head.split()[0] not in NON_WRITE_ROOTS}
    if not configuration_writes:
        raise TeardownAtlasError('cleaned command-write domain is empty')
    clear_source = _relative(clear_py_path)
    records: dict[str, dict[str, Any]] = {}
    by_class: dict[str, list[str]] = {name: [] for name in CLASS_NAMES}
    c2_evidence_tags: Counter[str] = Counter()
    for head in sorted(configuration_writes):
        forward_nodes = configuration_writes[head]
        clear_rule = first_matching_clear_rule(head, clear_rules)
        provenance: dict[str, Any] = {'xml': _xml_evidence(forward_nodes), 'clear_rule': None, 'manual_anchors': []}
        teardown: dict[str, Any]
        classification: str
        if clear_rule is not None:
            classification = 'C1'
            rule_payload = clear_rule.as_dict(clear_source)
            provenance['clear_rule'] = rule_payload['source']
            teardown = {'status': 'framework_cleanup_rule', 'suggested_inverse': clear_rule.cleanup_commands[0], 'suggested_inverses': list(clear_rule.cleanup_commands), 'framework_rule_order': clear_rule.order, 'matched_prefixes': [prefix for prefix in clear_rule.prefixes if head.startswith(prefix)]}
        else:
            tokens = head.split()
            matches: list[dict[str, Any]] = []
            for prefix_length in range(len(tokens), 0, -1):
                prefix = ' '.join(tokens[:prefix_length])
                candidates = (('no_prefix', f'no {prefix}'), ('clear_prefix', f'clear {prefix}'), ('no_prefix_all', f'no {prefix} all'), ('clear_prefix_all', f'clear {prefix} all'))
                for form_order, (form, candidate) in enumerate(candidates):
                    evidence_nodes = node_index.get(candidate)
                    if not evidence_nodes:
                        continue
                    evidence = _xml_evidence(evidence_nodes)
                    matches.append({'candidate': candidate, 'form': form, 'form_order': form_order, 'matched_forward_prefix': prefix, 'matched_forward_prefix_tokens': prefix_length, 'xml': evidence})
            if matches:
                chosen = min(matches, key=lambda item: (0 if item['xml']['executable_item'] else 1, -item['matched_forward_prefix_tokens'], item['form_order'], item['candidate']))
                classification = 'C2'
                evidence_kind = 'item' if chosen['xml']['executable_item'] else 'menu'
                c2_evidence_tags[evidence_kind] += 1
                teardown = {'status': 'xml_executable_inverse' if chosen['xml']['executable_item'] else 'xml_inverse_ancestor', 'suggested_inverse': chosen['candidate'], 'suggested_inverses': [chosen['candidate']], 'suggested_inverse_executable': chosen['xml']['executable_item'], 'requires_specialization': not chosen['xml']['executable_item'], 'matched_form': chosen['form'], 'matched_forward_prefix': chosen['matched_forward_prefix'], 'xml_evidence': chosen['xml']}
            else:
                terminal_state = tokens[-1] if tokens[-1] in SWITCH_STATES else None
                base = ' '.join(tokens[:-1]) if terminal_state else head
                sibling_heads = sorted((sibling_head for sibling_head in configuration_writes if sibling_head != head and sibling_head.rsplit(' ', 1)[0] == base and (sibling_head.rsplit(' ', 1)[-1] in SWITCH_STATES)))
                if terminal_state is not None and sibling_heads:
                    inverse_head = next((s for s in sibling_heads if s.rsplit(' ', 1)[-1] != terminal_state), None)
                    classification = 'C2'
                    teardown = {'status': 'xml_switch_sibling_inverse', 'suggested_inverse': inverse_head, 'suggested_inverses': [inverse_head] if inverse_head else [], 'suggested_inverse_executable': inverse_head is not None, 'requires_specialization': False, 'matched_form': 'switch_sibling', 'configured_state': terminal_state, 'switch_base': base, 'switch_siblings': sibling_heads}
                else:
                    classification = 'C3'
                    teardown = {'status': 'no_mechanical_inverse', 'suggested_inverse': None, 'suggested_inverses': []}
        records[head] = {'head': head, 'tokens': head.split(), 'class': classification, 'origin': 'vendor_xml', 'xml': {'tag': 'item', 'user_level': 'CLI_LEVEL_CONFIG', 'src': sorted({node.src for node in forward_nodes}), 'variant_count': len(forward_nodes)}, 'teardown': teardown, 'observation': _observation_for_head(head, node_index), 'provenance': provenance}
        by_class[classification].append(head)
    xml_identity = {'path': _relative(source.xml_path), 'sha256': source.xml_sha256, 'size': source.xml_size, 'generation_id': source.generation_id, 'manifest_path': _relative(source.manifest_path), 'manifest_sha256': source.manifest_sha256}
    clear_identity = {'path': clear_source, 'sha256': clear_py_sha256}
    identity_material = json.dumps({'clear_py_sha256': clear_py_sha256, 'xml_sha256': source.xml_sha256}, sort_keys=True, separators=(',', ':')).encode('utf-8')
    class_stats = {name: {'count': len(by_class[name]), 'ratio': round(len(by_class[name]) / len(records), 6)} for name in CLASS_NAMES}
    observation_mapped_count = sum(((record.get('observation') or {}).get('status') == 'mapped' for record in records.values()))
    payload = {'schema': ATLAS_SCHEMA, 'version': source.version, 'device_build': source.device_build, 'generator': 'scripts/gen_command_teardown_atlas.py', 'identity': {'schema': 'ist.command-teardown-identity', 'xml': xml_identity, 'clear_py': clear_identity, 'sha256': _sha256_bytes(identity_material), 'composition': 'sha256(canonical_json({clear_py_sha256,xml_sha256}))'}, 'auxiliary_sources': {'switch_default_directions': dict(direction_source or {'path': _relative(DEFAULT_DOMAIN_GRAMMAR), 'sha256': None, 'section_sha256': None, 'domain_grammar_sha256': None, 'present': False, 'schema': None})}, 'policy': {'domain_cleaning': [{'criterion': 'origin == vendor_xml', 'provenance': ['scripts/maintenance/build_vendor_stdlib.py:vendor headers origin', 'manual worked examples excluded: heads whose origin is not vendor_xml are prose examples carrying instance values']}, {'criterion': 'XML tag == item', 'provenance': 'vendor XML structure: menu is a non-executable container'}, {'criterion': 'XML @user_level == CLI_LEVEL_CONFIG', 'provenance': 'vendor XML @user_level declaration'}, {'criterion': 'every XML path token matches ^[A-Za-z0-9_.-]+$', 'provenance': 'vendor XML command-name lexical structure'}], 'configuration_write_selection': {'excluded_roots': sorted(NON_WRITE_ROOTS), 'provenance': 'command grammar: no/clear are teardown operators and show is read-only'}, 'classification_precedence': list(CLASS_NAMES), 'C1': 'first source-ordered clear.py CMD_RULES startswith match; stop after first hit', 'C2': 'non-C1 with an XML no/clear prefix ancestor, including no/clear X all; item evidence is preferred over menu evidence', 'C2b': 'non-C1/non-C2 switch terminal or same-base switch sibling; default direction comes only from switch_default_directions', 'C3': 'no mechanical inverse found by C1/C2/C2b'}, 'stats': {'xml_command_node_count': len(xml.nodes), 'xml_tag_counts': dict(xml.tag_counts), 'xml_user_level_counts': dict(xml.user_level_counts), 'xml_token_valid_node_count': xml.token_valid_node_count, 'config_item_rows': config_item_rows, 'valid_config_item_rows': valid_config_item_rows, 'unique_config_item_heads': len(clean_items), 'configuration_write_head_count': len(records), 'write_selection_excluded_head_count': len(clean_items) - len(records), 'clear_rule_count': len(clear_rules), 'clear_rule_prefix_count': sum((len(rule.prefixes) for rule in clear_rules)), 'clear_rules_with_multiple_cleanup_commands': sum((len(rule.cleanup_commands) > 1 for rule in clear_rules)), 'C2_evidence_node_tags': dict(sorted(c2_evidence_tags.items())), 'classes': class_stats, 'observation_mapped_count': observation_mapped_count, 'observation_gap_count': len(records) - observation_mapped_count}, 'clear_rules': [rule.as_dict(clear_source) for rule in clear_rules], 'classes': by_class, 'commands': records}
    validate_atlas(payload)
    return payload

def validate_atlas(payload: Mapping[str, Any]) -> None:
    if not accepts_schema(payload.get('schema'), ATLAS_SCHEMA):
        raise TeardownAtlasError('teardown atlas has an unsupported schema')
    build = str(payload.get('device_build') or '')
    version = str(payload.get('version') or '')
    _validated_component(build, label='atlas device build')
    _validated_component(version, label='atlas version')
    identity = payload.get('identity')
    if not isinstance(identity, dict):
        raise TeardownAtlasError('teardown atlas identity is missing')
    xml_identity = identity.get('xml')
    clear_identity = identity.get('clear_py')
    if not isinstance(xml_identity, dict) or not isinstance(clear_identity, dict):
        raise TeardownAtlasError('teardown atlas source identity is malformed')
    xml_sha = str(xml_identity.get('sha256') or '')
    clear_sha = str(clear_identity.get('sha256') or '')
    if not SHA256_RE.fullmatch(xml_sha) or not SHA256_RE.fullmatch(clear_sha):
        raise TeardownAtlasError('teardown atlas source digest is malformed')
    expected_identity = _sha256_bytes(json.dumps({'clear_py_sha256': clear_sha, 'xml_sha256': xml_sha}, sort_keys=True, separators=(',', ':')).encode('utf-8'))
    if identity.get('sha256') != expected_identity:
        raise TeardownAtlasError('teardown atlas composite identity is invalid')
    commands = payload.get('commands')
    classes = payload.get('classes')
    if not isinstance(commands, dict) or not isinstance(classes, dict):
        raise TeardownAtlasError('teardown atlas command/class maps are missing')
    if set(classes) != set(CLASS_NAMES):
        raise TeardownAtlasError('teardown atlas class map is not closed')
    seen: set[str] = set()
    for class_name in CLASS_NAMES:
        heads = classes[class_name]
        if not isinstance(heads, list) or heads != sorted(heads) or len(heads) != len(set(heads)):
            raise TeardownAtlasError(f'teardown atlas {class_name} list is not deterministic')
        for head in heads:
            if head in seen:
                raise TeardownAtlasError('teardown atlas head appears in multiple classes')
            seen.add(head)
            record = commands.get(head)
            if not isinstance(record, dict) or record.get('head') != head:
                raise TeardownAtlasError('teardown atlas record/head mismatch')
            if record.get('class') != class_name:
                raise TeardownAtlasError('teardown atlas record/class mismatch')
            tokens = record.get('tokens')
            if not isinstance(tokens, list) or ' '.join(tokens) != head:
                raise TeardownAtlasError('teardown atlas tokens do not reconstruct the head')
            if not all((isinstance(token, str) and TOKEN_RE.fullmatch(token) for token in tokens)):
                raise TeardownAtlasError('teardown atlas contains an invalid token')
            observation = record.get('observation')
            if not isinstance(observation, dict) or observation.get('status') not in {'mapped', 'atlas_gap'}:
                raise TeardownAtlasError('teardown atlas observation mapping is invalid')
            expected_clean = observation.get('expected_clean')
            if not isinstance(expected_clean, dict) or expected_clean.get('forward_head') != head:
                raise TeardownAtlasError('teardown atlas clean-state binding is invalid')
            if observation['status'] == 'mapped':
                show_head = str(observation.get('show_head') or '')
                evidence = observation.get('xml_evidence')
                if not show_head.startswith('show ') or not isinstance(evidence, dict) or evidence.get('executable_item') is not True or (expected_clean.get('mode') != 'no_forward_head_line') or (expected_clean.get('comparison') != 'token_prefix'):
                    raise TeardownAtlasError('teardown atlas mapped observation is invalid')
                show_args = observation.get('show_args')
                if show_head == RUNNING_CONFIG_SHOW_HEAD:
                    if show_args != [_running_config_filter(head)] or observation.get('derivation') != 'running_config_fallback':
                        raise TeardownAtlasError('teardown atlas running-config observation lacks its literal filter')
                elif show_args is not None:
                    raise TeardownAtlasError('teardown atlas observation carries arguments for a bare show head')
            elif observation.get('show_head') is not None or not isinstance(observation.get('candidate_show_heads'), list) or expected_clean.get('mode') != 'unavailable':
                raise TeardownAtlasError('teardown atlas observation gap is invalid')
    if seen != set(commands):
        raise TeardownAtlasError('teardown atlas class map does not cover every command')
    stats = payload.get('stats')
    class_stats = stats.get('classes') if isinstance(stats, dict) else None
    if not isinstance(class_stats, dict):
        raise TeardownAtlasError('teardown atlas class statistics are missing')
    for class_name in CLASS_NAMES:
        entry = class_stats.get(class_name)
        if not isinstance(entry, dict) or entry.get('count') != len(classes[class_name]):
            raise TeardownAtlasError('teardown atlas class statistics are inconsistent')
    if stats.get('configuration_write_head_count') != len(commands):
        raise TeardownAtlasError('teardown atlas total statistics are inconsistent')
    mapped_count = sum(((record.get('observation') or {}).get('status') == 'mapped' for record in commands.values()))
    if stats.get('observation_mapped_count') != mapped_count or stats.get('observation_gap_count') != len(commands) - mapped_count:
        raise TeardownAtlasError('teardown atlas observation statistics are inconsistent')

def load_command_teardown_atlas(path: Path=DEFAULT_OUTPUT, *, expected_build: str | None=None) -> dict[str, Any]:
    raw = _read_regular(path, label='command teardown atlas', max_bytes=64 * 1024 * 1024)
    payload = _load_json_bytes(raw, label='command teardown atlas')
    if not isinstance(payload, dict):
        raise TeardownAtlasError('command teardown atlas root must be an object')
    validate_atlas(payload)
    if expected_build is not None and payload.get('device_build') != str(expected_build):
        raise TeardownAtlasError('command teardown atlas is bound to a different build')
    return payload

def verify_atlas_source_identity(payload: Mapping[str, Any], *, command_tree_root: Path=DEFAULT_COMMAND_TREE_ROOT, clear_py_path: Path=DEFAULT_CLEAR_PY, domain_grammar_path: Path=DEFAULT_DOMAIN_GRAMMAR) -> None:
    validate_atlas(payload)
    source = locate_active_command_tree(str(payload['device_build']), version=str(payload['version']), command_tree_root=command_tree_root)
    identity = payload['identity']
    if source.xml_sha256 != identity['xml']['sha256']:
        raise TeardownAtlasError('command teardown atlas XML identity is stale')
    clear_raw = _read_regular(clear_py_path, label='framework clear.py', max_bytes=4 * 1024 * 1024)
    if _sha256_bytes(clear_raw) != identity['clear_py']['sha256']:
        raise TeardownAtlasError('command teardown atlas clear.py identity is stale')

def command_record(atlas: Mapping[str, Any], head: str) -> Mapping[str, Any] | None:
    validate_atlas(atlas)
    normalized = ' '.join(str(head or '').strip().lower().split())
    record = atlas['commands'].get(normalized)
    return record if isinstance(record, dict) else None

def generate_atlas(device_build: str, *, version: str | None=None, command_tree_root: Path=DEFAULT_COMMAND_TREE_ROOT, clear_py_path: Path=DEFAULT_CLEAR_PY, domain_grammar_path: Path=DEFAULT_DOMAIN_GRAMMAR) -> dict[str, Any]:
    source = locate_active_command_tree(device_build, version=version, command_tree_root=command_tree_root)
    xml = parse_command_tree(source)
    clear_raw = _read_regular(clear_py_path, label='framework clear.py', max_bytes=4 * 1024 * 1024)
    rules = parse_clear_rules_bytes(clear_raw, filename=str(clear_py_path))
    return build_atlas(source, xml, rules, clear_py_path=clear_py_path, clear_py_sha256=_sha256_bytes(clear_raw), direction_source={'path': _relative(domain_grammar_path), 'sha256': None, 'section_sha256': None, 'domain_grammar_sha256': _sha256_bytes(_read_regular(domain_grammar_path, label='domain grammar', max_bytes=16 * 1024 * 1024)), 'present': False, 'schema': None})

def _top_level_property_spans(text: str) -> dict[str, tuple[int, int]]:
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_pairs)
    length = len(text)
    index = 0

    def skip_space(position: int) -> int:
        while position < length and text[position].isspace():
            position += 1
        return position
    index = skip_space(index)
    if index >= length or text[index] != '{':
        raise TeardownAtlasError('domain grammar root must be an object')
    index += 1
    spans: dict[str, tuple[int, int]] = {}
    while True:
        index = skip_space(index)
        if index < length and text[index] == '}':
            break
        key_start = index
        try:
            key, key_end = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise TeardownAtlasError('domain grammar top-level key cannot be parsed') from exc
        if not isinstance(key, str) or key in spans:
            raise TeardownAtlasError('domain grammar has an invalid/duplicate top-level key')
        index = skip_space(key_end)
        if index >= length or text[index] != ':':
            raise TeardownAtlasError('domain grammar top-level property lacks a colon')
        index = skip_space(index + 1)
        try:
            _value, value_end = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise TeardownAtlasError(f'domain grammar section {key!r} cannot be parsed') from exc
        spans[key] = (key_start, value_end)
        index = skip_space(value_end)
        if index < length and text[index] == ',':
            index += 1
            continue
        if index < length and text[index] == '}':
            break
        raise TeardownAtlasError('domain grammar top-level delimiter is malformed')
    return spans

def _render_top_level_property(key: str, value: Mapping[str, Any]) -> str:
    rendered_value = json.dumps(value, ensure_ascii=False, indent=1)
    return json.dumps(key, ensure_ascii=False) + ': ' + rendered_value.replace('\n', '\n ')

def render_domain_grammar_sections(original: bytes, *, framework_section: Mapping[str, Any]) -> bytes:
    try:
        text = original.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise TeardownAtlasError('domain grammar is not UTF-8') from exc
    before = _load_json_bytes(original, label='domain grammar')
    if not isinstance(before, dict):
        raise TeardownAtlasError('domain grammar root must be an object')
    spans = _top_level_property_spans(text)
    has_rules = 'framework_cleanup_rules' in spans
    has_legacy_scopes = 'framework_cleanup_scopes' in spans
    if has_rules == has_legacy_scopes:
        raise TeardownAtlasError('domain grammar must contain exactly one framework cleanup section')
    operations: list[tuple[int, int, str]] = []
    framework_source_key = 'framework_cleanup_rules' if has_rules else 'framework_cleanup_scopes'
    framework_start, framework_end = spans[framework_source_key]
    operations.append((framework_start, framework_end, _render_top_level_property('framework_cleanup_rules', framework_section)))
    for retired_key in ('switch_default_directions', 'bed_domain_preflight', 'endpoint_address_semantics'):
        if retired_key not in spans:
            continue
        start, end = spans[retired_key]
        tail = text[end:]
        drop_end = end + (len(tail) - len(tail.lstrip(', \n'))) if tail[:1] in {',', ' ', '\n'} else end
        operations.append((start, drop_end, ''))
    updated = text
    for start, end, replacement in sorted(operations, reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    encoded = updated.encode('utf-8')
    after = _load_json_bytes(encoded, label='generated domain grammar')
    if not isinstance(after, dict):
        raise TeardownAtlasError('generated domain grammar root must be an object')
    owned = {'framework_cleanup_rules', 'framework_cleanup_scopes', 'switch_default_directions', 'bed_domain_preflight', 'endpoint_address_semantics'}
    before_rest = {key: value for key, value in before.items() if key not in owned}
    after_rest = {key: value for key, value in after.items() if key not in owned}
    if before_rest != after_rest:
        raise TeardownAtlasError('domain grammar generation changed an unowned section')
    if after.get('framework_cleanup_rules') != dict(framework_section):
        raise TeardownAtlasError('framework cleanup section did not round-trip')
    if 'framework_cleanup_scopes' in after:
        raise TeardownAtlasError('legacy framework_cleanup_scopes survived generation')
    if 'switch_default_directions' in after:
        raise TeardownAtlasError('retired switch direction section survived generation')
    if 'bed_domain_preflight' in after:
        raise TeardownAtlasError('retired bed-domain preflight section survived generation')
    if 'endpoint_address_semantics' in after:
        raise TeardownAtlasError('retired endpoint-address semantics survived generation')
    return encoded
_DANGEROUS_BACKFILL_ROOTS = frozenset({'admin', 'bond', 'cluster', 'config', 'debug', 'ha', 'hostname', 'interface', 'ip', 'ipv6', 'ntp', 'passwd', 'synconfig', 'system', 'vlan', 'write'})

def clear_py_backfill_rows(atlas: Mapping[str, Any]) -> list[dict[str, Any]]:
    validate_atlas(atlas)
    rows: list[dict[str, Any]] = []
    for head, record in sorted((atlas.get('commands') or {}).items()):
        if record.get('class') not in {'C2', 'C2b'}:
            continue
        teardown = dict(record.get('teardown') or {})
        suggestion = teardown.get('suggested_inverse')
        specialization = bool(teardown.get('requires_specialization'))
        first = head.split()[0]
        suggestion_tokens = str(suggestion or '').split()
        suggestion_root = suggestion_tokens[1] if suggestion_tokens and suggestion_tokens[0] in {'no', 'clear'} and (len(suggestion_tokens) > 1) else suggestion_tokens[0] if suggestion_tokens else ''
        dangerous = first in _DANGEROUS_BACKFILL_ROOTS or suggestion_root in _DANGEROUS_BACKFILL_ROOTS or head.startswith('segment ha ')
        module_clear_all = bool(suggestion_tokens and suggestion_tokens[0] == 'clear' and (suggestion_tokens[-1] == 'all'))
        if dangerous:
            risk = 'dangerous_global_surface'
            risk_reason = 'touches a global/system baseline surface'
            risk_reason_zh = '触碰全局、系统或 step0 基线配置面'
        elif specialization or not suggestion or module_clear_all:
            risk = 'needs_evaluation'
            risk_reason = 'inverse is unknown/container-only or clears an aggregate module'
            risk_reason_zh = '逆元未知、仅有 menu 祖先，或会聚合清除整个模块'
        elif suggestion_tokens and suggestion_tokens[0] == 'no':
            risk = 'safe_object_level_deletion'
            risk_reason = 'exact object-level no-form'
            risk_reason_zh = '存在对象级 no 形态；具体参数可能仍需绑定'
        else:
            risk = 'needs_evaluation'
            risk_reason = 'cleanup is not a proven object-level no-form'
            risk_reason_zh = '尚未证明是对象级 no 删除，需评估作用范围'
        refs: set[str] = set((record.get('xml') or {}).get('src') or [])
        refs.update((teardown.get('xml_evidence') or {}).get('src') or [])
        for source in teardown.get('direction_sources') or []:
            ref = str(source.get('ref') or '') if isinstance(source, dict) else ''
            if ref:
                refs.add(ref)
        if record.get('provenance', {}).get('clear_rule'):
            refs.add(str(record['provenance']['clear_rule']))
        rows.append({'head': head, 'class': record['class'], 'suggested_inverse': suggestion, 'suggestion_status': str(teardown.get('status') or ''), 'requires_specialization': specialization, 'provenance': sorted(refs), 'risk': risk, 'risk_label_zh': {'safe_object_level_deletion': '安全', 'needs_evaluation': '需评估', 'dangerous_global_surface': '危险'}[risk], 'risk_reason': risk_reason, 'risk_reason_zh': risk_reason_zh})
    return rows

def _md_cell(value: Any) -> str:
    return str(value).replace('|', '\\|').replace('\n', '<br>')

def render_clear_py_backfill_report(atlas: Mapping[str, Any], *, domain_grammar_sha256: str) -> str:
    rows = clear_py_backfill_rows(atlas)
    if str(atlas.get('device_build')) == '585' and len(rows) != 827:
        raise TeardownAtlasError(f'build 585 backfill count drifted: {len(rows)}')
    risk_counts = Counter((row['risk'] for row in rows))
    dangerous_surface_counts = {prefix.strip(): sum((row['head'].startswith(prefix) for row in rows)) for prefix in ('system ', 'config ', 'admin ', 'ha ', 'segment ha ', 'debug ')}
    unknown = sum((row['suggested_inverse'] is None for row in rows))
    specialization = sum((row['requires_specialization'] for row in rows))
    identity = atlas['identity']
    lines = ['# clear.py 反哺候选（生成式）', '', '> 本文件由 `scripts/gen_command_teardown_atlas.py` 生成；手改会在再生时覆盖。', '', '## 身份与范围', '', f"- device build：`{atlas['device_build']}`（version `{atlas['version']}`）", f"- atlas identity：`{identity['sha256']}`", f"- XML SHA-256：`{identity['xml']['sha256']}`", f"- clear.py SHA-256：`{identity['clear_py']['sha256']}`", f'- domain_grammar SHA-256：`{domain_grammar_sha256}`', f'- 候选：{len(rows)}（C2+C2b）', f'- unknown 建议：{unknown}；需进一步具体化：{specialization}', '', '## 风险口径', '', f"- 安全（safe_object_level_deletion）：{risk_counts['safe_object_level_deletion']}；对象级 `no` 形态，参数可能仍需绑定。", f"- 需评估（needs_evaluation）：{risk_counts['needs_evaluation']}；聚合 `clear X all`、menu 祖先或 unknown，必须评估。", f"- 危险（dangerous_global_surface）：{risk_counts['dangerous_global_surface']}；触碰 system/config/admin/ha/debug（含 segment ha）及类似全局基线。", '- 危险面候选计数：' + '；'.join((f'{name}={count}' for name, count in dangerous_surface_counts.items())) + '（直接 ha 命令已由 C1 框架规则承接，因此本候选集为 0）。', '', '“安全”只表示破坏半径是对象级，不等于该字符串可以直接粘进 clear.py。XML item 可能仍声明必填参数；对象参数如何从用例命令绑定到清理命令，仍需实现与评估。', '', '危险项不得直接写入跳转机框架：`clear config`、system/admin/ha 等全局清理可能连 step0 下发的全局基线一起删除。未来修改 clear.py 前必须先执行 `backup_jumphost_framework --contract-scope`，再按契约范围部署。', '', '## 候选明细', '', '| # | 命令头 | 类别 | 建议逆元/清理 | 状态 | 出处 | 风险 |', '|---:|---|---|---|---|---|---|']
    for index, row in enumerate(rows, 1):
        suggestion = row['suggested_inverse']
        if suggestion is None:
            suggestion_text = 'unknown（默认方向待测，不得机械翻转）'
        elif row['requires_specialization']:
            suggestion_text = f'{suggestion} …（XML menu 祖先，需具体化）'
        else:
            suggestion_text = str(suggestion)
        provenance = '<br>'.join((_md_cell(ref) for ref in row['provenance']))
        class_text = {'C2': 'C2（XML 逆元）', 'C2b': 'C2b（开关默认方向）'}.get(row['class'], row['class'])
        status_text = {'xml_executable_inverse': 'XML 可执行逆元', 'xml_inverse_ancestor': 'XML menu 逆元祖先', 'known_default': '默认方向已知', 'unknown_default': '默认方向未知'}.get(row['suggestion_status'], row['suggestion_status'])
        lines.append(f"| {index} | `{_md_cell(row['head'])}` | {_md_cell(class_text)} | `{_md_cell(suggestion_text)}` | {_md_cell(status_text)}（{_md_cell(row['suggestion_status'])}） | {provenance} | {_md_cell(row['risk_label_zh'])}（{_md_cell(row['risk'])}）：{_md_cell(row['risk_reason_zh'])} |")
    return '\n'.join(lines) + '\n'

@dataclass(frozen=True)
class GeneratedProjectionSet:
    domain_grammar_bytes: bytes
    atlas: Mapping[str, Any]
    backfill_report: str
    framework_section: Mapping[str, Any]

def generate_projection_set(device_build: str, *, version: str | None=None, command_tree_root: Path=DEFAULT_COMMAND_TREE_ROOT, clear_py_path: Path=DEFAULT_CLEAR_PY, domain_grammar_path: Path=DEFAULT_DOMAIN_GRAMMAR) -> GeneratedProjectionSet:
    source = locate_active_command_tree(device_build, version=version, command_tree_root=command_tree_root)
    xml = parse_command_tree(source)
    clear_raw = _read_regular(clear_py_path, label='framework clear.py', max_bytes=4 * 1024 * 1024)
    rules = parse_clear_rules_bytes(clear_raw, filename=str(clear_py_path))
    clear_sha = _sha256_bytes(clear_raw)
    domain_raw = _read_regular(domain_grammar_path, label='domain grammar', max_bytes=16 * 1024 * 1024)
    base_atlas = build_atlas(source, xml, rules, clear_py_path=clear_py_path, clear_py_sha256=clear_sha, direction_source={'path': _relative(domain_grammar_path), 'sha256': None, 'section_sha256': None, 'domain_grammar_sha256': None, 'present': False, 'schema': None})
    framework_section = framework_cleanup_rules_section(base_atlas)
    domain_bytes = render_domain_grammar_sections(domain_raw, framework_section=framework_section)
    final_atlas = build_atlas(source, xml, rules, clear_py_path=clear_py_path, clear_py_sha256=clear_sha, direction_source={'path': _relative(domain_grammar_path), 'sha256': None, 'section_sha256': None, 'domain_grammar_sha256': _sha256_bytes(domain_bytes), 'present': False, 'schema': None})
    report = render_clear_py_backfill_report(final_atlas, domain_grammar_sha256=_sha256_bytes(domain_bytes))
    return GeneratedProjectionSet(domain_grammar_bytes=domain_bytes, atlas=final_atlas, backfill_report=report, framework_section=framework_section)

def render_atlas(payload: Mapping[str, Any]) -> str:
    validate_atlas(payload)
    return json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + '\n'

def _write_bytes_atomic(path: Path, payload: bytes, *, mode: int=420) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass

def write_atlas(path: Path, payload: Mapping[str, Any]) -> None:
    _write_bytes_atomic(path, render_atlas(payload).encode('utf-8'))

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device-build', required=True)
    parser.add_argument('--version')
    parser.add_argument('--command-tree-root', type=Path, default=DEFAULT_COMMAND_TREE_ROOT)
    parser.add_argument('--clear-py', type=Path, default=DEFAULT_CLEAR_PY)
    parser.add_argument('--domain-grammar', type=Path, default=DEFAULT_DOMAIN_GRAMMAR)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--backfill-output', type=Path, default=DEFAULT_BACKFILL_OUTPUT)
    parser.add_argument('--check', action='store_true', help='verify domain grammar generated sections, atlas, and backfill report byte-for-byte without rewriting')
    return parser
_GENERATION_RECORD_FIELDS = ('generation_id', 'manifest_path', 'manifest_sha256', 'path')

def _atlas_content_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    validate_atlas(payload)
    normalized = json.loads(json.dumps(dict(payload)))
    for field in _GENERATION_RECORD_FIELDS:
        normalized['identity']['xml'].pop(field, None)
    return normalized

def atlas_content_sha256(payload: Mapping[str, Any]) -> str:
    return _canonical_sha256(_atlas_content_payload(payload))

def _content_identity_payload(raw: bytes) -> dict | None:
    try:
        payload = _load_json_bytes(raw, label='command teardown atlas')
    except TeardownAtlasError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return _atlas_content_payload(payload)
    except TeardownAtlasError:
        return None

def _atlas_is_content_equivalent(current: bytes, rendered: bytes) -> bool:
    left = _content_identity_payload(current)
    right = _content_identity_payload(rendered)
    if left is None or right is None:
        return False
    lx = (left.get('identity') or {}).get('xml') or {}
    rx = (right.get('identity') or {}).get('xml') or {}
    lc = (left.get('identity') or {}).get('clear_py') or {}
    rc = (right.get('identity') or {}).get('clear_py') or {}
    if lx.get('sha256') != rx.get('sha256') or lc.get('sha256') != rc.get('sha256'):
        return False
    return left == right

def _converge_generated_bytes(path: Path, rendered: bytes, *, label: str, max_bytes: int, equivalent: Callable[[bytes, bytes], bool] | None=None) -> bool:
    if path.is_symlink():
        raise TeardownAtlasError(f'{label} must not be a symbolic link')
    current: bytes | None = None
    if path.exists():
        current = _read_regular(path, label=label, max_bytes=max_bytes)
    if current == rendered or (current is not None and equivalent is not None and equivalent(current, rendered)):
        return False
    _write_bytes_atomic(path, rendered)
    return True

def main(argv: Sequence[str] | None=None) -> int:
    args = _parser().parse_args(argv)
    generated = generate_projection_set(args.device_build, version=args.version, command_tree_root=args.command_tree_root, clear_py_path=args.clear_py, domain_grammar_path=args.domain_grammar)
    payload = generated.atlas
    rendered_atlas = render_atlas(payload).encode('utf-8')
    rendered_report = generated.backfill_report.encode('utf-8')
    convergence_status = 'checked'
    if args.check:
        current_domain = _read_regular(args.domain_grammar, label='domain grammar', max_bytes=16 * 1024 * 1024)
        if current_domain != generated.domain_grammar_bytes:
            raise TeardownAtlasError('domain grammar generated sections are stale; rerun without --check')
        current_atlas = _read_regular(args.output, label='command teardown atlas', max_bytes=64 * 1024 * 1024)
        if current_atlas != rendered_atlas and (not _atlas_is_content_equivalent(current_atlas, rendered_atlas)):
            raise TeardownAtlasError('command teardown atlas is stale; rerun without --check')
        if args.backfill_output.exists() or args.backfill_output.is_symlink():
            current_report = _read_regular(args.backfill_output, label='clear.py backfill report', max_bytes=32 * 1024 * 1024)
            if current_report != rendered_report:
                raise TeardownAtlasError('clear.py backfill report is stale; rerun without --check')
        else:
            print(f'skipped {args.backfill_output}: absent (untracked review by-product); grammar and atlas were still verified')
            convergence_status = 'checked (backfill report absent)'
    else:
        changed: list[str] = []
        if _converge_generated_bytes(args.domain_grammar, generated.domain_grammar_bytes, label='domain grammar', max_bytes=16 * 1024 * 1024):
            changed.append('domain_grammar')
        if _converge_generated_bytes(args.output, rendered_atlas, label='command teardown atlas', max_bytes=64 * 1024 * 1024, equivalent=_atlas_is_content_equivalent):
            changed.append('command_teardown_atlas')
        if _converge_generated_bytes(args.backfill_output, rendered_report, label='clear.py backfill report', max_bytes=32 * 1024 * 1024):
            changed.append('clear_py_backfill_report')
        convergence_status = 'updated=' + ','.join(changed) if changed else 'reused=all'
    stats = payload['stats']
    counts = stats['classes']
    print(f"converged {args.output} + domain sections + {args.backfill_output}: total={stats['configuration_write_head_count']} " + ' '.join((f"{name}={counts[name]['count']}" for name in CLASS_NAMES)) + f" identity={payload['identity']['sha256']} {convergence_status}")
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
