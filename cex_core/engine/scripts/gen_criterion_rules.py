# 生成：tools/extract_engine.py ← InfoTest scripts/gen_criterion_rules.py（sha256 f7915346876f1389）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import argparse
import ast
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence
ROOT = _cex_data_path('')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cex_core.engine.case_compiler.criterion_carriers import carrier_contract_sha256, criterion_type_blueprints
DEFAULT_SOURCE = ROOT / 'scripts/data/criterion_rule_sources.json'
DEFAULT_ATLAS = ROOT / 'knowledge/data/compile_ref/command_teardown_atlas.json'
DEFAULT_OUTPUT = ROOT / 'knowledge/data/compile_ref/criterion_rules.json'
STEP_GRAPH = ROOT / 'main/case_compiler/step_graph.py'
BLOCKS_SCHEMA = ROOT / 'knowledge/data/compile_ref/blocks_schema.json'
DOMAIN_GRAMMAR = ROOT / 'knowledge/data/compile_ref/domain_grammar.json'
CARRIER_SOURCE = ROOT / 'main/case_compiler/criterion_carriers.py'
IDENTITY_KINDS = frozenset({'mathematical_derivation', 'manual_anchor', 'author_signature', 'user_ruling'})

class CriterionRuleGenerationError(RuntimeError):

    def __init__(self, message: str, *, reason_code: str='', source_path: str='') -> None:
        super().__init__(message)
        self.reason_code = reason_code or 'criterion_rule_generation_failed'
        self.source_path = source_path

    def disclosure(self) -> dict[str, str]:
        return {'reason_code': self.reason_code, 'source_path': self.source_path}

def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CriterionRuleGenerationError(f'unreadable JSON source: {path}') from exc
    if not isinstance(value, dict):
        raise CriterionRuleGenerationError(f'JSON source must be an object: {path}')
    return value

def _literal_string_set(path: Path, name: str) -> frozenset[str]:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise CriterionRuleGenerationError(f'cannot parse language source: {path}') from exc
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any((isinstance(target, ast.Name) and target.id == name for target in targets)):
            continue
        literal_node = node.value
        if isinstance(literal_node, ast.Call) and isinstance(literal_node.func, ast.Name) and (literal_node.func.id in {'set', 'frozenset', 'tuple', 'list'}) and (len(literal_node.args) == 1) and (not literal_node.keywords):
            literal_node = literal_node.args[0]
        try:
            value = ast.literal_eval(literal_node)
        except (ValueError, TypeError) as exc:
            raise CriterionRuleGenerationError(f'{name} is not a literal closed set') from exc
        if not isinstance(value, (set, frozenset, tuple, list)):
            raise CriterionRuleGenerationError(f'{name} is not a collection')
        return frozenset((str(item) for item in value))
    raise CriterionRuleGenerationError(f'language closed set not found: {name}')

def derive_criterion_types(*, step_graph_path: Path=STEP_GRAPH, blocks_schema_path: Path=BLOCKS_SCHEMA) -> list[dict[str, Any]]:
    operators = _literal_string_set(step_graph_path, '_FOUND_OPS')
    block_payload = _read_json(blocks_schema_path)
    blocks = frozenset((str(value) for value in (block_payload.get('closed_sets') or {}).get('kinds') or []))
    if not operators or not blocks:
        raise CriterionRuleGenerationError('L operator or block closed set is empty')
    out: list[dict[str, Any]] = []
    for blueprint in criterion_type_blueprints():
        missing_ops = sorted(set(blueprint['operators']) - operators)
        missing_blocks = sorted(set(blueprint['block_kinds']) - blocks)
        if missing_ops or missing_blocks:
            raise CriterionRuleGenerationError(f"criterion lowering is outside the current L closed set: {blueprint['criterion_type']} ops={missing_ops} blocks={missing_blocks}")
        out.append(dict(blueprint))
    if len({row['criterion_type'] for row in out}) != len(out):
        raise CriterionRuleGenerationError('criterion type catalogue contains duplicate types')
    return out

def _symbol_exists(path: Path, symbol: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, SyntaxError):
        return False
    return any((isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol or (isinstance(node, (ast.Assign, ast.AnnAssign)) and any((isinstance(target, ast.Name) and target.id == symbol for target in (node.targets if isinstance(node, ast.Assign) else [node.target])))) for node in tree.body))

