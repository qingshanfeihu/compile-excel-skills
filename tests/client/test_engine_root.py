"""引擎数据根的摆放与找回：

- 几个工具调用同时第一次用：各自摆进独立的临时目录、在锁里换上，结果完整（H2）；
- 已摆好的数据根缺了文件：按文件清单查出来、重摆，不再因为标记在就一直用残缺的（H2）；
- 数据包里的文件被改过（或同步中断留下的混杂文件）：摆放前按清单 SHA 核，拒绝（M1）；
- 批次钉住开始时的数据根：换了数据包照样回到原来那个；它没了就如实报错；文件夹改名后
  旧版记的绝对路径照样找得回（M5）；
- 激活时清掉继承来的 IST_* 环境变量；引擎在数据根设好之前就被导入过，拒绝激活。

每个用例在子进程里跑（引擎按数据根在导入时定常量，激活还会改进程环境）。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

from cex_client import workspace as wsmod
from conftest import REPO_ROOT

FRAMEWORK_FILES = 1500


def _framework_tar() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for i in range(FRAMEWORK_FILES):
            data = f"# framework file {i}\n".encode() * 20
            info = tarfile.TarInfo(f"lib/pkg{i % 30}/mod{i}.py")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _bundle(ws: wsmod.Workspace, *, bundle_id: str = "e" * 64, extra: dict | None = None) -> None:
    files = {
        "framework/framework_tree.tar.gz": _framework_tar(),
        "projections/domain_grammar.json": b"{}",
        "manual/10.5.0/cli_cn.md": "# CLI\n".encode(),
        "cmdtree/source.json": json.dumps({"schema": "cex.cmdtree-source/v1",
                                           "full_version": "APV_10.5.0.585"}).encode(),
        **(extra or {}),
    }
    entries = []
    for rel, data in files.items():
        (ws.bundle_dir() / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws.bundle_dir() / rel).write_bytes(data)
        entries.append({"kind": rel.split("/", 1)[0], "path": rel,
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    (ws.bundle_dir() / "manifest.json").write_text(json.dumps(
        {"schema": "cex.bundle/v1", "bundle_id": bundle_id, "build": "B_1", "entries": entries}),
        encoding="utf-8")


def _workspace(tmp_path: Path, name: str = "ws") -> wsmod.Workspace:
    ws = wsmod.init(tmp_path / name, server="https://ces.example.test", device_build="B_1")
    _bundle(ws)
    return ws


def _py(script: str, env: dict | None = None) -> dict:
    code = f"import json, os, sys\nsys.path.insert(0, {str(REPO_ROOT)!r})\n" + script
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600,
                          env={**os.environ, "CEX_ENGINE_DATA_ROOT": "", **(env or {})})
    assert proc.returncode == 0, proc.stderr[-3000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_concurrent_first_use_builds_one_complete_root(tmp_path):
    ws = _workspace(tmp_path)
    start = time.time() + 2
    script = f"""
import time
from pathlib import Path
from cex_client import engine_env, workspace as wsmod
ws = wsmod.Workspace(Path({str(ws.root)!r}))
time.sleep(max(0.0, {start} - time.time()))
root, info = engine_env.materialize(ws)
print(json.dumps({{"root": str(root), "files": info.get("files")}}))
"""
    code = f"import json, sys\nsys.path.insert(0, {str(REPO_ROOT)!r})\n" + script
    procs = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) for _ in range(4)]
    results = [p.communicate(timeout=600) for p in procs]
    assert [p.returncode for p in procs] == [0, 0, 0, 0], [err[-1500:] for _out, err in results]
    roots = {json.loads(out.strip().splitlines()[-1])["root"] for out, _err in results}
    assert len(roots) == 1
    root = Path(roots.pop())
    mirror = root / "knowledge" / "framework" / "mirror" / "lib"
    assert sum(1 for p in mirror.rglob("*.py")) == FRAMEWORK_FILES
    from cex_client import engine_env

    assert engine_env._reusable(root) is not None
    leftovers = [p.name for p in root.parent.iterdir() if p.name != root.name]
    assert leftovers == [], "no staging directory is left behind"


def test_a_root_missing_files_is_rebuilt_not_reused(tmp_path):
    ws = _workspace(tmp_path)
    from cex_client import engine_env

    root, _info = engine_env.materialize(ws)
    victim = root / "knowledge" / "framework" / "mirror" / "lib" / "pkg3" / "mod3.py"
    assert victim.is_file()
    victim.unlink()
    again, _info = engine_env.materialize(ws)
    assert again == root and victim.is_file(), "the incomplete root was rebuilt"


def test_a_modified_bundle_file_never_reaches_the_engine_root(tmp_path):
    ws = _workspace(tmp_path)
    (ws.bundle_dir() / "projections" / "domain_grammar.json").write_text('{"tampered": 1}',
                                                                         encoding="utf-8")
    from cex_client import engine_env
    from cex_client.errors import ClientError

    try:
        engine_env.materialize(ws)
    except ClientError as exc:
        assert "cex_sync" in str(exc)
    else:
        raise AssertionError("a file that does not match the manifest was placed")
    assert not (ws.state_dir / "engine" / ("e" * 16)).exists()


def test_a_batch_stays_on_its_data_root_and_says_so_when_it_is_gone(tmp_path):
    ws = _workspace(tmp_path)
    result = _py(f"""
