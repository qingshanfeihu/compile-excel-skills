"""床事实视图（cex_bed_topology 与 cex_author_prepare 给写手的那一段）：

- 网关另报的服务清单（host/ip/proto/port/note）一并列出，选后端按服务选；旧网关不报就是空表（I2）；
- 引擎摘要里让写手调引擎内部工具 compile_report_underdetermined 的话，换成客户端里真能做的事。
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

from cex_client import bed, engine_env, gateway
from cex_client import workspace as wsmod
from conftest import REPO_ROOT

SERVICES = [
    {"host": "web1", "ip": "192.0.2.10", "proto": "http", "port": 80, "note": "nginx"},
    {"host": "dns1", "ip": "192.0.2.53", "proto": "DNS", "port": "53", "note": ""},
    {"host": "bad", "ip": "", "proto": "http", "port": 80},
    {"host": "bad2", "ip": "192.0.2.9", "proto": "gopher", "port": 70},
    "not a row",
]


def _engine_sentence() -> str:
    """env_facts.summary_for_agent 里提到 compile_report_underdetermined 的那句原文。"""
    source = (REPO_ROOT / "cex_core" / "engine" / "ist_core" / "tools" / "_shared"
              / "env_facts.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and "compile_report_underdetermined" in node.value:
            return node.value
    raise AssertionError("the engine summary no longer mentions compile_report_underdetermined")


def test_services_keep_the_agreed_fields_and_drop_malformed_rows():
    rows = bed.normalize_services(SERVICES)
    assert rows == [
        {"host": "web1", "ip": "192.0.2.10", "proto": "http", "port": 80, "note": "nginx"},
        {"host": "dns1", "ip": "192.0.2.53", "proto": "dns", "port": 53, "note": ""}]
    assert bed.normalize_services(None) == [] and bed.normalize_services({"x": 1}) == []


def test_the_summary_tells_the_agent_to_report_gaps_to_the_user():
    sentence = _engine_sentence()
    rewritten = bed.client_summary(sentence)
    assert "compile_report_underdetermined" not in rewritten
    assert "告诉用户" in rewritten and "不要猜 IP" in rewritten


def test_fetch_stores_and_shows_the_bed_services(tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    ws = wsmod.init(tmp_path / "ws", server="https://ces.example.test", device_build="B_1")
    topology = {"devices": [], "_bed": {"conf": "bed"}}
    raw = (json.dumps(topology, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    import hashlib

    reply = {"ok": True, "topology": topology, "sha256": hashlib.sha256(raw).hexdigest(),
             "rag_md": "# bed", "observation": {}, "services": SERVICES}
    monkeypatch.setattr(gateway, "call_tool", lambda _ws, name, args: dict(reply))
    monkeypatch.setattr(gateway, "lease_args", lambda _ws: {})
    monkeypatch.setattr(engine_env, "prepare", lambda _ws, **_k: (tmp_path, {}))
    seen = []
    monkeypatch.setattr(bed, "facts_view",
                        lambda topo, services=None: seen.append(services) or {"services": services})
    out = bed.fetch(ws)
    assert out["ok"] and out["services"] == bed.normalize_services(SERVICES)
    assert bed.load_services(ws) == bed.normalize_services(SERVICES), "kept for cex_author_prepare"
    old = {k: v for k, v in reply.items() if k != "services"}
    monkeypatch.setattr(gateway, "call_tool", lambda _ws, name, args: dict(old))
    assert bed.fetch(ws)["services"] == [] and bed.load_services(ws) == []


def test_the_facts_view_lists_services_next_to_the_engine_summary(tmp_path):
    code = f"""
import json, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import bed
topology = {{"devices": [{{"name": "APV0", "type": "APV", "ipv4": ["10.0.0.1/24"]}}]}}
view = bed.facts_view(topology, bed.normalize_services({SERVICES!r}))
print(json.dumps(view, ensure_ascii=False))
"""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          timeout=300, env={**os.environ, "CEX_ENGINE_DATA_ROOT": str(tmp_path)})
    assert proc.returncode == 0, proc.stderr[-3000:]
    view = json.loads(proc.stdout.strip().splitlines()[-1])
    assert view["services"][0]["ip"] == "192.0.2.10"
    assert "192.0.2.10 http/80" in view["summary"] and "192.0.2.53 dns/53" in view["summary"]
    assert "compile_report_underdetermined" not in view["summary"]