def _manual_anchor(identity: Mapping[str, Any]) -> dict[str, Any]:
    from cex_core.engine.case_compiler.mindmap_contract_projector import ground_source_span
    rel = str(identity.get('source_path') or '')
    quote = str(identity.get('quote') or '')
    path = ROOT / rel
    if not rel or not quote or (not path.is_file()) or (not path.resolve().is_relative_to(ROOT)):
        raise CriterionRuleGenerationError('manual identity has no bounded source', reason_code='manual_anchor_source_unbounded', source_path=str(rel or ''))
    text = path.read_text(encoding='utf-8')
    span = ground_source_span(quote, text, origin='manual')
    if span is None:
        raise CriterionRuleGenerationError(f'manual quote is not grounded: {rel}', reason_code='manual_anchor_quote_not_grounded', source_path=str(rel))
    line_start = text.count('\n', 0, int(span['start'])) + 1
    line_end = text.count('\n', 0, int(span['end'])) + 1
    return {'kind': 'manual_anchor', 'source_path': rel, 'source_sha256': _sha256_bytes(path.read_bytes()), 'source_span': span, 'line_start': line_start, 'line_end': line_end, 'quote': quote}

def _mathematical_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    proofs = identity.get('proofs')
    if not isinstance(proofs, list) or not proofs:
        raise CriterionRuleGenerationError('mathematical identity has no proof list')
    normalized: list[dict[str, str]] = []
    for proof in proofs:
        if not isinstance(proof, dict):
            raise CriterionRuleGenerationError('mathematical proof must be an object')
        rel = str(proof.get('source_path') or '')
        symbol = str(proof.get('symbol') or '')
        claim = str(proof.get('claim') or '')
        path = ROOT / rel
        if not rel or not symbol or (not claim) or (not path.is_file()) or (not path.resolve().is_relative_to(ROOT)) or (not _symbol_exists(path, symbol)):
            raise CriterionRuleGenerationError(f'mathematical proof is not mechanically resolvable: {rel}:{symbol}')
        normalized.append({'source_path': rel, 'source_sha256': _sha256_bytes(path.read_bytes()), 'symbol': symbol, 'claim': claim})
    return {'kind': 'mathematical_derivation', 'proofs': normalized}

def _author_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    required = {'kind', 'signer', 'signed_at', 'question_digest', 'answer_receipt_sha256'}
    if set(identity) != required or identity.get('kind') != 'author_signature':
        raise CriterionRuleGenerationError('author signature fields are not closed')
    if not all((str(identity.get(key) or '').strip() for key in required - {'kind'})):
        raise CriterionRuleGenerationError('author signature is incomplete')
    for key in ('question_digest', 'answer_receipt_sha256'):
        value = str(identity.get(key) or '')
        if len(value) != 64 or any((char not in '0123456789abcdef' for char in value)):
            raise CriterionRuleGenerationError('author signature digest is invalid')
    return dict(identity)

def _user_ruling_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    required = {'kind', 'ruling_id', 'authority', 'ruled_at', 'decision', 'manual_method_anchor'}
    if set(identity) != required or identity.get('kind') != 'user_ruling':
        raise CriterionRuleGenerationError('user ruling fields are not closed')
    if identity.get('authority') != 'user' or str(identity.get('ruled_at') or '') != '2026-08-23' or (not str(identity.get('ruling_id') or '').strip()) or (not str(identity.get('decision') or '').strip()) or (not isinstance(identity.get('manual_method_anchor'), Mapping)):
        raise CriterionRuleGenerationError('user ruling identity is incomplete')
    return {'kind': 'user_ruling', 'ruling_id': str(identity['ruling_id']), 'authority': 'user', 'ruled_at': '2026-08-23', 'decision': str(identity['decision']), 'manual_method_anchor': _manual_anchor({'kind': 'manual_anchor', **dict(identity['manual_method_anchor'])})}

def _normalize_identity(identity: Any) -> dict[str, Any]:
    if not isinstance(identity, dict) or identity.get('kind') not in IDENTITY_KINDS:
        raise CriterionRuleGenerationError('rule candidate needs mathematical_derivation, manual_anchor, author_signature, or user_ruling identity')
    kind = str(identity['kind'])
    if kind == 'manual_anchor':
        return _manual_anchor(identity)
    if kind == 'mathematical_derivation':
        return _mathematical_identity(identity)
    if kind == 'user_ruling':
        return _user_ruling_identity(identity)
    return _author_identity(identity)

