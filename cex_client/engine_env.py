"""cex_core.engine 的数据根：从已同步的数据包在工作区里摆出 InfoTest 仓根的布局。

  .compile-excel/engine/<bundle_id 前 16 位>/
      knowledge/data/compile_ref/…              ← 包里的 projections/…，加 cmdtree/ 的命令树文件
      knowledge/data/manual/<版本>/…            ← manual/<版本>/{cli,app}_cn.md 与 catalog
      knowledge/data/auto_env/env_capabilities.json ← 设备 OS build（cmdtree/source.json）
      knowledge/data/auto_env/network_topology.json ← 本床拓扑（cex_bed_topology 取回，见 place_topology）
      knowledge/data/spec/active.json           ← 由 spec/manifest.json 算出的活动指针
      knowledge/data/spec/generations/<gid>/    ← spec/{manifest.json,index.json,state.tsv,docs/…}
      knowledge/framework/mirror/…              ← framework/framework_tree.tar.gz 解开
      knowledge/footprints/nodes_<版本>/…       ← footprints/nodes_<版本>.tar.gz 解开（包里只有一个
                                                  版本时同时摆成 nodes/，引擎两处都读）
      runtime/command_tree/products/…/builds/<ver>_<build>/{active.json,generations/<gid>/…}
                                                ← cmdtree/generation_manifest.json 声明的命令树代际
      runtime/criterion_author_rules.jsonl      ← projections/criterion_author_rules.jsonl（判据台账种子）
                                                  + 本工作区自己裁定过的记录（见 merge_local_rules）
      scripts/maintenance/assets/ssl_lifecycle_contract.json ← projections/ssl_lifecycle_contract.json
      main/case_compiler/*.py                   ← 抽取副本按 InfoTest 模块名写回的源码（见 code_mirror）

命令树投影要引擎认，还得有它记下的 XML（按文件名与哈希核对来源），拆卸图谱与 SSL 生命周期
证据还要核对命令树代际。数据包里的 XML 是发布端去掉凭据默认值后的版本，代际、投影、拆卸图谱
都由发布端用引擎自己的函数从这份 XML 重新推导（cmdtree/source.json 记着脱敏收据），这里只按
代际清单逐文件核哈希后摆放。旧数据包只有投影时仍按平面布局摆，引擎如实报命令树不可用。

一律复制（不链接）：引擎按 nofollow 读文件、代际 docs 还要求链接数为 1。包里缺规格书同步
台账（state.tsv，旧版导入器没发）时不摆规格书代际——引擎照它自己的"规格书不可达"走
no_governing_spec，而不是拿一个校验不过的代际去碰运气。

引擎模块在导入时就按数据根算常量，所以 ``activate`` 必须在第一次 import cex_core.engine
之前调用；同一进程里换数据根、或引擎在数据根设好之前就被导入过，都会被拒绝（circle 这类
长驻宿主换工作区要重启）。激活时去掉进程环境里的 IST_* 变量：引擎会读它们（设备 build、
命令清单版本、多租户……），从 shell 继承来的值不能盖过数据包里的事实。

摆放在工作区锁里做，先摆进同目录的独立临时目录（每个进程一个），摆齐、记下文件清单
（.inventory.json）再整体换上；复用已摆好的数据根前逐个核清单里的文件都在，缺了就重摆。
重组/编写批次记住它开始时用的数据根（工作区相对路径），后续调用都回到那一个（pinned_root）：
中途 cex_sync 换了数据包也不会悄悄换数据根；那个数据根没了就如实报错，让重新准备这一批。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from . import bundle
from .errors import ClientError
from .workspace import (
    Workspace,
    from_state_path,
    safe_component,
    safe_relative_path,
    state_lock,
    to_state_path,
)

DATA_ROOT_ENV = "CEX_ENGINE_DATA_ROOT"
LAYOUT = 4  # 摆放规则变了就加一，已摆好的旧数据根会重摆（4：带文件清单，复用前核文件在不在）
_MARKER = ".complete.json"
_INVENTORY = ".inventory.json"
_ENGINE_PREFIX = "cex_core.engine."
_ROOT_MODULE = "cex_core.engine._root"
_SPEC_ACTIVE_SCHEMA = "ist.spec.active"
_COMMAND_TREE_ACTIVE_SCHEMA = "ist.command-tree.active"
_GENERATION_MANIFEST = "cmdtree/generation_manifest.json"
# 不进 compile_ref、摆到引擎另读的位置的包内文件
_ROUTED_PROJECTIONS = {
    "ssl_lifecycle_contract.json": "scripts/maintenance/assets/ssl_lifecycle_contract.json",
    "criterion_author_rules.jsonl": "runtime/criterion_author_rules.jsonl",
}
_FOOTPRINT_TAR = re.compile(r"^footprints/nodes_([0-9][0-9.]*)\.tar\.gz$")
TOPOLOGY_REL = "knowledge/data/auto_env/network_topology.json"
TOPOLOGY_MD_REL = "knowledge/data/auto_env/network_topology_rag.md"
RULE_LEDGER_REL = "runtime/criterion_author_rules.jsonl"
ENGINE_DIR = Path(__file__).resolve().parents[1] / "cex_core" / "engine"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _command_tree_store(entries: dict[str, Path], root: Path) -> dict[str, Any]:
    """按代际清单摆命令树活动代际；清单里每个文件都要在包里且哈希一致。"""
    manifest_path = entries.get(_GENERATION_MANIFEST)
    if manifest_path is None:
        return {"status": "absent"}
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    ids = {key: safe_component(manifest.get(key), f"command tree {key}")
           for key in ("generation_id", "product", "platform", "version", "device_build")}
    partition = (root / "runtime" / "command_tree" / "products" / ids["product"] / "platforms"
                 / ids["platform"] / "builds" / f"{ids['version']}_{ids['device_build']}")
    generation = partition / "generations" / ids["generation_id"]
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ClientError("the command tree generation manifest declares no artifacts; "
                          "republish the bundle")
    shipped: dict[str, str] = {}
    for name, declared in sorted(artifacts.items()):
        name = safe_component(name, "command tree artifact")
        source = entries.get(f"cmdtree/{name}")
        digest = str((declared or {}).get("sha256") or "") if isinstance(declared, dict) else ""
        if source is None or _sha256(source) != digest:
            raise ClientError(f"the synced bundle's command tree file {name} does not match its "
                              "generation manifest; call cex_sync, or republish the bundle")
        _copy(source, generation / name)
        shipped[name] = digest
    (generation / "manifest.json").write_bytes(raw)
    active = {"schema": _COMMAND_TREE_ACTIVE_SCHEMA, "product": ids["product"],
              "platform": ids["platform"], "version": ids["version"],
              "device_build": ids["device_build"], "generation_id": ids["generation_id"],
              "manifest_sha256": hashlib.sha256(raw).hexdigest()}
    (partition / "active.json").write_text(
        json.dumps(active, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8")
    projection = next((digest for name, digest in shipped.items()
                       if name.startswith("vendor_stdlib_")), "")
    return {"status": "ready", "generation_id": ids["generation_id"],
            "manifest_sha256": active["manifest_sha256"], "projection_sha256": projection}


def _footprints(entries: dict[str, Path], root: Path) -> list[str]:
    base = root / "knowledge" / "footprints"
    versions = []
    for rel, path in sorted(entries.items()):
        match = _FOOTPRINT_TAR.match(rel)
        if not match:
            continue
        version = safe_component(match.group(1), "footprint version")
        versions.append(version)
        _extract_tree(path, base / f"nodes_{version}")
        receipt = entries.get(f"footprints/receipt_nodes_{version}.json")
        if receipt is not None:
            _copy(receipt, base / f".receipt_nodes_{version}.json")
    if len(versions) == 1:
        # 引擎的出处核对读不带版本的 nodes/；包里只有一个版本时它就是这个版本
        version = versions[0]
        _extract_tree(entries[f"footprints/nodes_{version}.tar.gz"], base / "nodes")
        receipt = entries.get(f"footprints/receipt_nodes_{version}.json")
        if receipt is not None:
            _copy(receipt, base / ".receipt_nodes.json")
    return versions


def root_for(ws: Workspace, manifest: dict[str, Any]) -> Path:
    bundle_id = str(manifest.get("bundle_id") or "")
    return ws.state_dir / "engine" / safe_component(bundle_id[:16] or "bundle", "bundle id")


def _reusable(target: Path) -> dict[str, Any] | None:
    """已摆好的数据根能不能直接用：标记是当前布局、文件清单没被改、清单里的文件一个不少。
    （引擎运行时会往数据根里添文件、续写台账，所以只核"在不在"，不核内容。）"""
    try:
        done = json.loads((target / _MARKER).read_text(encoding="utf-8"))
        raw = (target / _INVENTORY).read_bytes()
    except (OSError, ValueError):
        return None
    if not isinstance(done, dict) or done.get("layout") != LAYOUT \
            or hashlib.sha256(raw).hexdigest() != done.get("inventory_sha256"):
        return None
    try:
        files = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return None
    if not isinstance(files, list) or len(files) != done.get("files"):
        return None
    for rel in files:
        try:
            if not stat.S_ISREG(os.lstat(target / str(rel)).st_mode):
                return None
        except OSError:
            return None
    return done


def materialize(ws: Workspace) -> tuple[Path, dict[str, Any]]:
    with bundle.locked(ws, shared=True):
        manifest = bundle.cached_manifest(ws)
        if manifest is None:
            raise ClientError("no synced compile data; call cex_sync first")
        target = root_for(ws, manifest)
        done = _reusable(target)
        if done is not None:
            return target, done
        with state_lock(ws, "engine", target.name):
            done = _reusable(target)  # 等锁期间别的调用可能已经摆好
            if done is not None:
                return target, done
            return _build(ws, manifest, target)


def _build(ws: Workspace, manifest: dict[str, Any], target: Path) -> tuple[Path, dict[str, Any]]:
    target.parent.mkdir(parents=True, exist_ok=True)
    legacy = target.with_name(target.name + ".tmp")  # 旧版客户端的固定暂存名
    if legacy.is_dir() and not legacy.is_symlink():
        shutil.rmtree(legacy, ignore_errors=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", suffix=".staging",
                                    dir=target.parent))
    try:
        info = _populate(ws, manifest, staging)
        files = sorted(path.relative_to(staging).as_posix() for path in staging.rglob("*")
                       if path.is_file() and not path.is_symlink())
        inventory = json.dumps(files, ensure_ascii=False).encode("utf-8")
        (staging / _INVENTORY).write_bytes(inventory)
        info.update(files=len(files), inventory_sha256=hashlib.sha256(inventory).hexdigest())
        (staging / _MARKER).write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        bundle.swap_directory(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target, info


def pinned_root(ws: Workspace, recorded: Any) -> tuple[Path, dict[str, Any]]:
    """批次开始时用的数据根：还在且完整就用它；缺了文件而数据包没换就原地重摆；数据包已经
    换了（那一版的包已不在工作区里）就如实报错，让这一批在当前数据上重新准备。"""
    root = from_state_path(ws, recorded)
    if root.parent != ws.state_dir / "engine" or not root.name:
        raise ClientError(f"the batch state names {recorded!r}, which is not a compile data root "
                          "of this workspace; prepare the batch again")
    done = _reusable(root)
    if done is not None:
        return root, done
    manifest = bundle.cached_manifest(ws)
    if manifest is not None and root_for(ws, manifest) == root:
        return materialize(ws)
    current = str((manifest or {}).get("bundle_id") or "")[:16] or "none"
    raise ClientError(
        f"this batch was prepared on compile data {root.name}, which is no longer complete in this "
        f"workspace (the synced bundle is now {current}). Prepare the batch again on the current "
        "data: cex_recompose_prepare (same mindmap and out_name; recorded cases stay recorded), "
        "cex_recompose_seal, then cex_author_prepare")


def _populate(ws: Workspace, manifest: dict[str, Any], staging: Path) -> dict[str, Any]:
    bundle_id = str(manifest.get("bundle_id") or "")
    entries: dict[str, Path] = {}
    for entry in manifest.get("entries") or []:
        # 每个文件按清单 SHA 核过再摆：中断的同步、被改过的文件都不会进数据根
        entries[safe_relative_path(entry.get("path"))] = bundle.verified_file(ws, entry)
    compile_ref = staging / "knowledge" / "data" / "compile_ref"
    manual_root = staging / "knowledge" / "data" / "manual"
    command_tree: dict[str, Any] = {"projections": [], "xml": []}
    routed: list[str] = []
    for rel, path in entries.items():
        if rel.startswith("projections/"):
            tail = rel[len("projections/"):]
            if tail in _ROUTED_PROJECTIONS:
                _copy(path, staging / _ROUTED_PROJECTIONS[tail])
                routed.append(tail)
            else:
                _copy(path, compile_ref / tail)
        elif rel.startswith("cmdtree/") and rel not in ("cmdtree/source.json", _GENERATION_MANIFEST):
            # 平面布局：vendor_stdlib_<ver>_<build>.json 与 cmdtree_<build>.xml 并排，引擎按投影里
            # 记的 XML 文件名与哈希核对来源（没有活动代际时引擎就读这一份）
            name = safe_component(rel[len("cmdtree/"):], "command tree file")
            _copy(path, compile_ref / name)
            command_tree["xml" if name.endswith(".xml") else "projections"].append(name)
        elif rel.startswith("manual/"):
            tail = rel[len("manual/"):]
            if tail.endswith("/sync_state.json"):
                _copy(path, manual_root / ".sync_state.json")
            else:
                _copy(path, manual_root / tail)
    command_tree["store"] = _command_tree_store(entries, staging)
    build = str(manifest.get("build") or "")
    source: dict[str, Any] = {}
    if "cmdtree/source.json" in entries:
        source = json.loads(entries["cmdtree/source.json"].read_text(encoding="utf-8"))
        build = str(source.get("full_version") or build)
        if isinstance(source.get("sanitization"), dict):
            command_tree["sanitization"] = source["sanitization"]
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
            "capability": {"generation_id": str(source.get("generation_id") or ""),
                           "projection_sha256": str(source.get("projection_sha256") or "")},
            "routed": sorted(routed), "footprints": _footprints(entries, staging),
            "spec": _spec_generation(entries, staging), "framework_files": framework_files}
    return info


# ── 每次 prepare 都对齐的部分（不随数据包变） ───────────────────────────────


def _infotest_spelling(text: str) -> str:
    """抽取时的包改名（tools/extract_engine.py PACKAGES）倒回去；生成的 _root 助手不属 InfoTest。"""
    text = re.sub(r"\bcex_core\.engine\.scripts\b", "scripts", text)
    return re.sub(r"\bcex_core\.engine\b(?!\._root\b)", "main", text)


def code_mirror(root: Path) -> int:
    """派生规则收据要对规则逻辑取指纹：引擎按 InfoTest 路径（main/case_compiler/…）读源码。

    客户端没有 InfoTest 源码；这里把正在执行的抽取副本按 InfoTest 模块名写回数据根，
    指纹因此就是实际执行的那份逻辑。每次 prepare 都对齐（客户端升级后数据根不重摆）。
    """
    manifest = json.loads((ENGINE_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    written = 0
    for entry in manifest.get("modules") or []:
        source = str(entry.get("source") or "")
        if not source.startswith("main/case_compiler/") or source.endswith("/__init__.py"):
            continue
        rel = entry["engine_module"].split(".")[2:]
        text = _infotest_spelling(ENGINE_DIR.joinpath(*rel).with_suffix(".py")
                                  .read_text(encoding="utf-8"))
        target = root / safe_relative_path(source)
        if target.is_file() and target.read_text(encoding="utf-8") == text:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
        written += 1
    return written


def local_rules_path(ws: Workspace) -> Path:
    """本工作区裁定过的判据记录：换数据包（新数据根）时要接着用。"""
    return ws.state_dir / "criterion" / "criterion_author_rules.jsonl"


def merge_local_rules(ws: Workspace, root: Path) -> int:
    """把本工作区的裁定记录并进数据根的台账（按 rule_sha256 去重，追加在种子之后）。"""
    local = local_rules_path(ws)
    if not local.is_file():
        return 0
    ledger = root / RULE_LEDGER_REL
    present: set[str] = set()
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                present.add(str(json.loads(line).get("rule_sha256") or ""))
            except ValueError:
                continue
    missing = []
    for line in local.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and str(record.get("rule_sha256") or "") not in present:
            missing.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
            present.add(str(record.get("rule_sha256") or ""))
    if missing:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger, "a", encoding="utf-8") as stream:
            stream.write("".join(line + "\n" for line in missing))
    return len(missing)


def topology_path(ws: Workspace) -> Path:
    return ws.state_dir / "bed" / "network_topology.json"


def place_topology(ws: Workspace, root: Path) -> dict[str, Any] | None:
    """cex_bed_topology 取回的本床拓扑摆到引擎读的位置；没取过就不摆（判据照引擎报床事实不可用）。"""
    source = topology_path(ws)
    target = root / TOPOLOGY_REL
    if not source.is_file():
        if target.exists():
            target.unlink()
        return None
    raw = source.read_bytes()
    if not target.is_file() or target.read_bytes() != raw:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, target)
    rag = source.with_name("network_topology_rag.md")
    if rag.is_file():
        _copy(rag, root / TOPOLOGY_MD_REL)
    return {"path": str(target), "sha256": hashlib.sha256(raw).hexdigest()}


def _loaded_engine_modules() -> list[str]:
    return sorted(name for name in sys.modules
                  if name.startswith(_ENGINE_PREFIX) and name != _ROOT_MODULE)


def _bound_while_unset() -> tuple[str, ...]:
    """引擎自己记下的"数据根没设时就算过路径"的模块（cex_core.engine.modules_bound_while_unset）。"""
    if _ROOT_MODULE not in sys.modules:
        return ()
    from cex_core.engine import _root

    return tuple(getattr(_root, "modules_bound_while_unset", lambda: ())())


def activate(root: Path) -> Path:
    """设数据根；引擎已经按另一个数据根导入过、或在数据根设好之前就被导入过（它按"未设"算好了
    常量），都拒绝。两道判定都做：引擎自己记下的"未设时算过路径"的模块（之后再设环境变量也
    改不过来），和"引擎模块已导入而数据根还没设"。同时清掉进程环境里的 IST_* 变量。"""
    root = Path(root).resolve()
    current = os.environ.get(DATA_ROOT_ENV, "").strip()
    bound = _bound_while_unset()
    if bound:
        raise ClientError(
            f"the compile engine ({bound[0]}) computed its data paths in this process before its "
            "data root was set, so it holds no compile data; restart the harness")
    loaded = _loaded_engine_modules()
    if loaded:
        from cex_core.engine import _root

        if not _root.data_root_configured():
            raise ClientError(
                f"the compile engine ({loaded[0]}) was imported in this process before its data "
                "root was set, so it holds no compile data; restart the harness")
        if Path(current).expanduser().resolve() != root:
            raise ClientError("the compile engine is already loaded for another workspace or "
                              "batch data in this process; restart the harness to switch")
    for name in [key for key in os.environ if key.startswith("IST_")]:
        del os.environ[name]
    os.environ[DATA_ROOT_ENV] = str(root)
    return root


def prepare(ws: Workspace, pinned: Any = None) -> tuple[Path, dict[str, Any]]:
    """摆好（或找回批次钉住的）数据根、对齐每次都要对齐的部分，再激活。"""
    root, info = pinned_root(ws, pinned) if pinned else materialize(ws)
    with state_lock(ws, "engine", root.name):
        code_mirror(root)
        merge_local_rules(ws, root)
        topology = place_topology(ws, root)
    info = {**info, "topology": topology, "data_root": to_state_path(ws, root)}
    return activate(root), info


__all__ = ["DATA_ROOT_ENV", "activate", "code_mirror", "local_rules_path", "materialize",
           "merge_local_rules", "pinned_root", "place_topology", "prepare", "root_for",
           "topology_path"]
