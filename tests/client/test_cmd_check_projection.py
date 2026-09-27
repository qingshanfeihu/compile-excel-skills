"""cex_cmd_check 读的是生成器真实写出的投影形状：headers（厂商 XML）+ manual_declarations
（手册声明），heads 由加载时合成（与 InfoTest vendor_stdlib 加载同一判定：同名条目拒绝）。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cex_client import tools
from cex_client import workspace as wsmod
from cex_core.vendor_cmd import load_projection

PROJECTION = {
    "schema": "ist.vendor_stdlib", "version": "10.5", "device_os_build": "585",
    "headers": {"sdns listener": {"pmax": 1, "args": [{"position": 1, "type": "U16",
                                                       "optional": False}],
                                  "src": "vendor_xml:585:global/sdns/listener"}},
    "manual_declarations": {"sdns pool": {"pmax": 1, "src": "manual:cli_cn.md:12",
                                          "origin": "manual"}},
    "stats": {"vendor_header_count": 1},
}


def _workspace(tmp_path: Path, projection: dict) -> wsmod.Workspace:
    ws = wsmod.init(tmp_path / "ws", server="https://ces.example.test", device_build="B_1")
    data = json.dumps(projection).encode()
    rel = "cmdtree/vendor_stdlib_10.5_585.json"
    (ws.bundle_dir() / rel).parent.mkdir(parents=True, exist_ok=True)
    (ws.bundle_dir() / rel).write_bytes(data)
    (ws.bundle_dir() / "manifest.json").write_text(json.dumps({
        "bundle_id": "d" * 64, "build": "B_1",
        "entries": [{"kind": "cmdtree", "path": rel, "sha256": hashlib.sha256(data).hexdigest(),
                     "bytes": len(data)}]}), encoding="utf-8")
    return ws


def test_generator_shaped_projection_is_read(tmp_path):
    ws = _workspace(tmp_path, PROJECTION)
    out = tools.call("cex_cmd_check", {"workspace": str(ws.root),
                                       "commands": ["sdns listener 53", "sdns listener 53 54",
                                                    "sdns nope"]})
    assert out["ok"], out
    ok, extra, missing = out["results"]
    assert ok["hit"] and ok["head"] == "sdns listener"
    assert ok["src"] == "vendor_xml:585:global/sdns/listener"
    assert not extra["hit"] and extra["head"] == "sdns listener"
    assert extra["reason_code"] == "parameter_contract_violation"
    assert not missing["hit"] and missing["head"] == ""


def test_overlapping_tables_are_refused(tmp_path):
    bad = {**PROJECTION, "manual_declarations": {"sdns listener": {"pmax": 1, "src": "manual:x"}}}
    path = tmp_path / "p.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="同名"):
        load_projection(path)


def test_more_commands_than_the_limit_are_refused_not_silently_truncated(tmp_path):
    ws = _workspace(tmp_path, PROJECTION)
    over = tools.call("cex_cmd_check", {"workspace": str(ws.root),
                                        "commands": ["sdns listener 53"] * 201})
    assert over["ok"] is False and "201" in over["error"] and "split" in over["error"]
    full = tools.call("cex_cmd_check", {"workspace": str(ws.root),
                                        "commands": ["sdns listener 53"] * 200})
    assert full["ok"] and full["checked"] == 200 and len(full["results"]) == 200