def _command_heads(atlas: Mapping[str, Any]) -> tuple[str, ...]:
    commands = atlas.get('commands')
    if not isinstance(commands, dict):
        raise CriterionRuleGenerationError('command atlas has no commands object')
    return tuple(sorted((str(head) for head in commands if str(head).strip())))

def _reject_concrete_command(candidate: Mapping[str, Any], heads: Sequence[str]) -> None:
    inspected = {key: value for key, value in candidate.items() if key != 'identity'}
    text = json.dumps(inspected, ensure_ascii=False, sort_keys=True).casefold()
    hits = []
    for head in heads:
        normalized = str(head or '').strip().casefold()
        if not normalized:
            continue
        if ' ' in normalized:
            matched = normalized in text
        else:
            matched = re.search(f'(?<![A-Za-z0-9_]){re.escape(normalized)}(?![A-Za-z0-9_])', text) is not None
        if matched:
            hits.append(str(head))
    if hits:
        raise CriterionRuleGenerationError('rule text contains a concrete command head: ' + ', '.join(hits[:3]))

def compile_rule_candidate(candidate: Mapping[str, Any], *, criterion_types: set[str], command_heads: Sequence[str]) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise CriterionRuleGenerationError('rule candidate must be an object')
    required = {'rule_id', 'description', 'predicate', 'output', 'identity'}
    if set(candidate) != required:
        raise CriterionRuleGenerationError('rule candidate fields are not closed')
    rule_id = str(candidate.get('rule_id') or '')
    predicate = candidate.get('predicate')
    output = candidate.get('output')
    if not rule_id or not isinstance(predicate, dict) or (not isinstance(output, dict)):
        raise CriterionRuleGenerationError('rule candidate body is incomplete')
    criterion_type = str(output.get('criterion_type') or '')
    if criterion_type not in criterion_types:
        raise CriterionRuleGenerationError('rule output criterion_type is outside the catalogue')
    _reject_concrete_command(candidate, command_heads)
    identity = _normalize_identity(candidate.get('identity'))
    body = {'schema': 'ist.criterion-rule', 'rule_id': rule_id, 'description': str(candidate.get('description') or ''), 'predicate': dict(predicate), 'output': dict(output), 'identity': identity}
    return {**body, 'rule_sha256': _sha256_bytes(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))}

def _object_classes(source: Mapping[str, Any], atlas: Mapping[str, Any]) -> dict[str, Any]:
    raw = source.get('object_classes')
    commands = atlas.get('commands')
    if not isinstance(raw, dict) or not isinstance(commands, dict):
        raise CriterionRuleGenerationError('object class inputs are unavailable')
    out: dict[str, Any] = {}
    for class_id, spec in sorted(raw.items()):
        if not isinstance(spec, dict):
            raise CriterionRuleGenerationError('object class source must be an object')
        markers = {str(value).casefold() for value in spec.get('atlas_tokens') or [] if str(value).strip()}
        if not markers:
            raise CriterionRuleGenerationError('object class has no atlas token basis')
        members: list[str] = []
        for head, entry in commands.items():
            tokens = {str(value).casefold() for value in ((entry or {}).get('tokens') if isinstance(entry, dict) else []) or []}
            if tokens & markers:
                members.append(str(head))
        if not members:
            raise CriterionRuleGenerationError(f'object class {class_id} has no atlas members')
        out[str(class_id)] = {'atlas_tokens': sorted(markers), 'members': sorted(members), 'identity': _normalize_identity(spec.get('identity'))}
    return out

def _adjudication_manual_anchors(source: Mapping[str, Any], *, algorithm_classes: set[str]) -> list[dict[str, Any]]:
    raw = source.get('adjudication_manual_anchors')
    if not isinstance(raw, list) or not raw:
        raise CriterionRuleGenerationError('adjudication manual anchors are unavailable')
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != {'anchor_key', 'algorithm_classes', 'identity'}:
            raise CriterionRuleGenerationError('adjudication manual anchor fields are not closed')
        key = str(item.get('anchor_key') or '').strip()
        applies = item.get('algorithm_classes')
        if not key or key in seen or (not isinstance(applies, list)) or (not applies) or any((str(value) not in algorithm_classes for value in applies)):
            raise CriterionRuleGenerationError('adjudication manual anchor applicability is invalid')
        identity = _normalize_identity(item.get('identity'))
        if identity.get('kind') != 'manual_anchor':
            raise CriterionRuleGenerationError('adjudication evidence anchor must be grounded in a manual')
        seen.add(key)
        out.append({'anchor_key': key, 'algorithm_classes': sorted({str(value) for value in applies}), 'identity': identity})
    return out

