"""本床拓扑事实：经网关 bed_topology 取回、存在工作区，编写阶段的判据都读它。

网关就在跳板机上，按 InfoTest 拓扑生成器同一套纯函数现合成本床 network_topology.json
（跳板机本机网卡、conf 里的各台主机、被测设备 show ip address）。客户端按原样存盘（摘要要
与网关给的 sha256 逐字节一致），engine_env 每次 prepare 把它摆到引擎读的位置；判据
（listener/VIP 选取、触发机与目标同段、后端真实地址、不可达地址）一律由引擎 env_facts 读，
这里把引擎给写手的那段床事实摘要转交，只改两处：
- 网关另报的本床服务清单（services：哪台主机、哪个地址、什么协议、哪个端口）一并列出——
  选后端按服务选，不是挑一个裸 IP；旧网关不报就是空表；
- 摘要里让写手调引擎内部工具（compile_report_underdetermined）的话，换成客户端里真能做的：
  把缺口如实告诉用户。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from . import engine_env, gateway
from .errors import ClientError
from .workspace import Workspace, write_file_safely

_PROTOCOLS = ("http", "https", "tcp", "udp", "dns")
_ENGINE_REPORT_TOOL = re.compile(
    r"用\s*compile_report_underdetermined\s*如实呈报\(obstacle=([^)]*)\)")
_ENGINE_TOOL_NAME = re.compile(r"compile_report_underdetermined")


def services_path(ws: Workspace):
    return engine_env.topology_path(ws).with_name("services.json")


def _write(ws: Workspace, path, data: bytes) -> None:
    write_file_safely(ws.root, path, data)


def normalize_services(raw: Any) -> list[dict[str, Any]]:
    """网关报的服务清单只留约定的五个字段；形状不对的条目丢掉（旧网关没有这一项就是空表）。"""
    out: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        proto = str(item.get("proto") or "").strip().lower()
        ip = str(item.get("ip") or "").strip()
        try:
            port = int(item.get("port"))
        except (TypeError, ValueError):
            port = None
        if proto not in _PROTOCOLS or not ip or port is None or not 0 < port < 65536:
            continue
        out.append({"host": str(item.get("host") or "").strip(), "ip": ip, "proto": proto,
                    "port": port, "note": str(item.get("note") or "").strip()})
    return out


def client_summary(text: str) -> str:
    """引擎摘要里客户端没有的工具换成客户端里该做的事。"""
    text = _ENGINE_REPORT_TOOL.sub(
        lambda m: f"把这一缺口如实告诉用户（{m.group(1)}），由用户补充床事实或调整用例", text)
    return _ENGINE_TOOL_NAME.sub("向用户如实报告缺口", text)


def _services_lines(services: list[dict[str, Any]]) -> list[str]:
    if not services:
        return []
    lines = ["本床服务清单(后端按服务选:协议与端口对得上的那一条,不要只挑一个裸 IP):"]
    for row in services:
        note = f"  ({row['note']})" if row.get("note") else ""
        lines.append(f"  {row['host'] or '-'} {row['ip']} {row['proto']}/{row['port']}{note}")
    return lines


def facts_view(topology: dict[str, Any],
               services: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """引擎 env_facts 对这份拓扑的结论：写手选地址时要的那几张表（须先 engine_env.prepare）。"""
    from cex_core.engine.ist_core.tools._shared.env_facts import EnvFacts

    facts = EnvFacts(topology)
    services = list(services or [])
    summary = client_summary(facts.summary_for_agent())
    extra = _services_lines(services)
    return {
        "services": services,
        "listener_ips": facts.listener_ips(),
        "service_ips": facts.service_ips(),
        "listener_trigger_pairs": [{"target": ip, "trigger_hosts": list(hosts)}
                                   for ip, hosts in facts.listener_trigger_pairs()],
        "summary": summary + ("\n" + "\n".join(extra) if extra else ""),
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
    services = normalize_services(out.get("services"))
    path = engine_env.topology_path(ws)
    _write(ws, path, raw)
    _write(ws, path.with_name("network_topology_rag.md"),
           str(out.get("rag_md") or "").encode("utf-8"))
    _write(ws, services_path(ws),
           (json.dumps(services, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    engine_env.prepare(ws)
    return {"ok": True, "sha256": out["sha256"], "path": str(path),
            "bed": topology.get("_bed"), "observation": out.get("observation"),
            **facts_view(topology, services)}


def load(ws: Workspace) -> dict[str, Any] | None:
    path = engine_env.topology_path(ws)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_services(ws: Workspace) -> list[dict[str, Any]]:
    try:
        return normalize_services(json.loads(services_path(ws).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


__all__ = ["client_summary", "facts_view", "fetch", "load", "load_services", "normalize_services"]
