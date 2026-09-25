# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/compile_prep.py（sha256 46f1810afab16116）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import logging
import re
from pathlib import Path
from langchain_core.tools import tool
from cex_core.engine.ist_core.security_scrub import scrub_text
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, read_regular_nofollow, sha256_bytes, validate_json_budget
logger = logging.getLogger(__name__)
_MINDMAP_LEADING_MARKERS = (b'\xef\xbf\xbf', b'\xef\xbb\xbf')

def _strip_mindmap_leading_markers(raw: bytes) -> bytes:
    body = raw
    while body:
        matched = next((marker for marker in _MINDMAP_LEADING_MARKERS if body.startswith(marker)), None)
        if matched is None:
            break
        body = body[len(matched):]
    return body

def _logical_source_id(path: Path) -> str:
    project_root = _cex_data_path('')
    try:
        logical = path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        logical = f'sandbox-input/{path.name}'
    return scrub_text(logical, scrub_paths=False)

def _load_mindmap(path: Path) -> tuple[list, bytes]:
    raw = read_regular_nofollow(path, error_type=ValueError, invalid_message='mindmap path is invalid', directory_message='mindmap parent is unavailable', open_message='mindmap is unavailable', bounds_message='mindmap exceeds its sealed size boundary', changed_message='mindmap changed while being read', max_bytes=32 * 1024 * 1024, min_bytes=1)
    assert isinstance(raw, bytes)
    body = _strip_mindmap_leading_markers(raw)
    validate_json_budget(body, error_type=ValueError, message='mindmap exceeds the JSON structure budget')
    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('mindmap must be one complete JSON document with no trailing data') from exc
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError('mindmap JSON top level must be a one-element [root] array')
    root = payload[0]
    if not isinstance(root, dict):
        raise ValueError('mindmap root must be an object')
    if not isinstance(root.get('data'), dict):
        raise ValueError('mindmap root must contain a data object')
    if not isinstance(root.get('children'), list):
        raise ValueError('mindmap root must contain a children array')
    return (payload, raw)

def _verify_preserved_entry_bytes(directory: Path, preserved: dict[str, bytes]) -> None:
    for name, expected in preserved.items():
        current = read_regular_nofollow(directory / name, trusted_root=directory, error_type=ValueError, min_bytes=len(expected), max_bytes=len(expected), require_current_uid=True, invalid_message='preserved entry path is invalid', directory_message='preserved entry directory is unavailable', open_message='preserved entry is unavailable', bounds_message='preserved entry size changed', changed_message='preserved entry changed while reading')
        if current != expected:
            raise ValueError('preserved entry changed after validation')

