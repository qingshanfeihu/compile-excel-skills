# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/_shared/env_facts.py（sha256 a68684bfa000c2c6）。不在这里手改。
from __future__ import annotations
import functools
import ipaddress
import json
import logging
import re
from cex_core.engine import knowledge_paths as _kp
logger = logging.getLogger(__name__)
_TOPOLOGY_JSON = _kp.KNOWLEDGE_AUTO_ENV_TOPOLOGY_JSON
_ACTIONS_JSON = _kp.KNOWLEDGE_AUTO_ENV_ACTIONS_JSON
_IPV4_RE = re.compile('\\b(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\b')
_NON_HOST_IPV4S = frozenset({'0.0.0.0', '255.255.255.255'})
_IPV6_TOKEN_RE = re.compile('[0-9A-Fa-f:.]{2,}')

def _is_contiguous_netmask(ip: str) -> bool:
    try:
        value = int(ipaddress.IPv4Address(ip))
    except ValueError:
        return False
    inverted = value ^ 4294967295
    return inverted & inverted + 1 == 0

def normalize_ip_literal(value: object) -> str:
    text = str(value or '').strip().strip('[]')
    if not text:
        return ''
    text = text.split('%')[0].split('/')[0]
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return ''
_SERVER_TYPES = ('服务器',)
_LB_TYPES = ('负载均衡',)
_TRIGGER_TYPES = ('路由器', '客户端')

