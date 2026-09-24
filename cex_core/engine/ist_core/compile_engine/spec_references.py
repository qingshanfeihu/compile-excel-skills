# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/spec_references.py（sha256 a0e25c456f1c9ebf）。不在这里手改。
from __future__ import annotations
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow
from cex_core.engine.kms.spec_index import resolve_indexed_spec
_SLICE_HEADER = '<!-- ist.spec-reference-slice level=reference signing_power=none scenario_1=not_judged source={name} sha256={sha256} anchor={anchor} -->'
_HEADING_RE = re.compile('^(#{1,6})\\s')

def _num_re(num: str) -> re.Pattern[str]:
    return re.compile(f'(?<!\\d){re.escape(num)}(?!\\d)')
_SLICE_MAX_LINES = 240
_SLICE_MAX_CHARS = 20000
_WINDOW_BEFORE = 20
_WINDOW_AFTER = 80
_HEAD_LINES = 80

def _evidence_numbers(evidence: str) -> list[str]:
    channel, _sep, payload = str(evidence or '').partition(':')
    if not channel.startswith('bug_') or not payload:
        return []
    return [n for n in payload.split(',') if n]

def _slice_bounds(lines: list[str], numbers: list[str]) -> tuple[int, int]:
    hit: int | None = None
    if numbers:
        pats = [_num_re(n) for n in numbers]
        for idx, line in enumerate(lines):
            if any((p.search(line) for p in pats)):
                hit = idx
                break
    if hit is None and numbers:
        numbers = []
    if not numbers:
        return (0, min(len(lines), _HEAD_LINES))
    start_heading: int | None = None
    for idx in range(hit, -1, -1):
        if _HEADING_RE.match(lines[idx]):
            start_heading = idx
            break
    if start_heading is None:
        return (max(0, hit - _WINDOW_BEFORE), min(len(lines), hit + _WINDOW_AFTER))
    level = len(_HEADING_RE.match(lines[start_heading]).group(1))
    end = len(lines)
    for idx in range(start_heading + 1, len(lines)):
        m = _HEADING_RE.match(lines[idx])
        if m and len(m.group(1)) <= level:
            end = idx
            break
    end = min(end, start_heading + _SLICE_MAX_LINES)
    return (start_heading, end)

def build_spec_references(project_root: Path, out_dir: Path, out_name: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    references: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    slice_dir = Path(out_dir) / 'spec_references'
    if slice_dir.is_dir() and (not slice_dir.is_symlink()):
        shutil.rmtree(slice_dir)
    written_dir = False
    for match in matches:
        name = str((match or {}).get('file') or '').strip()
        evidence = str((match or {}).get('evidence') or '')
        if not name:
            dropped.append({'file': '', 'reason': 'invalid_match'})
            continue
        resolved = resolve_indexed_spec(Path(project_root), name)
        if resolved is None:
            dropped.append({'file': name, 'reason': 'identity_unresolved'})
            continue
        text = resolved.content.decode('utf-8', errors='replace')
        lines = text.splitlines()
        start, end = _slice_bounds(lines, _evidence_numbers(evidence))
        body = '\n'.join(lines[start:end])[:_SLICE_MAX_CHARS]
        end_line = start + max(1, len(body.splitlines()))
        anchor = f'{name}:{start + 1}-{end_line}'
        header = _SLICE_HEADER.format(name=name, sha256=resolved.sha256, anchor=anchor)
        if not written_dir:
            slice_dir.mkdir(parents=False, exist_ok=True)
            written_dir = True
        slice_bytes = (header + '\n\n' + body + '\n').encode('utf-8')
        atomic_write_bytes_nofollow(slice_dir / name, slice_bytes, error_type=ValueError, invalid_message='spec reference slice path is invalid', unavailable_message='spec reference slice directory is unavailable')
        references.append({'name': name, 'sha256': resolved.sha256, 'size': resolved.size, 'slice_sha256': hashlib.sha256(slice_bytes).hexdigest(), 'slice_size': len(slice_bytes), 'anchor': anchor, 'ref': f'workspace/outputs/{out_name}/spec_references/{name}', 'evidence': evidence})
    return {'references': references, 'dropped': dropped}