def _archive_nonempty_batch_before_recreate(batch_dir: Path, *, batch_name: str) -> str:
    if not batch_dir.exists():
        return ''
    if batch_dir.is_symlink() or not batch_dir.is_dir():
        raise ValueError('batch output directory is not a safe regular directory')
    names = {entry.name for entry in batch_dir.iterdir()}
    if not names:
        return ''
    preserved: dict[str, bytes] = {}
    validated_entry = False
    from cex_core.engine.ist_core.compile_engine import _shared as sh, compile_context as CC
    context = sh.current_engine_node_context()
    if context is not None and context[1] == 'prep':
        preserved = CC.validate_entry_initialization(sh.project_root(), batch_dir.parent, batch_name, state=context[0])
        validated_entry = True
        _verify_preserved_entry_bytes(batch_dir, preserved)
        if names == preserved.keys():
            return ''
    elif names == {'compile_context.json', 'compile_entry_inputs.json'}:
        return ''
    elif 'manifest.json' not in names and (names == {'compile_context.json'} or 'engine_run.json' in names):
        raise CC.CompileContextIdentityError('current entry initialization requires a trusted prep scope')
    import time
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    archive_stem = f'{batch_name}_pre_recreate_{stamp}'
    if len(archive_stem) > 180:
        digest = sha256_bytes(batch_name.encode('utf-8'))[:12]
        archive_stem = f'{batch_name[:120]}_{digest}_pre_recreate_{stamp}'
    from cex_core.engine.ist_core.compile_engine.batch_storage import quarantine_root
    archive_root = quarantine_root(batch_dir.parent)
    archive_root.mkdir(parents=True, exist_ok=True)
    archive = archive_root / archive_stem
    sequence = 0
    while archive.exists() or archive.is_symlink():
        sequence += 1
        archive = archive_root / f'{archive_stem}_{sequence}'
    context_path = batch_dir / 'compile_context.json'
    if context_path.is_symlink():
        raise ValueError('compile context is a symbolic link before batch archive')
    if not validated_entry and context_path.is_file():
        context_raw = read_regular_nofollow(context_path, error_type=ValueError, invalid_message='compile context path is invalid before batch archive', directory_message='compile context directory is unavailable before batch archive', open_message='compile context is unavailable before batch archive', bounds_message='compile context exceeds its archive boundary', changed_message='compile context changed during batch archive', max_bytes=4 * 1024 * 1024, min_bytes=2)
        assert isinstance(context_raw, bytes)
        preserved['compile_context.json'] = context_raw
    sidecar_path = batch_dir / 'compile_entry_inputs.json'
    if sidecar_path.is_symlink():
        raise ValueError('entry input sidecar is a symbolic link before batch archive')
    if not validated_entry and sidecar_path.is_file():
        sidecar_raw = read_regular_nofollow(sidecar_path, error_type=ValueError, invalid_message='entry input sidecar path is invalid before batch archive', directory_message='entry input sidecar directory is unavailable before batch archive', open_message='entry input sidecar is unavailable before batch archive', bounds_message='entry input sidecar exceeds its archive boundary', changed_message='entry input sidecar changed during batch archive', max_bytes=64 * 1024, min_bytes=2)
        assert isinstance(sidecar_raw, bytes)
        preserved['compile_entry_inputs.json'] = sidecar_raw
    _verify_preserved_entry_bytes(batch_dir, preserved)
    batch_dir.rename(archive)
    created = False
    try:
        _verify_preserved_entry_bytes(archive, preserved)
        batch_dir.mkdir()
        created = True
        for name, raw in preserved.items():
            atomic_write_bytes_nofollow(batch_dir / name, raw, error_type=ValueError, invalid_message='new entry path is invalid after batch archive', unavailable_message='new batch directory is unavailable after batch archive')
    except Exception:
        try:
            if created:
                for name in preserved:
                    (batch_dir / name).unlink(missing_ok=True)
                batch_dir.rmdir()
        except OSError:
            logger.exception('批目录归档失败后新目录清理不完整')
        if not batch_dir.exists() and archive.exists():
            archive.rename(batch_dir)
        raise
    return archive.name

def _node_text(node: dict) -> str:
    return ((node.get('data') or {}).get('text') or '').strip()

def _node_children(node: dict) -> list:
    return node.get('children') or []

def _node_data(node: dict) -> dict:
    return node.get('data') or {}
_NUMBERED_STEP_RE = re.compile('(?m)^\\s*(?:\\[?([0-9]+)\\]?)[.、:：)）]\\s*')
_CHECK_REF_RE = re.compile('\\[([A-Za-z0-9_-]+)\\]', re.IGNORECASE)

def _numbered_source_atoms(text: str) -> list[tuple[str, str]]:
    source = str(text or '')
    matches = list(_NUMBERED_STEP_RE.finditer(source))
    atoms: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        atom = source[match.start():end].strip()
        if atom:
            atoms.append((match.group(1), atom))
    return atoms

def _action_source_atoms(text: str) -> list[tuple[str, str]]:
    source = str(text or '')
    numbered = _numbered_source_atoms(source)
    if numbered:
        return numbered
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if len(lines) > 1:
        return [(str(index), line) for index, line in enumerate(lines, 1)]
    return [('1', source.strip())] if source.strip() else []

def _labeled_expectation_atoms(text: str) -> dict[str, str]:
    source = str(text or '')
    pattern = re.compile('(?m)^\\s*\\[([A-Za-z0-9_-]+)\\]\\s*')
    matches = list(pattern.finditer(source))
    atoms: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        atom = source[match.start():end].strip()
        if atom:
            atoms[match.group(1).lower()] = atom
    return atoms