def _pending_proposals(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    if source.get('pending_proposals'):
        raise CriterionRuleGenerationError('criterion rules may not wait for author signature after the 2026-08-23 ruling')
    return []

def generate_projection(*, source_path: Path=DEFAULT_SOURCE, atlas_path: Path=DEFAULT_ATLAS) -> dict[str, Any]:
    source = _read_json(source_path)
    from cex_core.engine.scripts import gen_command_teardown_atlas
    try:
        atlas = gen_command_teardown_atlas.load_command_teardown_atlas(atlas_path)
        command_atlas_content_sha256 = gen_command_teardown_atlas.atlas_content_sha256(atlas)
    except gen_command_teardown_atlas.TeardownAtlasError as exc:
        raise CriterionRuleGenerationError('command atlas content identity is invalid') from exc
    command_atlas_source_identity_sha256 = str((atlas.get('identity') or {}).get('sha256') or '')
    grammar = _read_json(DOMAIN_GRAMMAR)
    grammar_algorithm_classes = {str(value) for value in grammar.get('algorithm_classes') or {}}
    if not grammar_algorithm_classes:
        raise CriterionRuleGenerationError('grammar algorithm classes are unavailable')
    criterion_types = derive_criterion_types()
    type_ids = {row['criterion_type'] for row in criterion_types}
    heads = _command_heads(atlas)
    rules = [compile_rule_candidate(candidate, criterion_types=type_ids, command_heads=heads) for candidate in source.get('rules') or []]
    if len({row['rule_id'] for row in rules}) != len(rules):
        raise CriterionRuleGenerationError('rule ids are not unique')
    payload: dict[str, Any] = {'schema': 'ist.criterion-rules', 'generator': 'scripts/gen_criterion_rules.py', 'identity': {'source_path': source_path.relative_to(ROOT).as_posix(), 'source_sha256': _sha256_bytes(source_path.read_bytes()), 'command_atlas_path': atlas_path.relative_to(ROOT).as_posix(), 'command_atlas_content_sha256': command_atlas_content_sha256, 'command_atlas_source_identity_sha256': command_atlas_source_identity_sha256, 'version_family': str(atlas.get('version') or ''), 'device_build': str(atlas.get('device_build') or ''), 'criterion_carriers_path': CARRIER_SOURCE.relative_to(ROOT).as_posix(), 'criterion_carrier_contract_sha256': carrier_contract_sha256()}, 'criterion_types': criterion_types, 'object_classes': _object_classes(source, atlas), 'adjudication_manual_anchors': _adjudication_manual_anchors(source, algorithm_classes=grammar_algorithm_classes), 'rules': rules, 'pending_proposals': _pending_proposals(source)}
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    payload['projection_sha256'] = _sha256_bytes(body)
    return payload

def render_projection(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def _write_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--atlas', type=Path, default=DEFAULT_ATLAS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--check', action='store_true')
    return parser

def main(argv: Sequence[str] | None=None) -> int:
    args = _parser().parse_args(argv)
    rendered = render_projection(generate_projection(source_path=args.source, atlas_path=args.atlas))
    convergence_status = 'checked'
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != rendered:
            raise CriterionRuleGenerationError('criterion rule projection is stale; rerun without --check')
    else:
        if args.output.is_symlink():
            raise CriterionRuleGenerationError('criterion rule projection path must not be a symbolic link')
        try:
            current = args.output.read_bytes()
        except FileNotFoundError:
            current = None
        except OSError as exc:
            raise CriterionRuleGenerationError('criterion rule projection cannot be read for convergence') from exc
        if current != rendered:
            _write_atomic(args.output, rendered)
            convergence_status = 'updated'
        else:
            convergence_status = 'reused'
    print(f'converged {args.output}: {convergence_status}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
