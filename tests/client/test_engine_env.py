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
                                              "xml": ["cmdtree_585.xml"],
                                              "store": {"status": "absent"}}
    query = result["query"]
    assert query["ok"] and query["data_root"] == str(root)
    assert "1 recorded command heads" in query["result"]


def test_a_projection_without_its_xml_is_reported_unavailable(tmp_path):
    query = _run(tmp_path, with_xml=False)["query"]
    assert query["ok"] and "capability unknown" in query["result"]


def test_generation_store_routed_files_mirror_topology_and_local_rules(tmp_path):
    """发布端推导出的命令树代际按清单摆成活动代际，引擎自己的读取函数认得出；判据台账种子与
    SSL 证据摆到引擎读的位置；派生规则指纹要读的源码按 InfoTest 模块名写回；本床拓扑与本工作区
    的裁定记录每次 prepare 都对齐。代际由引擎自己的 publish_local_command_tree 生成（投影生成器
    换成最小的合成投影），这样清单、代际号、投影策略身份都与客户端引擎一致。"""
    script = f'''
import hashlib, json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
gen_root = Path(tempfile.mkdtemp(dir={str(tmp_path)!r}))
os.environ["CEX_ENGINE_DATA_ROOT"] = str(gen_root)
from cex_core.engine.sync.command_tree_sync import projection_policy_identity, publish_local_command_tree
xml = {XML!r}
(gen_root / "in.xml").write_bytes(xml)
projection = dict({PROJECTION!r})

def builder(*, version, device_build, xml_path, output_dir, manual_version):
    payload = dict(projection, projection_policy=projection_policy_identity())
    payload["source"] = dict(payload["source"], sha256=hashlib.sha256(xml).hexdigest())
    out = Path(output_dir) / f"vendor_stdlib_{{version}}_{{device_build}}.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return {{"path": str(out)}}

(gen_root / "cmdtree_585.xml").write_bytes(xml)
result = publish_local_command_tree(xml_path=gen_root / "cmdtree_585.xml",
    expected_sha256=hashlib.sha256(xml).hexdigest(),
    full_version="Example Beta.APV-HG-K.10.5.0.585", version="10.5", projection_builder=builder,
    store_root=gen_root / "store")
gen = result.generation_root
files = {{
    "cmdtree/generation_manifest.json": (gen / "manifest.json").read_bytes(),
    "cmdtree/cmdtree_585.xml": (gen / "cmdtree_585.xml").read_bytes(),
    "cmdtree/vendor_stdlib_10.5_585.json": (gen / "vendor_stdlib_10.5_585.json").read_bytes(),
    "cmdtree/source.json": json.dumps({{"schema": "cex.cmdtree-source/v2",
        "full_version": result.full_version, "generation_id": result.generation_id,
        "projection_sha256": result.projection_sha256,
        "sanitization": {{"blanked_default_values": 0}}}}).encode(),
    "projections/criterion_author_rules.jsonl": b'{{"rule_sha256": "seed"}}\\n',
    "projections/ssl_lifecycle_contract.json": b'{{"schema": "x"}}',
    "projections/domain_grammar.json": b"{{}}",
    "manual/10.5.0/cli_cn.md": "# CLI\\n\\n**sdns listener** <port>\\n".encode(),
}}
print(json.dumps({{"files": {{k: v.hex() for k, v in files.items()}},
                   "generation_id": result.generation_id}}))
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=300, env={**os.environ, "IST_DEVICE_OS_BUILD": ""})
    assert proc.returncode == 0, proc.stderr[-3000:]
    made = json.loads(proc.stdout.strip().splitlines()[-1])
    blob = tmp_path / "files.json"
    blob.write_text(json.dumps(made["files"]), encoding="utf-8")
    ws_root = tmp_path / "ws"
    script = f'''
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import engine_env, workspace as wsmod
ws = wsmod.init(Path({str(ws_root)!r}), server="https://ces.example.test", device_build="B_1")
files = {{k: bytes.fromhex(v) for k, v in json.loads(Path({str(blob)!r}).read_text()).items()}}
entries = []
for rel, data in files.items():
    (ws.bundle_dir() / rel).parent.mkdir(parents=True, exist_ok=True)
    (ws.bundle_dir() / rel).write_bytes(data)
    entries.append({{"kind": rel.split("/", 1)[0], "path": rel,
                     "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}})
(ws.bundle_dir() / "manifest.json").write_text(json.dumps({{"bundle_id": "f" * 64, "build": "B_1",
    "entries": entries}}), encoding="utf-8")
topology = engine_env.topology_path(ws)
topology.parent.mkdir(parents=True, exist_ok=True)
topology.write_text('{{"devices": []}}\\n', encoding="utf-8")
local = engine_env.local_rules_path(ws)
local.parent.mkdir(parents=True, exist_ok=True)
local.write_text('{{"rule_sha256": "seed"}}\\n{{"rule_sha256": "mine"}}\\n', encoding="utf-8")
root, info = engine_env.prepare(ws)
engine_env.prepare(ws)  # 再来一次：台账不重复追加，拓扑不重写
from cex_core.engine.case_compiler import vendor_stdlib
from cex_core.engine.sync.command_tree_sync import resolve_active_command_tree
active = resolve_active_command_tree(product="APV", platform="HG-K", version="10.5",
                                     device_build="585")
loaded = vendor_stdlib.load_vendor_stdlib()
print(json.dumps({{"root": str(root), "info": info,
                   "active": active.generation_id if active else None,
                   "heads": sorted((loaded or {{}}).get("heads") or {{}})}}))
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=300, env={**os.environ, "CEX_ENGINE_DATA_ROOT": "",
                                            "IST_DEVICE_OS_BUILD": ""})
    assert proc.returncode == 0, proc.stderr[-3000:]
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    root = Path(result["root"])
    assert result["info"]["command_tree"]["store"]["status"] == "ready"
    assert result["active"] == made["generation_id"], "the engine resolves the active generation"
    assert result["heads"] == ["sdns listener"], "the projection loads through the store"
    assert (root / "scripts/maintenance/assets/ssl_lifecycle_contract.json").is_file()
    assert not (root / "knowledge/data/compile_ref/ssl_lifecycle_contract.json").exists()
    assert (root / "knowledge/data/compile_ref/domain_grammar.json").is_file()
    ledger = (root / "runtime/criterion_author_rules.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["rule_sha256"] for line in ledger] == ["seed", "mine"]
    assert (root / "knowledge/data/auto_env/network_topology.json").read_text() == '{"devices": []}\n'
    mirror = (root / "main/case_compiler/provenance_ir.py").read_text(encoding="utf-8")
    assert "from main.case_compiler." in mirror and "cex_core.engine.case_compiler" not in mirror
    assert "cex_core.engine._root" in mirror, "the generated root helper keeps its own name"