def _source_step_intents(node: dict) -> tuple[list[dict[str, str]], str, list[str]]:
    children = _node_children(node)
    if len(children) == 1 and (not _node_children(children[0])) and (not _numbered_source_atoms(_node_text(children[0]))):
        action_block = _node_text(node)
        expectation_block = _node_text(children[0])
        actions = _action_source_atoms(action_block)
        labeled = _labeled_expectation_atoms(expectation_block)
        intents: list[dict[str, str]] = []
        matched_labels: set[str] = set()
        for _number, action in actions:
            refs = [m.group(1).lower() for m in _CHECK_REF_RE.finditer(action)]
            expected_parts = [labeled[label] for label in refs if label in labeled]
            matched_labels.update((label for label in refs if label in labeled))
            if not expected_parts and len(actions) == 1:
                expected_parts = [expectation_block] if expectation_block else []
                matched_labels.update(labeled)
            intents.append({'desc': action, 'expected': '  '.join(expected_parts)})
        unmatched = [value for label, value in labeled.items() if label not in matched_labels]
        return (intents, 'case_body_with_leaf_expectation', unmatched)
    intents = []
    for step_node in children:
        step_desc = _node_text(step_node)
        expects = [_node_text(c) for c in _node_children(step_node) if _node_text(c)]
        intents.append({'desc': step_desc, 'expected': '  '.join(expects) if expects else ''})
    return (intents, 'title_steps_expectations', [])

def _extract_cases(root: dict) -> list[dict]:
    cases: list[dict] = []

    def walk(node: dict, group_path: list[str]) -> None:
        d = _node_data(node)
        autoid = str(d.get('autoid') or '').strip()
        if autoid:
            auto_marker = str(d.get('auto') or '').strip()
            if auto_marker and auto_marker.upper() != 'YES':
                return
            step_intents, source_layout, unbound_expectations = _source_step_intents(node)
            cases.append({'autoid': autoid, 'title': _node_text(node), 'group_path': list(group_path), 'priority': d.get('priority'), 'resource': d.get('resource'), 'source_layout': source_layout, 'step_intents': step_intents, 'unbound_expectations': unbound_expectations, 'init_commands': None, 'steps': None, 'assertions_provenance': None, 'compile_state': {'draft_xlsx': None, 'verdict': None, 'device_truth': None, 'grade': None, 'rounds': 0, 'status': 'pending'}})
            return
        title = _node_text(node)
        next_path = group_path + [title] if title else group_path
        for c in _node_children(node):
            walk(c, next_path)
    walk(root, [])
    return cases

