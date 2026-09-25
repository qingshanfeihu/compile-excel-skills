# 生成：tools/extract_engine.py ← InfoTest main/ist_core/memory/footprint/schema.py（sha256 92fba4c7d7bfc46f）。不在这里手改。
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
FactKind = Literal['cli_command', 'decision_rule', 'behavior', 'known_issue']
Level = Literal['leaf', 'trunk', 'branch', 'root']

@dataclass
class RawFact:
    fact_kind: FactKind
    feature_path: list[str]
    fact_key: str
    cli_commands: list[list[str]] = field(default_factory=list)
    cli_syntax: str = ''
    parameters: list[dict] = field(default_factory=list)
    condition: str = ''
    decision: str = ''
    content: str = ''
    issue_id: str = ''
    issue_title: str = ''
    affected_versions: list[str] = field(default_factory=list)
    evidence_file: str = ''
    evidence_quote: str = ''
    device_evidence: dict = field(default_factory=dict)
    raw_invocation: str = ''
    validity: str = 'verified'
    observed_under: str = ''
    valid_for: list[str] = field(default_factory=list)
    superseded_by: str = ''
    catalog_head: str = ''
    catalog_identity: dict = field(default_factory=dict)
    source_thread: str = ''

@dataclass
class RoutedFact:
    fact: RawFact
    level: Level
    target_file: str

@dataclass
class MergeResult:
    action: str = 'skip'
    target_file: str = ''
    detail: str = ''

def longest_common_prefix(seqs: list[list[str]]) -> list[str]:
    if not seqs:
        return []
    prefix = list(seqs[0])
    for seq in seqs[1:]:
        i = 0
        while i < len(prefix) and i < len(seq) and (prefix[i] == seq[i]):
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix

def anchor_paths(cli_commands: list[list[str]], fallback: list[str] | None=None) -> list[list[str]]:
    cleaned = [list(c) for c in cli_commands or [] if c]
    if not cleaned:
        return [list(fallback)] if fallback else []
    unique: list[list[str]] = []
    for c in cleaned:
        if c not in unique:
            unique.append(c)
    if len(unique) == 1:
        return [unique[0]]
    prefix = longest_common_prefix(unique)
    if prefix:
        return [prefix]
    modules: list[list[str]] = []
    for c in unique:
        head = [c[0]]
        if head not in modules:
            modules.append(head)
    return modules

def node_template(feature_id: str, level: str='leaf') -> dict[str, Any]:
    return {'schema_version': 3, 'feature_id': feature_id, 'level': level, 'cli': {'commands': []}, 'decision_rules': [], 'behaviors': [], 'known_issues': [], 'children': [], 'version_scope': {}, 'footprint_meta': _meta_template()}

def leaf_template(feature_id: str) -> dict[str, Any]:
    return node_template(feature_id, 'leaf')

def trunk_template(feature_id: str) -> dict[str, Any]:
    return node_template(feature_id, 'trunk')

def branch_template(feature_id: str) -> dict[str, Any]:
    return node_template(feature_id, 'branch')

def root_template(feature_id: str) -> dict[str, Any]:
    return node_template(feature_id, 'root')

def _meta_template() -> dict[str, Any]:
    return {'created_at': None, 'verified_count': 0, 'source_threads': []}
TEMPLATE_MAP: dict[str, Any] = {'leaf': leaf_template, 'trunk': trunk_template, 'branch': branch_template, 'root': root_template}
LEVEL_KINDS: dict[str, set[str]] = {'leaf': {'cli_command', 'decision_rule', 'behavior', 'known_issue'}, 'trunk': {'cli_command', 'decision_rule', 'behavior', 'known_issue'}, 'branch': {'cli_command', 'decision_rule', 'behavior', 'known_issue'}, 'root': {'cli_command', 'decision_rule', 'behavior', 'known_issue'}}
