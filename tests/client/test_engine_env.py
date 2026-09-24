"""引擎数据根的摆放：命令树投影、手册、设备 build 都放到引擎读的位置。

命令树投影要引擎认，还得有投影里记下的原始 XML（按文件名与哈希核对来源）。数据包只发
投影时，命令树查询如实报"不可用"，而不是拿一份核不了来源的投影去答。这里用一棵最小的
合成命令树（格式按引擎的投影契约）把两种情况都走一遍，每种在独立子进程里（引擎按数据根
在导入时定常量）。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

pytest.importorskip("langchain_core")

XML = (b'<commands><scope type="global"><menu name="sdns"><item name="listener">'
       b'<arguments><arg name="port" type="U16"/></arguments></item></menu></scope></commands>')
PROJECTION = {
    "schema": "ist.vendor_stdlib", "version": "10.5", "device_os_build": "585",
    "source": {"kind": "vendor_command_tree_xml", "device_os_build": "585",
               "filename": "cmdtree_585.xml", "sha256": hashlib.sha256(XML).hexdigest()},
    "headers": {"sdns listener": {"pmax": 1,
                                  "args": [{"position": 1, "type": "U16", "optional": False}],
                                  "src": "vendor_xml:585:global/sdns/listener"}},
    "manual_declarations": {}, "stats": {"vendor_header_count": 1},
}


def _run(tmp_path: Path, *, with_xml: bool) -> dict:
    files = {
        "cmdtree/vendor_stdlib_10.5_585.json": json.dumps(PROJECTION).encode(),
        "cmdtree/source.json": json.dumps({"schema": "cex.cmdtree-source/v1",
                                           "full_version": "APV_10.5.0.585"}).encode(),
        "manual/10.5.0/cli_cn.md": "# CLI\n\n**sdns listener** <port>\n".encode(),
        "manual/10.5.0/sync_state.json": b"{}",
    }
    if with_xml:
        files["cmdtree/cmdtree_585.xml"] = XML
    blob = tmp_path / "files.json"
    blob.write_text(json.dumps({k: v.hex() for k, v in files.items()}), encoding="utf-8")
    script = f'''
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import engine_env, tools, workspace as wsmod
ws = wsmod.init(Path({str(tmp_path / "ws")!r}), server="https://ces.example.test", device_build="B_1")
files = {{k: bytes.fromhex(v) for k, v in json.loads(Path({str(blob)!r}).read_text()).items()}}
entries = []
for rel, data in files.items():
    (ws.bundle_dir() / rel).parent.mkdir(parents=True, exist_ok=True)
    (ws.bundle_dir() / rel).write_bytes(data)
    entries.append({{"kind": rel.split("/", 1)[0], "path": rel,
                     "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}})
(ws.bundle_dir() / "manifest.json").write_text(json.dumps({{"bundle_id": "e" * 64, "build": "B_1",
    "entries": entries}}), encoding="utf-8")
root, info = engine_env.materialize(ws)
out = tools.call("cex_lang_query", {{"workspace": str(ws.root), "kind": "complete",
                                     "name": "sdns list"}})
print(json.dumps({{"root": str(root), "info": info, "query": out}}, ensure_ascii=False))
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=300, env={**os.environ, "CEX_ENGINE_DATA_ROOT": "",
                                            "IST_DEVICE_OS_BUILD": ""})
    assert proc.returncode == 0, proc.stderr[-3000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_layout_places_command_tree_manuals_and_build(tmp_path):
    result = _run(tmp_path, with_xml=True)
    root = Path(result["root"])
    assert (root / "knowledge/data/compile_ref/vendor_stdlib_10.5_585.json").is_file()
    assert (root / "knowledge/data/manual/10.5.0/cli_cn.md").is_file()
    assert (root / "knowledge/data/manual/.sync_state.json").is_file()
    capabilities = json.loads((root / "knowledge/data/auto_env/env_capabilities.json")
                              .read_text(encoding="utf-8"))
    assert capabilities == {"build": "APV_10.5.0.585"}
    assert result["info"]["command_tree"] == {"projections": ["vendor_stdlib_10.5_585.json"],
                                              "xml": ["cmdtree_585.xml"]}
    query = result["query"]
    assert query["ok"] and query["data_root"] == str(root)
    assert "1 recorded command heads" in query["result"]


def test_a_projection_without_its_xml_is_reported_unavailable(tmp_path):
    query = _run(tmp_path, with_xml=False)["query"]
    assert query["ok"] and "capability unknown" in query["result"]
