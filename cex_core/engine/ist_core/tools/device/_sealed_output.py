# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/_sealed_output.py（sha256 2e8bbd04fd37e968）。不在这里手改。
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, lexical_absolute, read_regular_nofollow, validate_json_budget

class OutputLedgerError(PermissionError):
    pass

class OutputJsonBudgetError(OutputLedgerError):
    """读写同一结构预算的拒绝；调用方按类型识别，不解析报错文案。"""
_MAX_LEDGER_BYTES = 32 * 1024 * 1024

def output_root() -> Path:
    from cex_core.engine.ist_core.compile_engine import _shared as sh
    return lexical_absolute(sh.outputs_root())

def scoped_output_path(raw_path: str | Path) -> Path:
    text = str(raw_path or '').strip()
    if not text:
        raise OutputLedgerError('output path is empty')
    raw = Path(text)
    if '..' in raw.parts or text.startswith('~') or '~' in raw.parts or ('\x00' in text):
        raise OutputLedgerError('output path traversal is not allowed')
    root = output_root()
    if raw.is_absolute():
        target = lexical_absolute(raw)
    elif text == 'workspace/outputs' or text.startswith('workspace/outputs/'):
        from cex_core.engine.ist_core.compile_engine import _shared as sh
        target = lexical_absolute(sh.project_root() / raw)
    elif text == 'outputs' or text.startswith('outputs/'):
        rel = text[len('outputs'):].lstrip('/')
        target = lexical_absolute(root / rel)
    else:
        target = lexical_absolute(root / raw)
    try:
        rel = target.relative_to(root)
    except ValueError as exc:
        raise OutputLedgerError('path is outside the current workspace/outputs scope') from exc
    if not rel.parts:
        raise OutputLedgerError('an output file path is required')
    return target

def case_output_path(autoid: str, filename: str) -> Path:
    aid = str(autoid or '').strip()
    if len(aid) != 18 or not aid.isdigit():
        raise OutputLedgerError('autoid must be exactly 18 digits')
    if not filename or Path(filename).name != filename or filename in {'.', '..'}:
        raise OutputLedgerError('output filename is invalid')
    return scoped_output_path(output_root() / aid / filename)

def sibling_last_run_path(raw_path: str | Path) -> Path:
    source = scoped_output_path(raw_path)
    target = source if source.name == 'last_run.json' else source.parent / 'last_run.json'
    return scoped_output_path(target)

def read_bytes(path: str | Path, *, max_bytes: int=_MAX_LEDGER_BYTES, preserve_missing: bool=False, return_identity: bool=False) -> bytes | tuple[bytes, tuple[int, int, int, int, int]]:
    target = scoped_output_path(path)
    return read_regular_nofollow(target, error_type=OutputLedgerError, invalid_message='output file path is invalid', directory_message='output directory is unavailable or unsafe', open_message='output file is unavailable or unsafe', bounds_message='output file exceeds the allowed size or is not regular', changed_message='output file changed while being read', max_bytes=max_bytes, min_bytes=0, require_current_uid=True, preserve_missing=preserve_missing, return_identity=return_identity)

def read_json(path: str | Path, *, max_bytes: int=_MAX_LEDGER_BYTES, preserve_missing: bool=False) -> Any:
    payload = read_bytes(path, max_bytes=max_bytes, preserve_missing=preserve_missing)
    validate_json_budget(payload, error_type=OutputJsonBudgetError, message='output JSON exceeds structural budget')
    try:
        return json.loads(payload.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OutputLedgerError('output JSON is invalid') from exc

def write_json(path: str | Path, value: Any) -> str:
    from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
    from cex_core.engine.ist_core.compile_engine.engine_quarantine import session_admission_boundary
    target = scoped_output_path(path)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(payload) > _MAX_LEDGER_BYTES:
        raise OutputLedgerError('output JSON exceeds the allowed size')
    validate_json_budget(payload, error_type=OutputJsonBudgetError, message='output JSON exceeds structural budget')
    with session_admission_boundary(current_worker_device_session()):
        return atomic_write_bytes_nofollow(target, payload, error_type=OutputLedgerError, invalid_message='output file path is invalid', unavailable_message='output directory or file is unavailable or unsafe', create_parents=True, mode=384)

def mtime_ns_from_identity(path: str | Path) -> int:
    target = scoped_output_path(path)
    _payload, identity = read_regular_nofollow(target, error_type=OutputLedgerError, invalid_message='output file path is invalid', directory_message='output directory is unavailable or unsafe', open_message='output file is unavailable or unsafe', bounds_message='output file exceeds the allowed size or is not regular', changed_message='output file changed while being read', max_bytes=_MAX_LEDGER_BYTES, min_bytes=0, require_current_uid=True, return_identity=True)
    return int(identity[3])

def ensure_case_directory(autoid: str) -> Path:
    from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow
    path = case_output_path(autoid, '.scope-anchor').parent
    descriptor = open_directory_nofollow(path, error_type=OutputLedgerError, invalid_message='case output directory is invalid', unavailable_message='case output directory is unavailable or unsafe', create_missing=True, create_mode=448)
    os.close(descriptor)
    return path
