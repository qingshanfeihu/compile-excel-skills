"""cex_core.engine 的数据根：从已同步的数据包在工作区里摆出 InfoTest 仓根的布局。

  .compile-excel/engine/<bundle_id 前 16 位>/
      knowledge/data/compile_ref/…              ← 包里的 projections/…，加 cmdtree/ 的命令树投影
                                                  （数据包带了原始 XML 就并排放）
      knowledge/data/manual/<版本>/…            ← manual/<版本>/{cli,app}_cn.md 与 catalog
      knowledge/data/auto_env/env_capabilities.json ← 设备 OS build（cmdtree/source.json）
      knowledge/data/spec/active.json           ← 由 spec/manifest.json 算出的活动指针
      knowledge/data/spec/generations/<gid>/    ← spec/{manifest.json,index.json,state.tsv,docs/…}
      knowledge/framework/mirror/…              ← framework/framework_tree.tar.gz 解开

命令树投影要引擎认，还得有它记下的原始 XML（按文件名与哈希核对来源）；数据包只发投影时
引擎的命令树查询（lang_query 的 param / complete、step_structure 的对象类型闭集）如实报
不可用，命令存在性与参数个数改由 cex_cmd_check 直接读投影判（同一判定函数）。

一律复制（不链接）：引擎按 nofollow 读文件、代际 docs 还要求链接数为 1。包里缺规格书同步
台账（state.tsv，旧版导入器没发）时不摆规格书代际——引擎照它自己的"规格书不可达"走
no_governing_spec，而不是拿一个校验不过的代际去碰运气。

引擎模块在导入时就按数据根算常量，所以 ``activate`` 必须在第一次 import cex_core.engine
之前调用；同一进程里换数据根会被拒绝（circle 这类长驻宿主换工作区要重启）。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any

from . import bundle
from .errors import ClientError
from .workspace import Workspace, safe_component, safe_relative_path

DATA_ROOT_ENV = "CEX_ENGINE_DATA_ROOT"
LAYOUT = 2  # 摆放规则变了就加一，已摆好的旧数据根会重摆
_MARKER = ".complete.json"
_SPEC_ACTIVE_SCHEMA = "ist.spec.active"


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _extract_tree(archive: Path, target: Path) -> int:
    """只解普通文件与目录，路径必须留在 target 之内。"""
    count = 0
    with tarfile.open(archive, "r:*") as tar:
        for member in tar.getmembers():
            name = member.name
            while name.startswith("./"):
                name = name[2:]
            name = name.rstrip("/")
            if name in ("", "."):
                continue
            dest = target / safe_relative_path(name)
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                source = tar.extractfile(member)
                if source is None:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with source, open(dest, "wb") as out:
                    shutil.copyfileobj(source, out)
                count += 1
    return count


def _spec_generation(entries: dict[str, Path], root: Path) -> dict[str, Any]:
    manifest_path = entries.get("spec/manifest.json")
    if manifest_path is None:
        return {"status": "absent"}
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    generation_id = str(manifest.get("generation_id") or "")
    safe_component(generation_id, "spec generation id")
    if "spec/state.tsv" not in entries or "spec/index.json" not in entries:
        return {"status": "incomplete", "generation_id": generation_id,
                "note": "the bundle has no spec sync ledger (state.tsv); republish it with the "
                        "current importer to get governing-spec lookup"}
    store = root / "knowledge" / "data" / "spec"
    generation = store / "generations" / generation_id
    _copy(manifest_path, generation / "manifest.json")
    _copy(entries["spec/index.json"], generation / "index.json")
    _copy(entries["spec/state.tsv"], generation / "state.tsv")
    (generation / "docs").mkdir(parents=True, exist_ok=True)
    for rel, path in entries.items():
        if rel.startswith("spec/docs/"):
            _copy(path, generation / "docs" / rel[len("spec/docs/"):])
    active = {"schema": _SPEC_ACTIVE_SCHEMA, "generation_id": generation_id,
              "manifest_sha256": hashlib.sha256(raw).hexdigest()}
    (store / "active.json").write_text(json.dumps(active, ensure_ascii=False), encoding="utf-8")
    return {"status": "ready", "generation_id": generation_id}


def materialize(ws: Workspace) -> tuple[Path, dict[str, Any]]:
    manifest = bundle.cached_manifest(ws)
    if manifest is None:
        raise ClientError("no synced compile data; call cex_sync first")
    bundle_id = str(manifest.get("bundle_id") or "")
    target = ws.state_dir / "engine" / safe_component(bundle_id[:16] or "bundle", "bundle id")
    marker = target / _MARKER
    if marker.is_file():
        done = json.loads(marker.read_text(encoding="utf-8"))
        if done.get("layout") == LAYOUT:
            return target, done
    staging = target.with_name(target.name + ".tmp")
    if staging.exists():
        shutil.rmtree(staging)
    root_dir = ws.bundle_dir()
    entries: dict[str, Path] = {}
    for entry in manifest.get("entries") or []:
        rel = safe_relative_path(entry.get("path"))
        path = root_dir / rel
        if not path.is_file():
            raise ClientError(f"synced bundle is missing {rel}; call cex_sync")
        entries[rel] = path
    compile_ref = staging / "knowledge" / "data" / "compile_ref"
    manual_root = staging / "knowledge" / "data" / "manual"
    command_tree: dict[str, Any] = {"projections": [], "xml": []}
    for rel, path in entries.items():
        if rel.startswith("projections/"):
            _copy(path, compile_ref / rel[len("projections/"):])
        elif rel.startswith("cmdtree/") and rel != "cmdtree/source.json":
            # 平面布局：vendor_stdlib_<ver>_<build>.json 与（若数据包带了）cmdtree_<build>.xml
            # 并排，引擎按投影里记的 XML 文件名与哈希核对来源
            name = safe_component(rel[len("cmdtree/"):], "command tree file")
            _copy(path, compile_ref / name)
            command_tree["xml" if name.endswith(".xml") else "projections"].append(name)
        elif rel.startswith("manual/"):
            tail = rel[len("manual/"):]
            if tail.endswith("/sync_state.json"):
                _copy(path, manual_root / ".sync_state.json")
            else:
                _copy(path, manual_root / tail)
    build = str(manifest.get("build") or "")
    if "cmdtree/source.json" in entries:
        source = json.loads(entries["cmdtree/source.json"].read_text(encoding="utf-8"))
        build = str(source.get("full_version") or build)
    if build:
        # 引擎从这里取设备 OS build（configured_device_os_build），用来选命令树分区
        capabilities = staging / "knowledge" / "data" / "auto_env" / "env_capabilities.json"
        capabilities.parent.mkdir(parents=True, exist_ok=True)
        capabilities.write_text(json.dumps({"build": build}, ensure_ascii=False), encoding="utf-8")
    mirror = staging / "knowledge" / "framework" / "mirror"
    framework_files = 0
    if "framework/framework_tree.tar.gz" in entries:
        framework_files = _extract_tree(entries["framework/framework_tree.tar.gz"], mirror)
        if "framework/sync_meta.json" in entries:
            _copy(entries["framework/sync_meta.json"], mirror / ".sync_meta.json")
    info = {"layout": LAYOUT, "bundle_id": bundle_id, "build": manifest.get("build"),
            "device_os_build": build or None, "command_tree": command_tree,
            "spec": _spec_generation(entries, staging), "framework_files": framework_files}
    staging.mkdir(parents=True, exist_ok=True)
    (staging / _MARKER).write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    if target.exists():
        shutil.rmtree(target)
    os.replace(staging, target)
    return target, info


def activate(root: Path) -> Path:
    """设数据根；引擎已经按另一个数据根导入过就拒绝。"""
    root = Path(root).resolve()
    current = os.environ.get(DATA_ROOT_ENV, "").strip()
    if "cex_core.engine._root" in sys.modules and current and Path(current).resolve() != root:
        raise ClientError("the compile engine is already loaded for another workspace in this "
                          "process; restart the harness to switch workspaces")
    os.environ[DATA_ROOT_ENV] = str(root)
    return root


def prepare(ws: Workspace) -> tuple[Path, dict[str, Any]]:
    root, info = materialize(ws)
    return activate(root), info


__all__ = ["DATA_ROOT_ENV", "activate", "materialize", "prepare"]