class EnvFacts:

    def __init__(self, doc: dict):
        self._doc = doc
        self.devices: list[dict] = doc.get('devices', [])
        self._exact_ips: set[str] = set()
        self._subnets: list[ipaddress.IPv4Network] = []
        self._subnets6: list = []
        self._dev_nets: dict[str, list] = {}
        self._dev_exact: dict[str, set[str]] = {}
        self._dev_ifaces: dict[str, dict[str, list[str]]] = {}
        self._driver_names: set[str] = set()
        self._display_name: dict[str, str] = {}
        self._routes: list[tuple[str, object]] = []
        self._routes_uninterpretable = False
        self._build()
        self._build_routes(doc)

    def _build(self) -> None:
        seen_subnets: set[str] = set()
        for dev in self.devices:
            name_l = str(dev.get('name', '')).strip().lower()
            if name_l:
                self._display_name.setdefault(name_l, str(dev.get('name', '')).strip())
                self._dev_nets.setdefault(name_l, [])
                self._dev_exact.setdefault(name_l, set())
                self._dev_ifaces.setdefault(name_l, {})
                for iface, spec in (dev.get('interfaces') or {}).items():
                    if not isinstance(spec, dict):
                        continue
                    declared = [str(spec.get(family) or '').strip() for family in ('ipv4', 'ipv6')]
                    kept = [item for item in declared if item]
                    if kept:
                        self._dev_ifaces[name_l][str(iface).strip()] = kept
                if any((t in dev.get('type', '') for t in _TRIGGER_TYPES)):
                    self._driver_names.add(name_l)
            for cidr in dev.get('ipv4', []):
                bare = cidr.split('/')[0]
                self._exact_ips.add(bare)
                if name_l:
                    self._dev_exact[name_l].add(bare)
                if '/' in cidr:
                    try:
                        net = ipaddress.ip_network(cidr, strict=False)
                    except ValueError:
                        continue
                    if str(net) not in seen_subnets:
                        seen_subnets.add(str(net))
                        self._subnets.append(net)
                    if name_l and str(net) not in {str(n) for n in self._dev_nets[name_l]}:
                        self._dev_nets[name_l].append(net)
            for v6 in dev.get('ipv6', []):
                bare6 = v6.split('/')[0]
                self._exact_ips.add(bare6)
                if name_l:
                    self._dev_exact[name_l].add(bare6)
                if '/' in v6:
                    try:
                        net6 = ipaddress.ip_network(v6, strict=False)
                    except ValueError:
                        continue
                    if str(net6) not in {str(n) for n in self._subnets6}:
                        self._subnets6.append(net6)
                    if name_l and str(net6) not in {str(n) for n in self._dev_nets[name_l]}:
                        self._dev_nets[name_l].append(net6)

    def _build_routes(self, doc: dict) -> None:
        raw = doc.get('routes')
        if raw is None:
            return
        if not isinstance(raw, list):
            self._routes_uninterpretable = True
            logger.warning('拓扑 routes 字段存在但不是数组——驱动侧路径判据降级放行(防误杀)。')
            return
        for entry in raw:
            try:
                dev_l = str(entry['device']).strip().lower()
                net = ipaddress.ip_network(str(entry['destination']), strict=False)
            except Exception:
                self._routes_uninterpretable = True
                logger.warning('拓扑 routes 条目无法按最小 schema {device,destination} 解析:%r——驱动侧路径判据降级放行(防误杀)。', entry)
                return
            if dev_l:
                self._routes.append((dev_l, net))

    def is_reachable(self, ip: str) -> bool:
        bare = (ip or '').split('/')[0].strip()
        if bare in self._exact_ips:
            return True
        try:
            addr = ipaddress.IPv4Address(bare)
        except ValueError:
            return False
        return any((addr in net for net in self._subnets))

    def unreachable_ipv4s(self, text: str) -> list[str]:
        out: list[str] = []
        previous_was_ip = False
        previous_end = -1
        for m in _IPV4_RE.finditer(text or ''):
            ip = m.group(1)
            adjacent = previous_was_ip and (not (text or '')[previous_end:m.start()].strip(' \t/,'))
            previous_was_ip, previous_end = (True, m.end())
            if ip in _NON_HOST_IPV4S:
                continue
            if adjacent and _is_contiguous_netmask(ip):
                continue
            if ip not in out and (not self.is_reachable(ip)):
                out.append(ip)
        return out

    def _iter_ipv6_literals(self, text: str):
        for m in _IPV6_TOKEN_RE.finditer(text or ''):
            tok = m.group(0).strip('[]')
            if tok.count(':') < 2:
                continue
            tok = tok.split('%')[0]
            for cand in (tok, tok.rstrip('.'), tok.rstrip('.').rstrip(':')):
                if cand.count(':') < 2:
                    break
                try:
                    addr = ipaddress.IPv6Address(cand)
                except ValueError:
                    continue
                yield (cand, addr)
                break

    def unreachable_ipv6s(self, text: str) -> list[str]:
        out: list[str] = []
        for lit, addr in self._iter_ipv6_literals(text):
            if int(addr) == 0:
                continue
            bare = str(addr)
            if lit in self._exact_ips or bare in self._exact_ips:
                continue
            if any((addr in net for net in self._subnets6)):
                continue
            if lit not in out:
                out.append(lit)
        return out

    def service_ips(self) -> list[str]:
        out: list[str] = []
        for dev in self.devices:
            if any((t in dev.get('type', '') for t in _SERVER_TYPES)):
                for cidr in dev.get('ipv4', []):
                    bare = cidr.split('/')[0]
                    if bare not in out:
                        out.append(bare)
        return out

    def reachable_subnets(self) -> list[str]:
        return [str(n) for n in self._subnets]

    def infra_ips(self) -> frozenset[str]:
        out: set[str] = set()
        for ip in self._exact_ips:
            try:
                ipaddress.IPv4Address(ip)
                out.add(ip)
            except ValueError:
                continue
        return frozenset(out)

    def _types_per_subnet(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {str(n): set() for n in self._subnets}
        for dev in self.devices:
            t = dev.get('type', '')
            for cidr in dev.get('ipv4', []):
                try:
                    addr = ipaddress.IPv4Address(cidr.split('/')[0])
                except ValueError:
                    continue
                for net in self._subnets:
                    if addr in net:
                        out[str(net)].add(t)
        return out

    def _lb_ips_with_subnet(self) -> list[tuple[str, ipaddress.IPv4Network]]:
        out: list[tuple[str, ipaddress.IPv4Network]] = []
        for dev in self.devices:
            if not any((t in dev.get('type', '') for t in _LB_TYPES)):
                continue
            for cidr in dev.get('ipv4', []):
                try:
                    addr = ipaddress.IPv4Address(cidr.split('/')[0])
                except ValueError:
                    continue
                for net in self._subnets:
                    if addr in net:
                        out.append((str(addr), net))
                        break
        return out

    def listener_ips(self) -> list[str]:
        types = self._types_per_subnet()
        out: list[str] = []
        for ip, net in self._lb_ips_with_subnet():
            present = types.get(str(net), set())
            if any((any((tt in p for tt in _TRIGGER_TYPES)) for p in present)):
                if ip not in out:
                    out.append(ip)
        return out

    def unreachable_lb_ips(self) -> list[str]:
        types = self._types_per_subnet()
        out: list[str] = []
        for ip, net in self._lb_ips_with_subnet():
            present = types.get(str(net), set())
            if not any((any((tt in p for tt in _TRIGGER_TYPES)) for p in present)):
                if ip not in out:
                    out.append(ip)
        return out

    def listener_trigger_pairs(self) -> list[tuple[str, list[str]]]:
        out: list[tuple[str, list[str]]] = []
        seen: set[str] = set()
        for lb in self.devices:
            if not any((t in lb.get('type', '') for t in _LB_TYPES)):
                continue
            for cidr in list(lb.get('ipv4') or []) + list(lb.get('ipv6') or []):
                bare = str(cidr).split('/')[0].strip()
                if not bare or bare in seen:
                    continue
                try:
                    addr = ipaddress.ip_address(bare)
                except ValueError:
                    continue
                trig: list[str] = []
                for dev in self.devices:
                    if not any((t in dev.get('type', '') for t in _TRIGGER_TYPES)):
                        continue
                    name = str(dev.get('name', '')).strip().lower()
                    if not name:
                        continue
                    nets = self._dev_nets.get(name, [])
                    if any((addr.version == net.version and addr in net for net in nets)) and name not in trig:
                        trig.append(name)
                if trig:
                    seen.add(bare)
                    out.append((bare, trig))
        return out

    def _resolve_device_key(self, name: str) -> str:
        raw = str(name or '').strip().lower()
        if not raw:
            return ''
        if raw in self._dev_exact:
            return raw
        folded = re.sub('[^a-z0-9]', '', raw)
        candidates = [item for item in self._dev_exact if re.sub('[^a-z0-9]', '', item) == folded]
        return candidates[0] if len(candidates) == 1 else ''

    def device_carried_addresses(self, name: str) -> list[str]:
        key = self._resolve_device_key(name)
        return sorted(self._dev_exact.get(key, ())) if key else []

    def device_interface_addresses(self, name: str) -> dict[str, list]:
        key = self._resolve_device_key(name)
        out: dict[str, list] = {}
        for iface, addresses in (self._dev_ifaces.get(key) or {}).items():
            parsed = []
            for cidr in addresses:
                try:
                    parsed.append(ipaddress.ip_interface(cidr))
                except ValueError:
                    continue
            if parsed:
                out[iface] = parsed
        return out

    def carried_address_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for key in sorted(self._dev_exact):
            addresses = sorted(self._dev_exact.get(key, ()))
            if addresses:
                rows.append({'device': self._display_name.get(key, key), 'addresses': addresses})
        return rows

    def is_driver_device(self, name: str) -> bool:
        return str(name or '').strip().lower() in self._driver_names

    def device_declared_networks(self, name: str) -> list[str]:
        return [str(n) for n in self._dev_nets.get(str(name or '').strip().lower(), [])]

    def executor_path_verdict(self, executor: str, dest_ip: str) -> dict | None:
        name = str(executor or '').strip().lower()
        if not name:
            return None
        bare = str(dest_ip or '').split('/')[0].split('%')[0].strip().strip('[]')
        try:
            addr = ipaddress.ip_address(bare)
        except ValueError:
            return None
        if bare in _NON_HOST_IPV4S or int(addr) == 0:
            return None
        if bare in self._dev_exact.get(name, ()):
            return None
        if self._routes_uninterpretable:
            return None
        nets = self._dev_nets.get(name, [])
        if not nets:
            return {'executor': self._display_name.get(name, executor), 'executor_networks': [], 'dest': bare, 'dest_segments': self._segments_of(addr), 'reachable_drivers': self._drivers_reaching(addr), 'networks_undeclared': True}
        for net in nets:
            if addr.version == net.version and addr in net:
                return None
        for dev_l, net in self._routes:
            if dev_l == name and addr.version == net.version and (addr in net):
                return None
        return {'executor': self._display_name.get(name, executor), 'executor_networks': self.device_declared_networks(name), 'dest': bare, 'dest_segments': self._segments_of(addr), 'reachable_drivers': self._drivers_reaching(addr)}

    def _segments_of(self, addr) -> list[str]:
        dest_segments: list[str] = []
        for dev in self.devices:
            for cidr in list(dev.get('ipv4', [])) + list(dev.get('ipv6', [])):
                if '/' not in cidr:
                    continue
                try:
                    net = ipaddress.ip_network(cidr, strict=False)
                except ValueError:
                    continue
                if addr.version == net.version and addr in net and (str(net) not in dest_segments):
                    dest_segments.append(str(net))
        return dest_segments

    def _drivers_reaching(self, addr) -> list[str]:
        return sorted((self._display_name.get(dl, dl) for dl in self._driver_names if any((addr.version == n.version and addr in n for n in self._dev_nets.get(dl, [])))))

    def driver_path_verdict(self, executor: str, dest_ip: str) -> dict | None:
        name = str(executor or '').strip().lower()
        if name not in self._driver_names:
            return None
        return self.executor_path_verdict(name, dest_ip)

    def service_ips6(self) -> list[str]:
        out: list[str] = []
        for dev in self.devices:
            if any((t in dev.get('type', '') for t in _SERVER_TYPES)):
                for v6 in dev.get('ipv6', []):
                    bare6 = v6.split('/')[0]
                    if bare6 not in out:
                        out.append(bare6)
        return out

    def listener_ips6(self) -> list[str]:
        driver_v6 = [n for dl in self._driver_names for n in self._dev_nets.get(dl, []) if n.version == 6]
        out: list[str] = []
        for dev in self.devices:
            if not any((t in dev.get('type', '') for t in _LB_TYPES)):
                continue
            for v6 in dev.get('ipv6', []):
                bare6 = v6.split('/')[0]
                try:
                    addr = ipaddress.ip_address(bare6)
                except ValueError:
                    continue
                if any((addr in n for n in driver_v6)) and bare6 not in out:
                    out.append(bare6)
        return out

    def v6_lb_ips_without_driver_prefix(self) -> list[str]:
        driver_v6 = [n for dl in self._driver_names for n in self._dev_nets.get(dl, []) if n.version == 6]
        out: list[str] = []
        for dev in self.devices:
            if not any((t in dev.get('type', '') for t in _LB_TYPES)):
                continue
            for v6 in dev.get('ipv6', []):
                bare6 = v6.split('/')[0]
                try:
                    addr = ipaddress.ip_address(bare6)
                except ValueError:
                    continue
                if not any((addr in n for n in driver_v6)) and bare6 not in out:
                    out.append(bare6)
        return out

    def summary_for_agent(self) -> str:
        listener = self.listener_ips()
        listener6 = self.listener_ips6()
        shown_listener = list(listener) + [ip for ip in listener6 if ip not in listener]
        blind = self.unreachable_lb_ips()
        lines = ['=== 本测试床网络事实源(写 IP 只能用这里的真实可达值)===']
        lines.append(f"可达子网(IP 必须落在其中之一): {', '.join(self.reachable_subnets())}")
        lines.append(f"后端服务器真实 IP(service/pool 后端用): {', '.join(self.service_ips())}")
        if shown_listener:
            lines.append('★ 复用现有接口作 listener/VIP 时,用这些 APV 接口 IP(触发设备 dig/curl 够得着的网段): ' + ', '.join(shown_listener))
            lines.append('  若用例要测**新建接口类型**(VLAN 子接口、新网段 listener 等):事实源只记录了上述预置接口,未记录新建接口的连通性(VLAN trunk/触发机对接)——猜一个新 IP 大概率上机不解析。这属数据缺口,用 compile_report_underdetermined 如实呈报(obstacle=事实源缺该接口类型的拓扑/连通数据),不要猜 IP 硬编。')
        carried = self.carried_address_rows()
        if carried:
            lines.append('Exact carried-address inventory by target device (topology evidence for authoring, not a parameter-role verdict or expected-value signer; determine the endpoint role from the case intent and versioned parameter/manual text):')
            for row in carried:
                lines.append(f"  {row['device']}: {', '.join((str(x) for x in row['addresses']))}")
        pairs = self.listener_trigger_pairs()
        if pairs:
            lines.append("★ 触发机配对(dig/curl 必须从**与目标 listener 同段**的触发机发起,否则上机 'no servers could be reached'、断言全 fail):")
            for ip, trig in pairs:
                lines.append(f"    dig/curl 目标 {ip} → 必须用 test_env 主机 {' 或 '.join(trig)}")
        if blind:
            lines.append('注意：这些 APV 接口 IP 禁止配 listener/VIP(所在网段没有路由器/客户端,dig/curl 源够不着,上机必不解析): ' + ', '.join(blind))
        blind_v6 = self.v6_lb_ips_without_driver_prefix()
        if blind_v6:
            lines.append('注意：这些被测设备 IPv6 接口地址与**任何**触发设备(路由器/客户端)都不共享声明前缀——dig/curl 从驱动侧发起必然无路、上机空返回,禁止选作触发目标: ' + ', '.join(blind_v6))
        lines.append('设备清单:')
        for dev in self.devices:
            ips = ', '.join(dev.get('ipv4', []))
            v6s = ', '.join(dev.get('ipv6', []))
            line = f"  {dev.get('name')} [{dev.get('type')}]: {ips}"
            if v6s:
                line += f'; IPv6: {v6s}'
            lines.append(line)
        lines.append('选址规则:listener/VIP 的 IP、以及 check 步骤里 dig/curl 的目标 IP 必须一致且来自上面的 ★ 列表;后端用服务器真实 IP。**dig/curl 步骤的 test_env 主机(F 列)必须按上面「★ 触发机配对」选,且用小写**——目标 IP 在哪段就用哪台同段触发机(如 .32 段用 routerb、.34 段用 routera);框架按方法名精确分派(不转小写),写成 routerB 大写会 AttributeError、dig 不执行。选错段必不解析。')
        lines.append('禁止裸用 1.1.1.1/2.2.2.2/10.x/192.168.x 等示例 IP——它们不可达,上机 dig 必失败。')
        return '\n'.join(lines)

class EnvFactsUnavailable(RuntimeError):
    """床事实读不到。取不到 ≠ 确认可达，不能折叠成放行。"""

@functools.lru_cache(maxsize=1)
def get_env_facts() -> EnvFacts:
    """进程级缓存的原始读法。文件缺席/坏掉时返回空事实源。

    拓扑是生成物（`scripts/gen_network_topology.py`，随环境收敛重写）而非入库
    资产。**判据一律走 `require_env_facts()`**：空 devices 不是「这张床上什么
    都没有」，是「还没收敛过」，折叠成放行就等于把「不知道」签成「没问题」。
    这个函数只给 `require_env_facts()` 和收敛入口（写完要 `cache_clear()`
    再复核）用。
    """
    if not _TOPOLOGY_JSON.exists():
        logger.warning('env facts JSON 不存在: %s;判据入口会抛 EnvFactsUnavailable。', _TOPOLOGY_JSON)
        return EnvFacts({'devices': []})
    try:
        doc = json.loads(_TOPOLOGY_JSON.read_text(encoding='utf-8'))
    except Exception as exc:
        logger.warning('env facts JSON 解析失败: %s;判据入口会抛 EnvFactsUnavailable。', exc)
        return EnvFacts({'devices': []})
    return EnvFacts(doc)

def require_env_facts() -> EnvFacts:
    """读不到就抛，不把「没有事实」折叠成「可达」。

    批内这条永远抛不出来：`environment_prepare._converge_network_topology()`
    在开批时重探拓扑、写完立刻 `cache_clear()` + 本函数复核，读不成事实即
    `CompileEnvironmentPrepareError(network_topology_unavailable)`，批起不来。
    留着它是为了让批外直调（CLI、脚本、IDE 校验器）也够不到宽松放行；真抛出来
    时经 `middleware.tool_error_boundary` 变成一条工具故障回执。
    """
    facts = get_env_facts()
    if not facts.devices:
        raise EnvFactsUnavailable(f'床事实不可用（{_TOPOLOGY_JSON.name}）；它由环境收敛生成，先跑一次入口')
    return facts

def is_reachable(ip: str) -> bool:
    """没有拓扑事实不得当成可达——取不到就抛，不折叠成 True。"""
    return require_env_facts().is_reachable(ip)
