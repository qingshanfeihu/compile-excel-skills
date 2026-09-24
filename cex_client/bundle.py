"""把服务端数据包同步进工作区：清单 → 逐个 blob 下载 → 按清单 SHA 校验 → 原子落位。

- 本地已有且哈希一致的文件不重下；
- 下载内容与清单 SHA 不符就拒收，已有文件不动；
- 新清单里没有、旧清单里有的文件删除（只删旧清单登记过的文件，不碰别的）；
- 服务端不可达时，核验本地缓存完整后回退使用，并在结果里写明用的是哪一版缓存。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from . import auth
from .errors import ClientError, ServerUnreachable
from .workspace import Workspace, safe_component, safe_relative_path

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


def cached_manifest(ws: Workspace, build: str | None = None) -> dict[str, Any] | None:
    path = ws.bundle_dir(build) / MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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


def sync(ws: Workspace, channel: str | None = None) -> dict[str, Any]:
    build = ws.device_build
    channel = channel or ws.channel
    root = ws.bundle_dir(build)
    try:
        manifest = auth.request_json(
            ws, "GET", f"/v1/builds/{safe_component(build, 'device_build')}/bundle"
                       f"?channel={channel}")
    except ServerUnreachable:
        cached = verify_cache(ws, build)
        return {"ok": True, "source": "cache", "build": build,
                "bundle_id": cached.get("bundle_id"), "entries": _summary(cached),
                "note": f"server unreachable; using the cached bundle "
                        f"{str(cached.get('bundle_id'))[:12]} created {cached.get('created_at')}"}
    entries = _check_manifest(manifest, build)
    previous = cached_manifest(ws, build) or {}
    downloaded = unchanged = 0
    for entry in entries:
        target = _target(root, entry["path"])
        if target.is_file() and _sha256_file(target) == entry["sha256"]:
            unchanged += 1
            continue
        _download(ws, entry["sha256"], target)
        downloaded += 1
    keep = {entry["path"] for entry in entries}
    removed = 0
    for entry in previous.get("entries") or []:
        rel = entry.get("path")
        if rel in keep:
            continue
        try:
            path = _target(root, rel)
        except ClientError:
            continue
        if path.is_file():
            path.unlink()
            removed += 1
    tmp = root / f".{MANIFEST}.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, root / MANIFEST)
    return {"ok": True, "source": "server", "build": build, "channel": channel,
            "bundle_id": manifest.get("bundle_id"), "downloaded": downloaded,
            "unchanged": unchanged, "removed": removed, "entries": _summary(manifest)}


def entry_path(ws: Workspace, kind: str, name_prefix: str = "") -> Path | None:
    """已同步包里某一类的第一个文件（可按文件名前缀过滤）。"""
    manifest = cached_manifest(ws)
    if manifest is None:
        return None
    for entry in manifest.get("entries") or []:
        rel = str(entry.get("path") or "")
        if entry.get("kind") == kind and rel.rsplit("/", 1)[-1].startswith(name_prefix):
            path = _target(ws.bundle_dir(), rel)
            if path.is_file():
                return path
    return None
