# 生成：tools/extract_engine.py ← InfoTest scripts/maintenance/build_language_docs_index.py（sha256 5ce2e6b852d1960a）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
ROOT = _cex_data_path('')
DEFAULT_OUTPUT = ROOT / 'knowledge/data/compile_ref/language_docs_index.json'

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _python_entry(root: Path, path: Path, category: str) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    symbols = sorted((node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and (not node.name.startswith('_'))))
    doc = ast.get_docstring(tree) or ''
    return {'id': f'{category}:{path.stem}', 'category': category, 'path': path.relative_to(root).as_posix(), 'symbols': symbols, 'summary': doc.splitlines()[0] if doc else '', 'sha256': _sha256(path)}

def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'{path} must contain an object')
    return payload

def build_language_docs_index(root: Path=ROOT) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for category, directory in (('checker', root / 'main/case_compiler/checkers'), ('skill_library', root / 'main/case_compiler/skill_lib')):
        for path in sorted(directory.glob('*.py')):
            if path.name != '__init__.py':
                entries.append(_python_entry(root, path, category))
    method_path = root / 'knowledge/data/compile_ref/method_reference.json'
    method = _json(method_path)
    entries.append({'id': 'reference:method_reference', 'category': 'method_reference', 'path': method_path.relative_to(root).as_posix(), 'sections': [str(section.get('name') or '') for section in method.get('sections') or [] if isinstance(section, dict) and section.get('name')], 'shards': sum((len(section.get('shards') or []) for section in method.get('sections') or [] if isinstance(section, dict))), 'query': "lang_query(kind='signature'|'dispatch'|'usage'|'nearest'|'prompt_pattern'|'docs')", 'sha256': _sha256(method_path)})
    blocks_schema_path = root / 'knowledge/data/compile_ref/blocks_schema.json'
    blocks_schema = _json(blocks_schema_path)
    entries.append({'id': 'language:blocks_schema', 'category': 'blocks_schema', 'path': blocks_schema_path.relative_to(root).as_posix(), 'schema': str(blocks_schema.get('schema') or ''), 'kinds': list((blocks_schema.get('closed_sets') or {}).get('kinds') or []), 'expander': str((blocks_schema.get('_meta') or {}).get('expander') or ''), 'resolution': 'fs_read', 'summary': 'Per-kind blocks field contract parsed from the expander source: required/optional, value domains, assertion-identity carrier position, and every verbatim refusal.', 'sha256': _sha256(blocks_schema_path)})
    contract_path = root / 'knowledge/data/compile_ref/excel_contract.json'
    contract = _json(contract_path)
    entries.append({'id': 'language:excel_contract', 'category': 'excel_contract', 'path': contract_path.relative_to(root).as_posix(), 'schema': str(contract.get('schema') or ''), 'objects': len(contract.get('objects') or []), 'entries': len(contract.get('entries') or []), 'execute_actions': len(contract.get('execute_actions') or []), 'query': "lang_query(kind='contract'[, domain=<E>][, name=<F>])", 'summary': 'The only machine-readable authority for E/F values, signatures, G/H/I semantics, enablement and execute action grammar.', 'sha256': _sha256(contract_path)})
    reference_path = root / 'knowledge/data/compile_ref/EXCEL_FUNCTIONS.md'
    entries.append({'id': 'language:excel_functions', 'category': 'excel_language_reference', 'path': reference_path.relative_to(root).as_posix(), 'sections': [line.lstrip('#').strip() for line in reference_path.read_text(encoding='utf-8').splitlines() if line.startswith('## ')], 'resolution': 'fs_read', 'summary': 'Mechanics of the A-I execution language and the typed blocks: what each column means, per-kind field contracts, assertion identity and locators. Carries no function list by design.', 'sha256': _sha256(reference_path)})
    grammar_path = root / 'knowledge/data/compile_ref/domain_grammar.json'
    grammar = _json(grammar_path)
    entries.append({'id': 'grammar:domain_grammar', 'category': 'domain_grammar', 'path': grammar_path.relative_to(root).as_posix(), 'sections': sorted((key for key in grammar if key != '_meta')), 'sha256': _sha256(grammar_path)})
    criterion_path = root / 'knowledge/data/compile_ref/criterion_rules.json'
    criterion = _json(criterion_path)
    entries.append({'id': 'language:criterion_rules', 'category': 'criterion_rules', 'path': criterion_path.relative_to(root).as_posix(), 'schema': str(criterion.get('schema') or ''), 'criterion_types': [str(row.get('criterion_type') or '') for row in criterion.get('criterion_types') or [] if isinstance(row, dict) and row.get('criterion_type')], 'rule_count': len(criterion.get('rules') or []), 'pending_proposal_count': len(criterion.get('pending_proposals') or []), 'resolution': 'fs_read', 'summary': 'Generated criterion-type catalogue and identity-bound verdict-shape rules; pending author proposals are explicitly non-rules.', 'sha256': _sha256(criterion_path)})
    behavior_examples_path = root / 'knowledge/data/compile_ref/device_behavior_examples.json'
    behavior_examples = _json(behavior_examples_path)
    translation_vocabulary = behavior_examples.get('translation_shape_vocabulary') or {}
    entries.append({'id': 'facts:device_behavior_examples', 'category': 'device_behavior_examples', 'path': behavior_examples_path.relative_to(root).as_posix(), 'schema': str(behavior_examples.get('schema') or ''), 'status': str(behavior_examples.get('status') or 'unavailable'), 'unavailable_reason': str(behavior_examples.get('unavailable_reason') or ''), 'missing_required_entry_count': len(behavior_examples.get('missing_required_entries') or []), 'rule_ids': [str(row.get('id') or '') for row in behavior_examples.get('entries') or [] if isinstance(row, dict) and row.get('id')], 'fact_count': len(behavior_examples.get('entries') or []), 'translation_shape_count': len(translation_vocabulary.get('entries') or []), 'translation_shape_axes': list(translation_vocabulary.get('axes') or []), 'expected_authority': False, 'resolution': 'fs_read', 'summary': 'Generated actual-only device behavior, translation examples and translation-shape supply from verified workbooks, attribution receipts, and identity-marked K_ought adjudications; never expected-value authority.', 'sha256': _sha256(behavior_examples_path)})
    footprint_root = root / 'knowledge/footprints/nodes'
    entries.append({'id': 'facts:footprint', 'category': 'footprint', 'path': footprint_root.relative_to(root).as_posix(), 'status': 'runtime_resolved', 'resolution': 'kb_footprint', 'query': 'kb_footprint'})
    ledger_registry_path = root / 'knowledge/shadow_exec/echo_corpus.jsonl'
    ledger_manifest_path = root / 'knowledge/shadow_exec/manifest.json'
    ledger_manifest = _json(ledger_manifest_path)
    fixture_validation = ledger_manifest.get('behavior_ledger_projection') or {}
    corpus_identity = ledger_manifest.get('artifact_identity') or {}
    entries.append({'id': 'fixture:behavior_ledger', 'category': 'behavior_ledger', 'path': ledger_registry_path.relative_to(root).as_posix(), 'status': 'tracked_projection', 'resolution': 'local_replay / lookup_flip_baseline', 'device_os_build': str(fixture_validation.get('device_os_build') or ''), 'record_count': int(fixture_validation.get('entry_count') or 0), 'query': 'local_replay / lookup_flip_baseline', 'source_manifest': ledger_manifest_path.relative_to(root).as_posix(), 'source_manifest_sha256': _sha256(ledger_manifest_path), 'registry': ledger_registry_path.relative_to(root).as_posix(), 'registry_schema': str(corpus_identity.get('schema') or ''), 'registry_sha256': str(corpus_identity.get('corpus_sha256') or '')})
    pipeline_paths = ['main/ist_core/worker_device_context.py', 'main/ist_core/tools/knowledge/behavior_tool.py', 'main/case_compiler/provenance_ir.py']
    entries.append({'id': 'pipeline:probe_to_config_binding', 'category': 'evidence_pipeline', 'path': pipeline_paths[0], 'stages': [{'name': 'hypothesis_and_controlled_probe', 'path': pipeline_paths[0]}, {'name': 'verified_fact_writeback', 'path': pipeline_paths[1]}, {'name': 'config_binding_reference', 'path': pipeline_paths[2]}], 'complete': all(((root / path).is_file() for path in pipeline_paths))})
    entries.append({'id': 'reference:vendor_command_tree', 'category': 'vendor_command_tree', 'path': 'runtime/command_tree', 'status': 'runtime_resolved', 'resolution': 'vendor_stdlib.load_vendor_stdlib()', 'query': "lang_query(kind='param', name=<command>)", 'summary': '设备命令树投影:命令存在性/参数契约(position/type/optional/help)。'})
    _manual_root = root / 'knowledge/data/manual'

    def _version_sort_key(name: str) -> tuple:
        parts = []
        for segment in str(name).split('.'):
            if segment.isdigit():
                parts.append((0, int(segment), ''))
            else:
                parts.append((1, 0, segment))
        return tuple(parts)
    _scanned = sorted((child.name for child in _manual_root.iterdir() if child.is_dir() and (not child.name.startswith('.'))), key=_version_sort_key) if _manual_root.is_dir() else []
    entries.append({'id': 'reference:cli_app_manuals', 'category': 'vendor_manual', 'path': 'knowledge/data/manual', 'versions': _scanned, 'versions_source': 'local_scan', 'versions_note': '本机扫描结果，非随投影分发的事实——该目录不入 git（.gitignore）。清单为空只说明本机没有同步过手册语料（跑 python -m main.apv_doc_sync），不代表产品没有这些版本；换机重生成本投影会得到该机自己的清单。', 'files_per_version': ['cli_cn.md', 'app_cn.md'], 'status': 'tracked_projection', 'resolution': 'fs_grep(signature) → fs_read(offset=<line>) / apv_lang.manual_param_excerpt', 'query': "lang_query(kind='param', name=<command>)", 'summary': 'CLI/APP 手册(manual/<version>/{cli,app}_cn.md,单体文件):参数取值域与含义原文。按 identity.device_build 选版本;先 grep 签名行再按行号读窗口。'})
    return {'schema': 'ist.ide.language-docs', 'entries': sorted(entries, key=lambda item: item['id'])}

def write_language_docs_index(output: Path=DEFAULT_OUTPUT, *, root: Path=ROOT) -> dict[str, Any]:
    payload = build_language_docs_index(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise OSError('language docs projection path is a symbolic link')
    fd, temporary = tempfile.mkstemp(prefix=f'.{output.name}.', dir=output.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return payload
if __name__ == '__main__':
    write_language_docs_index()
