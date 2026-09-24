# 生成：tools/extract_engine.py ← InfoTest main/common/file_identity.py（sha256 69cf4eed18a6502d）。不在这里手改。
from __future__ import annotations
import hashlib
import os
import stat
import threading
from collections import OrderedDict
from pathlib import Path
_LOCK = threading.Lock()
_CACHE: OrderedDict[tuple[str, int, int, int, int, int, int], str] = OrderedDict()
_CAP = 32768
_READ_CHUNK = 1024 * 1024
_CTIME_IS_CHANGE_TIME = os.name == 'posix'

def _stat_signature(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (int(info.st_dev), int(info.st_ino), int(info.st_size), int(info.st_mtime_ns), int(info.st_ctime_ns), int(info.st_mode))

def _stat_identity(resolved: str) -> tuple[str, int, int, str]:
    before = os.stat(resolved)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('unsafe_file_identity')
    signature = _stat_signature(before)
    key = (resolved, *signature)
    public_identity = (resolved, int(before.st_size), int(before.st_mtime_ns))
    cacheable = _CTIME_IS_CHANGE_TIME and int(before.st_ino) != 0
    if cacheable:
        with _LOCK:
            hit = _CACHE.get(key)
            if hit is not None:
                _CACHE.move_to_end(key)
                return (*public_identity, hit)
    digest = hashlib.sha256()
    with open(resolved, 'rb') as stream:
        while (chunk := stream.read(_READ_CHUNK)):
            digest.update(chunk)
    after = os.stat(resolved)
    if _stat_signature(after) != signature or not stat.S_ISREG(after.st_mode):
        raise ValueError('file_changed_while_reading')
    value = digest.hexdigest()
    if cacheable:
        with _LOCK:
            _CACHE[key] = value
            while len(_CACHE) > _CAP:
                _CACHE.popitem(last=False)
    return (*public_identity, value)

def file_identity(path: Path) -> tuple[str, int, int, str]:
    return _stat_identity(str(Path(path).resolve()))

def walk_identity(root: Path) -> tuple[tuple[str, int, int, str], ...]:
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        return ()
    resolved_root = str(root.resolve())
    entries: list[tuple[str, int, int, str]] = []
    for dirpath, dirnames, filenames in os.walk(resolved_root):
        for name in sorted(dirnames + filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, resolved_root).replace(os.sep, '/')
            if os.path.islink(full):
                entries.append((rel, 0, 0, f'symlink:{os.readlink(full)}'))
                continue
            if os.path.isdir(full):
                continue
            entries.append((rel, *_stat_identity(full)[1:]))
    return tuple(sorted(entries))

def clear_file_identity_cache() -> None:
    with _LOCK:
        _CACHE.clear()