from pathlib import Path
from cex_client import engine_env, workspace as wsmod
from cex_client.errors import ClientError
ws = wsmod.Workspace(Path({str(ws.root)!r}))
root, info = engine_env.prepare(ws)
pinned = info["data_root"]
# 中途同步了另一版数据包：清单换了，钉住的数据根还在
manifest = json.loads((ws.bundle_dir() / "manifest.json").read_text())
manifest["bundle_id"] = "f" * 64
(ws.bundle_dir() / "manifest.json").write_text(json.dumps(manifest))
same, _ = engine_env.prepare(ws, pinned=pinned)
import shutil
shutil.rmtree(root)
try:
    engine_env.prepare(ws, pinned=pinned)
    gone = ""
except ClientError as exc:
    gone = str(exc)
print(json.dumps({{"pinned": pinned, "root": str(root), "same": str(same), "gone": gone,
                   "env": os.environ["CEX_ENGINE_DATA_ROOT"]}}))
""")
    assert result["pinned"] == ".compile-excel/engine/" + "e" * 16, "recorded relative to the folder"
    assert result["same"] == result["root"], "a bundle change does not switch a batch's data root"
    assert "cex_recompose_prepare" in result["gone"], result["gone"]


def test_a_renamed_workspace_finds_the_batch_root_by_its_old_absolute_path(tmp_path):
    ws = _workspace(tmp_path, "before")
    first = _py(f"""
from pathlib import Path
from cex_client import engine_env, workspace as wsmod
ws = wsmod.Workspace(Path({str(ws.root)!r}))
root, info = engine_env.prepare(ws)
print(json.dumps({{"root": str(root)}}))
""")
    moved = tmp_path / "after"
    shutil.move(str(ws.root), str(moved))
    second = _py(f"""
from pathlib import Path
from cex_client import engine_env, workspace as wsmod
ws = wsmod.Workspace(Path({str(moved.resolve())!r}))
root, info = engine_env.prepare(ws, pinned={first["root"]!r})
print(json.dumps({{"root": str(root)}}))
""")
    assert second["root"] == str(moved.resolve() / ".compile-excel" / "engine" / ("e" * 16))


def test_activation_drops_inherited_ist_variables(tmp_path):
    ws = _workspace(tmp_path)
    result = _py(f"""
from pathlib import Path
from cex_client import engine_env, workspace as wsmod
ws = wsmod.Workspace(Path({str(ws.root)!r}))
engine_env.prepare(ws)
from cex_core.engine.case_compiler.vendor_stdlib import configured_device_os_build
print(json.dumps({{"ist": sorted(k for k in os.environ if k.startswith("IST_")),
                   "build": configured_device_os_build()}}))
""", env={"IST_DEVICE_OS_BUILD": "APV_9.9.9.111", "IST_MULTI_TENANT": "1",
          "IST_SSH_USER": "someone", "IST_COMMAND_INVENTORY_VERSION": "9.9"})
    assert result["ist"] == []
    assert result["build"] == "585", "the bundle's device build, not the shell's"


def test_activation_refuses_an_engine_imported_before_its_root(tmp_path):
    ws = _workspace(tmp_path)
    result = _py(f"""
from pathlib import Path
from cex_client import engine_env, workspace as wsmod
from cex_client.errors import ClientError
import cex_core.engine.case_compiler.vendor_stdlib  # 数据根还没设：常量按"未设"算好了
ws = wsmod.Workspace(Path({str(ws.root)!r}))
root, _info = engine_env.materialize(ws)
try:
    engine_env.activate(root)
    error = ""
except ClientError as exc:
    error = str(exc)
print(json.dumps({{"error": error}}))
""")
    assert "before its data root was set" in result["error"], result


def test_activation_refuses_modules_bound_while_unset_even_after_the_root_is_set(tmp_path):
    """引擎导入时按"未设"算好了路径常量，之后有人补设了 CEX_ENGINE_DATA_ROOT（而且就是这个根）：
    只看"数据根现在设没设"会放行，引擎自己记下的 modules_bound_while_unset() 不会。"""
    ws = _workspace(tmp_path)
    result = _py(f"""
from pathlib import Path
from cex_client import engine_env, workspace as wsmod
from cex_client.errors import ClientError
import cex_core.engine.case_compiler.vendor_stdlib  # 数据根还没设：常量按"未设"算好了
from cex_core.engine import modules_bound_while_unset
ws = wsmod.Workspace(Path({str(ws.root)!r}))
root, _info = engine_env.materialize(ws)
os.environ["CEX_ENGINE_DATA_ROOT"] = str(root)  # 事后补设成同一个根
try:
    engine_env.activate(root)
    error = ""
except ClientError as exc:
    error = str(exc)
print(json.dumps({{"error": error, "bound": list(modules_bound_while_unset())}}))
""")
    assert result["bound"], "the engine recorded the modules that bound the unset root"
    assert "before its" in result["error"] and "data root was set" in result["error"], result