@tool(parse_docstring=True)
def compile_prep(mindmap_path: str, out_name: str='') -> str:
    """Parse one mindmap file into a batch-compile manifest (JSON intermediate representation) for stage-wise orchestration.

    Reads the whole mindmap and lists every case it contains (autoid as primary key) with
    title/grouping/step requirements/expectations (all verbatim mindmap requirements),
    grouped by parent chain.

    **This tool produces requirements only, never commands** (zero-hardcoding red line):
    each case's init_commands/steps/assertions_provenance in the manifest is null — those
    are filled in by the authoring sub-agent after consulting manuals/precedents, never
    written here. prep only answers "which cases does this mindmap compile, what is each
    case's raw requirement, how are they grouped".

    Key contracts:
    - autoid is the primary key; duplicate titles are **not deduplicated** (many same-named
      cases differ only in parameters).
    - group_path records the case's parent-node chain in the mindmap, letting the
      orchestrator recognize group-level shared baselines (some mindmaps hoist the baseline
      into a preceding out-of-group node that in-group cases do not restate).

    Args:
        mindmap_path: mindmap file path (workspace/inputs/automatic_case/*.txt, mind-map JSON).
        out_name: manifest output subdir (workspace/outputs/<out_name>/manifest.json);
            empty uses the mindmap filename (sans extension).

    Returns:
        Manifest path + case statistics (total/groups/duplicate titles). The orchestrator
        fans out by stage from it.
    """
    try:
        from cex_core.engine.ist_core.tools.deepagent.file_tools import _resolve_inside_root
        p = _resolve_inside_root(mindmap_path, must_exist=True)
    except Exception:
        return f'error: mindmap file does not exist: {scrub_text(mindmap_path)}'
    if not Path(p).is_file():
        return f'error: mindmap file does not exist: {scrub_text(mindmap_path)}'
    p = Path(p)
    try:
        mm, source_bytes = _load_mindmap(p)
        cases = _extract_cases(mm[0])
    except Exception as exc:
        return f'error: mindmap parse failed: {scrub_text(exc)}'
    if not cases:
        return 'error: no case node with an autoid found in the mindmap — confirm this is a test-case mindmap (case nodes should carry an autoid field in their data).'
    import re as _re
    from cex_core.engine.ist_core.compile_engine import _shared as _sh
    invalid_autoids: list[str] = []
    for case in cases:
        autoid = str(case.get('autoid') or '')
        try:
            _sh.safe_output_component(autoid, field='autoid')
        except ValueError:
            invalid_autoids.append(autoid)
            continue
        if not _re.fullmatch('\\d{18}', autoid):
            invalid_autoids.append(autoid)
    if invalid_autoids:
        return 'error: mindmap contains invalid production autoid values; each case autoid must be one 18-digit requirements-system id'
    seen, dups = (set(), [])
    for c in cases:
        if c['autoid'] in seen:
            dups.append(c['autoid'])
        seen.add(c['autoid'])
    if dups:
        return 'error: mindmap contains duplicate autoid primary keys'
    from collections import Counter
    groups = Counter((' / '.join(c['group_path']) for c in cases))
    titles = Counter((c['title'] for c in cases))
    dup_titles = {t: n for t, n in titles.items() if n > 1}

    def _family_key(c: dict) -> str:
        si = c.get('step_intents') or []
        first = si[0].get('desc') or '' if si else ''
        return _re.sub('\\s+', '', _re.sub('\\d+', 'N', first))
    fam_map: dict[str, list[str]] = {}
    for c in cases:
        fam_map.setdefault(_family_key(c), []).append(c['autoid'])
    fam_id = 0
    families = []
    for key, aids in fam_map.items():
        fam_id += 1
        fid = f'F{fam_id:02d}'
        for c in cases:
            if c['autoid'] in aids:
                c['family'] = fid
        families.append({'family': fid, 'size': len(aids), 'head': aids[0], 'members': aids, 'key_hint': key[:60]})
    families.sort(key=lambda f: -f['size'])
    try:
        sub = _sh.safe_output_component(out_name or p.stem, field='out_name')
    except ValueError as exc:
        return f'error: {exc}'
    manifest = {'batch_id': f'compile-{sub}', 'source': _logical_source_id(p), 'source_snapshot': f'workspace/outputs/{sub}/mindmap_source.json', 'source_sha256': sha256_bytes(source_bytes), 'source_size': len(source_bytes), 'out_name': sub, 'case_count': len(cases), 'groups': dict(groups), 'families': families, 'cases': cases}
    batch_dir = _sh.outputs_root() / sub
    archived_batch = _archive_nonempty_batch_before_recreate(batch_dir, batch_name=sub)
    out = batch_dir / 'manifest.json'
    snapshot = out.parent / 'mindmap_source.json'
    atomic_write_bytes_nofollow(snapshot, source_bytes, error_type=ValueError, invalid_message='mindmap snapshot path is invalid', unavailable_message='mindmap snapshot directory is unavailable')
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    atomic_write_bytes_nofollow(out, manifest_bytes, error_type=ValueError, invalid_message='manifest output path is invalid', unavailable_message='manifest output directory is unavailable')
    dup_note = f'\n⚠️ duplicate autoids: {dups}' if dups else ''
    return f'=== compile_prep ===\nmanifest written: {out}\n' + (f'previous non-empty batch quarantined: workspace/quarantine/compile_engine/{archived_batch}\n' if archived_batch else '') + f'mindmap: {p.name}  total cases: {len(cases)}\ngroups ({len(groups)}): {dict(list(groups.items())[:12])}\nintent families ({len(families)}): ' + '; '.join((f"{f['family']}×{f['size']}" for f in families[:8])) + f"\nduplicate titles: {len(dup_titles)} (autoid is the primary key; duplicate titles are not deduplicated, each compiles independently)\n{dup_note}\n--- the manifest holds requirements only (title/group/steps/expectations), no commands ---\nevery case's init_commands/steps/assertions_provenance is null,\nfilled in by the authoring sub-agent after consulting manuals/precedents. Next: the orchestrator dispatches briefs per case."
