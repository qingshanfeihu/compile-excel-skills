"""本床拓扑事实：经网关 bed_topology 取回、存在工作区，编写阶段的判据都读它。

网关就在跳板机上，按 InfoTest 拓扑生成器同一套纯函数现合成本床 network_topology.json
（跳板机本机网卡、conf 里的各台主机、被测设备 show ip address）。客户端按原样存盘（摘要要
与网关给的 sha256 逐字节一致），engine_env 每次 prepare 把它摆到引擎读的位置；判据
（listener/VIP 选取、触发机与目标同段、后端真实地址、不可达地址）一律由引擎 env_facts 读，
这里只把引擎给写手的那段床事实摘要原样转交。
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from . import engine_env, gateway
from .errors import ClientError
from .workspace import Workspace


def _write(path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def facts_view(topology: dict[str, Any]) -> dict[str, Any]:
    """引擎 env_facts 对这份拓扑的结论：写手选地址时要的那几张表（须先 engine_env.prepare）。"""
    from cex_core.engine.ist_core.tools._shared.env_facts import EnvFacts

    facts = EnvFacts(topology)
    return {
        "listener_ips": facts.listener_ips(),
        "service_ips": facts.service_ips(),
        "listener_trigger_pairs": [{"target": ip, "trigger_hosts": list(hosts)}
                                   for ip, hosts in facts.listener_trigger_pairs()],
        "summary": facts.summary_for_agent(),
    }


def fetch(ws: Workspace, *, refresh: bool = False) -> dict[str, Any]:
    out = gateway.call_tool(ws, "bed_topology", {**gateway.lease_args(ws), "refresh": bool(refresh)})
    if not out.get("ok"):
        return out
    topology = out.get("topology")
    if not isinstance(topology, dict):
        raise ClientError("the gateway returned no topology")
    raw = (json.dumps(topology, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != out.get("sha256"):
        raise ClientError("the bed topology does not match the digest the gateway sent")
    path = engine_env.topology_path(ws)
    _write(path, raw)
    _write(path.with_name("network_topology_rag.md"), str(out.get("rag_md") or "").encode("utf-8"))
    engine_env.prepare(ws)
    return {"ok": True, "sha256": out["sha256"], "path": str(path),
            "bed": topology.get("_bed"), "observation": out.get("observation"),
            **facts_view(topology)}


def load(ws: Workspace) -> dict[str, Any] | None:
    path = engine_env.topology_path(ws)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["facts_view", "fetch", "load"]
