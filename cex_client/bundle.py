"""把服务端数据包同步进工作区：清单 → 逐个 blob 下载 → 按清单 SHA 校验 → 整包原子换上。

- 新版本在旁边的临时目录里摆齐（本地已有且哈希一致的文件复制过去，不重下；其余下载），
  每个文件都按清单 SHA 核过，最后连同清单一起换掉 bundle/<build>/。中途失败（断网、拒收）
  旧包原样不动，不会出现"旧清单 + 新旧混杂的文件"；
- 下载内容与清单 SHA 不符就拒收；
- 服务端不可达时，核验本地缓存完整后回退使用，并在结果里写明用的是哪一版缓存；
- 读包里的文件（entry_path、引擎数据根的摆放）也按清单 SHA 再核一遍，被改过就让先 cex_sync。
同步与读包之间用工作区锁（同步独占、读取共享）。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import auth
from .errors import ClientError, ServerUnreachable
from .workspace import Workspace, safe_component, safe_relative_path, state_lock

MANIFEST = "manifest.json"
_SHA_CHARS = set("0123456789abcdef")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target(root: Path, rel: str) -> Path:
    target = (root / safe_relative_path(rel)).resolve()
    if root.resolve() not in target.parents:
        raise ClientError(f"bundle entry escapes the bundle directory: {rel!r}")
    return target


def _check_manifest(manifest: dict[str, Any], build: str) -> list[dict[str, Any]]:
    if manifest.get("schema") != "cex.bundle/v1" or manifest.get("build") != build:
        raise ClientError("server returned a bundle for another build or an unknown schema")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ClientError("bundle manifest has no entries")
    for entry in entries:
        sha = str(entry.get("sha256") or "")
        if len(sha) != 64 or set(sha) - _SHA_CHARS:
            raise ClientError(f"bundle entry has an invalid sha256: {entry.get('path')!r}")
        safe_relative_path(entry.get("path"))
    return entries


@contextmanager
def locked(ws: Workspace, build: str | None = None, *, shared: bool = False) -> Iterator[None]:
    with state_lock(ws, "bundle", build or ws.device_build, shared=shared):
        yield


def _download(ws: Workspace, sha: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    status, raw = auth.request(ws, "GET", f"/v1/blobs/{sha}", timeout=600)
    if status != 200:
        raise ClientError(f"blob {sha[:12]} download failed (HTTP {status})")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != sha:
        raise ClientError(f"SHA256 mismatch for {target.name}: expected {sha[:12]}, "
                          f"got {actual[:12]}; refused to write")
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".part", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _summary(manifest: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in manifest.get("entries") or []:
        counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1
    return counts


def cached_manifest_at(root: Path) -> dict[str, Any] | None:
    try:
        data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def cached_manifest(ws: Workspace, build: str | None = None) -> dict[str, Any] | None:
    return cached_manifest_at(ws.bundle_dir(build))


def verify_cache(ws: Workspace, build: str | None = None) -> dict[str, Any]:
    manifest = cached_manifest(ws, build)
    if manifest is None:
        raise ClientError("no cached bundle")
    root = ws.bundle_dir(build)
    for entry in _check_manifest(manifest, manifest.get("build", "")):
        path = _target(root, entry["path"])
        if not path.is_file() or _sha256_file(path) != entry["sha256"]:
            raise ClientError(f"cached bundle is incomplete or modified: {entry['path']}")
    return manifest


def _unchanged(root: Path, manifest: dict[str, Any], entries: list[dict[str, Any]]) -> bool:
    """本地已是这一版且每个文件都核得上：什么都不用做。"""
    cached = cached_manifest_at(root)
    if not cached or cached.get("bundle_id") != manifest.get("bundle_id"):
        return False
    if {(e.get("path"), e.get("sha256")) for e in cached.get("entries") or []} != \
            {(e["path"], e["sha256"]) for e in entries}:
        return False
    for entry in entries:
        path = _target(root, entry["path"])
        if not path.is_file() or _sha256_file(path) != entry["sha256"]:
            return False
    return True


def sync(ws: Workspace, channel: str | None = None) -> dict[str, Any]:
    build = ws.device_build
    channel = channel or ws.channel
    root = ws.bundle_dir(build)
    try:
        manifest = auth.request_json(
            ws, "GET", f"/v1/builds/{safe_component(build, 'device_build')}/bundle"
                       f"?channel={channel}")
    except ServerUnreachable:
        with locked(ws, build, shared=True):
            cached = verify_cache(ws, build)
        return {"ok": True, "source": "cache", "build": build,
                "bundle_id": cached.get("bundle_id"), "entries": _summary(cached),
                "note": f"server unreachable; using the cached bundle "
                        f"{str(cached.get('bundle_id'))[:12]} created {cached.get('created_at')}"}
    entries = _check_manifest(manifest, build)
    with locked(ws, build):
        if _unchanged(root, manifest, entries):
            return {"ok": True, "source": "server", "build": build, "channel": channel,
                    "bundle_id": manifest.get("bundle_id"), "downloaded": 0,
                    "unchanged": len(entries), "removed": 0, "entries": _summary(manifest)}
        previous = cached_manifest_at(root) or {}
        root.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.", suffix=".sync", dir=root.parent))
        try:
            downloaded = unchanged = 0
            for entry in entries:
                target = _target(staging, entry["path"])
                current = _target(root, entry["path"]) if root.is_dir() else None
                if current is not None and current.is_file() \
                        and _sha256_file(current) == entry["sha256"]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(current, target)
                    unchanged += 1
                else:
                    _download(ws, entry["sha256"], target)
                    downloaded += 1
                if _sha256_file(target) != entry["sha256"]:
                    raise ClientError(f"staged bundle file {entry['path']} does not match its "
                                      "manifest; nothing was changed")
            (staging / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
            swap_directory(staging, root)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    keep = {entry["path"] for entry in entries}
    removed = sum(1 for entry in previous.get("entries") or [] if entry.get("path") not in keep)
    return {"ok": True, "source": "server", "build": build, "channel": channel,
            "bundle_id": manifest.get("bundle_id"), "downloaded": downloaded,
            "unchanged": unchanged, "removed": removed, "entries": _summary(manifest)}


def swap_directory(staging: Path, root: Path) -> None:
    """摆齐的新包换上：旧目录先挪到旁边，新目录改名就位，再删旧的。"""
    old = None
    if root.exists():
        old = Path(tempfile.mkdtemp(prefix=f".{root.name}.", suffix=".old", dir=root.parent))
        os.rmdir(old)
        os.rename(root, old)
    try:
        os.rename(staging, root)
    except BaseException:
        if old is not None and not root.exists():
            os.rename(old, root)
        raise
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)


def verified_file(ws: Workspace, entry: dict[str, Any], build: str | None = None) -> Path:
    """包里一个条目的本地文件，按清单 SHA 核过才给。"""
    path = _target(ws.bundle_dir(build), str(entry.get("path") or ""))
    if not path.is_file() or _sha256_file(path) != str(entry.get("sha256") or ""):
        raise ClientError(f"the synced bundle file {entry.get('path')} is missing or does not match "
                          "its manifest (an interrupted or tampered sync); call cex_sync")
    return path


def entry_path(ws: Workspace, kind: str, name_prefix: str = "") -> Path | None:
    """已同步包里某一类的第一个文件（可按文件名前缀过滤），按清单 SHA 核过。"""
    with locked(ws, shared=True):
        manifest = cached_manifest(ws)
        if manifest is None:
            return None
        for entry in manifest.get("entries") or []:
            rel = str(entry.get("path") or "")
            if entry.get("kind") == kind and rel.rsplit("/", 1)[-1].startswith(name_prefix):
                return verified_file(ws, entry)
    return None
