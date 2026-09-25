# 生成：tools/extract_engine.py ← InfoTest scripts/gen_network_topology.py（sha256 7f2038fadc341ed4）。不在这里手改。
"""从跳板机现探生成 network_topology.json 与 network_topology_rag.md。

两份产物整份覆盖重写；探不到的设备由**声明适用于当前床**的
topology_overlay.json 补。仓里那份地址不是新床填完 environment 就能继承的
通用 overlay。口径见 .claude/rules/knowledge-kms.md「自动化环境拓扑」。
"""
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import argparse
import configparser
import ipaddress
import json
import logging
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
logger = logging.getLogger(__name__)
_ROOT = _cex_data_path('')
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AUTO_ENV = _ROOT / 'knowledge' / 'data' / 'auto_env'
_JSON_OUT = _AUTO_ENV / 'network_topology.json'
_RAG_OUT = _AUTO_ENV / 'network_topology_rag.md'
_OVERLAY = _AUTO_ENV / 'topology_overlay.json'
_REGENERATED_WARNING = '手改会被下一次环境收敛冲掉'
_OBSERVATION_OUT = _ROOT / 'runtime' / 'network_topology_observation.json'
_NAME_STYLE: dict[str, str] = {'clientc': 'clientC', 'clientd': 'clientD', 'cliente': 'clientE', 'routera': 'routerA', 'routerb': 'routerB'}
_TYPE_BY_PREFIX: tuple[tuple[str, str], ...] = (('client', '客户端'), ('router', '路由器'), ('APV', '负载均衡'), ('server', '服务器'), ('console', '控制台'))
_IP_OADDR_RE = re.compile('^\\d+:\\s+(?P<iface>\\S+)\\s+(?P<family>inet6?)\\s+(?P<cidr>\\S+)')
_ARP_RE = re.compile('\\((?P<ip>[\\d.]+)\\)\\s+at\\s+(?P<mac>\\S+).*?\\son\\s+(?P<iface>\\S+)')
_SUBNET_RE = re.compile('^(?P<a>\\d+)\\.(?P<b>\\d+)\\.(?P<c>\\d+)\\.(?P<d>\\d+)/(?P<mask>\\d+)$')

class TopologyProbeError(RuntimeError):
    """探测拿不到足以重写产物的事实时抛出——宁可不写，也不写半份。"""

class BedHostKeyMismatch(RuntimeError):
    """床内主机的密钥与已钉扎的不一致：**安全信号**，不是「机器没开机」。

    单立一类是为了让 `probe_hosts` 分得开——两种现场此前都只剩一句
    「探测 X 失败：<异常类名>」，机器没开机与「有别的东西在那个地址上应答、
    引擎拒绝把框架共享口令递过去」在用户面完全同形。
    """

def derive_conf_name(ip_addr_text: str, override: str='') -> str:
    """显式覆盖优先，否则取跳板机自身 10.4.* 地址的末段。

    同规则另有两份实现部署在跳板机上（device_mcp_client 内嵌脚本、
    device_mcp_server/tools.py），无法 import 本模块，靠守门测试比对防分叉。
    """
    value = (override or '').strip()
    if value:
        if not re.fullmatch('[A-Za-z0-9._-]+', value):
            raise TopologyProbeError('conf 名只允许字母数字与 . _ -')
        return value if value.endswith('.conf') else f'{value}.conf'
    match = re.search('10\\.4\\.\\d+\\.(\\d+)/\\d+', ip_addr_text or '')
    if not match:
        raise TopologyProbeError('跳板机上没有 10.4.* 地址，推不出 conf 名——显式配 IST_JUMPHOST_CONF_NAME')
    return f'{match.group(1)}.conf'

@dataclass(frozen=True)
class ConfFacts:
    """conf 里与拓扑有关的那几项。"""
    hosts: dict[str, str]
    device_ips: tuple[str, ...]
    device_names: tuple[str, ...]
    mysql_ip: str

def parse_conf(text: str) -> ConfFacts:
    """解析跳板机 conf。strict=False 因为 conf 有重复键。

    interpolation=None 不能去掉：开着插值 `marks=exec%%APV0,APV1` 会被读成
    `exec%APV0,APV1`，设备名少一截。
    """
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.read_string(text)
    hosts: dict[str, str] = {}
    dropped = 0
    if parser.has_section('env'):
        for key, value in parser.items('env'):
            ip = (value or '').strip()
            if not ip:
                continue
            try:
                ipaddress.ip_address(ip.split('/', 1)[0])
            except ValueError:
                dropped += 1
                continue
            hosts[key.strip()] = ip
    if dropped:
        logger.warning('conf [env] 丢弃 %d 条非 IP 取值（不回显值）', dropped)
    device_ips: tuple[str, ...] = ()
    if parser.has_option('comm', 'ssh_ips'):
        device_ips = tuple((ip.strip() for ip in parser.get('comm', 'ssh_ips').split(',') if ip.strip()))
    device_names: tuple[str, ...] = ()
    if parser.has_option('comm', 'marks'):
        raw = parser.get('comm', 'marks')
        tail = raw.split('%%', 1)[1] if '%%' in raw else raw
        device_names = tuple((n.strip() for n in tail.split(',') if n.strip()))
    mysql_ip = ''
    if parser.has_option('other', 'mysql_ip'):
        mysql_ip = parser.get('other', 'mysql_ip').strip()
    return ConfFacts(hosts, device_ips, device_names, mysql_ip)

@dataclass(frozen=True)
class Address:
    iface: str
    family: str
    cidr: str

def parse_ip_addr(text: str) -> tuple[Address, ...]:
    """解析 `ip -o addr show` 的原始输出。

    不解析 awk 预处理过的窄格式——那样生成器就与某条命令行绑死了。
    """
    out: list[Address] = []
    for line in (text or '').splitlines():
        match = _IP_OADDR_RE.match(line.strip())
        if not match:
            continue
        iface = match.group('iface')
        if iface == 'lo':
            continue
        out.append(Address(iface, match.group('family'), match.group('cidr')))
    return tuple(out)

def parse_arp(text: str) -> tuple[tuple[str, str], ...]:
    """解析 `arp -an`，返回 (物理口, 邻居 IPv4)；`<incomplete>` 不算邻居。"""
    out: list[tuple[str, str]] = []
    for line in (text or '').splitlines():
        match = _ARP_RE.search(line)
        if not match:
            continue
        if 'incomplete' in match.group('mac'):
            continue
        out.append((match.group('iface'), match.group('ip')))
    return tuple(out)

def _subnet_of(cidr: str) -> str:
    """`172.16.33.215/24` → `172.16.33.0/24`；解析不了就原样回。"""
    match = _SUBNET_RE.match(cidr)
    if not match:
        return cidr
    mask = int(match.group('mask'))
    if mask != 24:
        return f"{match.group('a')}.{match.group('b')}.{match.group('c')}.0/{mask}"
    return f"{match.group('a')}.{match.group('b')}.{match.group('c')}.0/24"

def _third_octet(cidr: str) -> str:
    match = _SUBNET_RE.match(cidr)
    return match.group('c') if match else ''

@dataclass
class L2Domain:
    """一个二层域：跳板机的一个物理口所在的那个广播域。"""
    iface: str
    subnets: list[str] = field(default_factory=list)
    members: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        """按网段号命名：net33 ← 172.16.33.0/24；一个口挂多段就并起来。"""
        octets = [o for o in (_third_octet(s) for s in self.subnets) if o]
        if not octets:
            return f'net-{self.iface}'
        return 'net' + '/'.join(octets)

def group_l2_domains(addresses: Sequence[Address], neighbors: Sequence[tuple[str, str]]=()) -> tuple[L2Domain, ...]:
    """按跳板机物理口归并出二层域；管理网 10.4/16 不算床内域。

    只吃跳板机自身的接口地址——这些由床的编址决定、跑批之间不抖。
    `neighbors` 保留参数位但不进域成员：ARP 条目会老化，让它参与就等于每批
    重写一次入密封轴的文件（config_binding_inputs），同名续跑会被自己写的
    产物判成上下文漂移、整批归档重编。成员由 `assign_domain_members` 从已知
    设备推导。
    """
    domains: dict[str, L2Domain] = {}
    for addr in addresses:
        if addr.family != 'inet' or addr.cidr.startswith('10.4.'):
            continue
        domain = domains.setdefault(addr.iface, L2Domain(addr.iface))
        subnet = _subnet_of(addr.cidr)
        if subnet not in domain.subnets:
            domain.subnets.append(subnet)
    for domain in domains.values():
        domain.subnets.sort()
    return tuple(sorted(domains.values(), key=lambda d: d.subnets[:1] or [d.iface]))

def assign_domain_members(domains: Sequence[L2Domain], devices: Sequence[Mapping[str, Any]]) -> None:
    """二层域成员 = 地址落在该域子网里的已知设备名。

    取设备名而不是 ARP 见过的裸 IP：前者由 conf 与各机自述决定，后者随邻居
    老化抖动。
    """
    prefixes = {domain.iface: tuple((s.rsplit('.', 2)[0] + '.' for s in domain.subnets)) for domain in domains}
    for domain in domains:
        seen: list[str] = []
        for device in devices:
            name = str(device.get('name') or '')
            if not name:
                continue
            for cidr in device.get('ipv4') or ():
                if str(cidr).startswith(prefixes[domain.iface]) and name not in seen:
                    seen.append(name)
                    break
        domain.members = sorted(seen)

def unregistered_neighbours(domains: Sequence[L2Domain], neighbors: Sequence[tuple[str, str]], devices: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    """ARP 上有、但拓扑里没有对应设备的地址。只作观察，不入密封轴。"""
    known = {str(cidr).split('/', 1)[0] for device in devices for cidr in device.get('ipv4') or ()}
    by_iface = {domain.iface for domain in domains}
    out: dict[str, list[str]] = {}
    for iface, ip in neighbors:
        if iface not in by_iface or ip in known:
            continue
        out.setdefault(iface, []).append(ip)
    return {k: sorted(v, key=_ip_sort_key) for k, v in out.items()}

def _ip_sort_key(ip: str) -> tuple[int, ...]:
    try:
        return tuple((int(p) for p in ip.split('.')))
    except ValueError:
        return (0,)

def canonical_device_name(conf_key: str) -> str:
    """conf 的 key → 拓扑设备名。表里没有的原样保留，不猜。"""
    key = (conf_key or '').strip()
    return _NAME_STYLE.get(key.lower(), key)

def device_type(name: str) -> str:
    for prefix, label in _TYPE_BY_PREFIX:
        if name.lower().startswith(prefix.lower()):
            return label
    return '未分类'
_MANAGEMENT_PREFIX = '10.4.'

def _is_management(cidr: str) -> bool:
    """管理网不是床内业务网——它进 ipv4 列表会污染可达性判据。"""
    return cidr.startswith(_MANAGEMENT_PREFIX)

def _bare_ip(value: object) -> str:
    return str(value or '').strip().split('%', 1)[0].split('/', 1)[0]

def overlay_ssh_ips(overlay: Mapping[str, Any] | None) -> frozenset[str] | None:
    """读 overlay 声明的适用床。未声明返回 None，不是空集。"""
    if not overlay:
        return None
    applies = overlay.get('applies_to')
    if not isinstance(applies, dict):
        return None
    raw = applies.get('device_ssh_ips')
    if not isinstance(raw, list) or not raw:
        return None
    ips = frozenset((_bare_ip(item) for item in raw if str(item).strip()))
    return ips or None

def overlay_for_conf(overlay: Mapping[str, Any] | None, conf: ConfFacts) -> dict[str, Any]:
    """只把声明适用于当前 conf ssh_ips 的 overlay 交给合成。

    仓里那份写的是某一床的 APV 地址，不是新床填完 environment 就能继承的
    通用事实。有设备条目却没声明适用床 → 抛，避免再变回静默通用 overlay。
    声明了但对不上当前 conf → 整份不用，退回 previous / conf。
    """
    if not overlay:
        return {}
    devices = overlay.get('devices')
    if not isinstance(devices, list) or not devices:
        return {}
    declared = overlay_ssh_ips(overlay)
    if declared is None:
        raise TopologyProbeError('topology_overlay.json 有设备条目但未声明 applies_to.device_ssh_ips——未绑定的 overlay 不能当通用床事实')
    current = frozenset((_bare_ip(ip) for ip in conf.device_ips if str(ip).strip()))
    if not current or current != declared:
        logger.warning('topology_overlay.json 声明适用于 %s，当前 conf ssh_ips 是 %s，整份忽略', sorted(declared), sorted(current))
        return {}
    return dict(overlay)

def entry_covers_management_ip(entry: Mapping[str, Any], mgmt_ip: str) -> bool:
    """上一轮/overlay 条目必须仍覆盖当前管理地址，才能沿用接口映射。"""
    bare = _bare_ip(mgmt_ip)
    if not bare:
        return False
    for cidr in list(entry.get('ipv4') or []) + list(entry.get('ipv6') or []):
        if _bare_ip(cidr) == bare:
            return True
    return False

def build_topology(*, conf: ConfFacts, jumphost_addresses: Sequence[Address], domains: Sequence[L2Domain], host_addresses: Mapping[str, Sequence[Address]], overlay: Mapping[str, Any] | None=None, previous: Mapping[str, Any] | None=None) -> dict[str, Any]:
    """合成 network_topology.json 的形状。

    取值顺序：本轮探到 > 绑定到本床的 overlay > 仍覆盖当前管理地址的 previous
    > conf 管理地址。探不到的不能退化成空条目——APV 是 CLI 设备永远探不到，
    抹掉就丢了实测的接口映射；但也不得把另一床的 APV 地址写进来。
    """
    devices: list[dict[str, Any]] = []
    unprobed: list[str] = []
    bound_overlay = overlay_for_conf(overlay, conf)
    prior = {str(d.get('name')): d for d in (previous or {}).get('devices', []) if isinstance(d, dict) and d.get('name')}
    declared = {str(d.get('name')): d for d in bound_overlay.get('devices', []) if isinstance(d, dict) and d.get('name')}

    def _fallback(name: str, mgmt_ip: str) -> dict[str, Any]:
        """绑定 overlay > 仍覆盖本机管理地址的 previous > conf 管理地址。"""
        for source in (declared, prior):
            kept = source.get(name)
            if kept and entry_covers_management_ip(kept, mgmt_ip):
                entry = {k: v for k, v in kept.items() if not k.startswith('_')}
                entry.setdefault('type', device_type(name))
                return entry
        entry = {'name': name, 'type': device_type(name), 'ipv4': [mgmt_ip if '/' in mgmt_ip else f'{mgmt_ip}/24'], 'ipv6': []}
        if '/' not in mgmt_ip:
            entry['_mask_assumed'] = True
        return entry
    for conf_key, mgmt_ip in sorted(conf.hosts.items()):
        name = canonical_device_name(conf_key)
        probed = host_addresses.get(conf_key) or host_addresses.get(name)
        entry: dict[str, Any] = {'name': name, 'type': device_type(name)}
        if probed:
            entry['ipv4'] = [a.cidr for a in probed if a.family == 'inet' and (not _is_management(a.cidr))]
            entry['ipv6'] = [a.cidr for a in probed if a.family == 'inet6' and (not a.cidr.lower().startswith('fe80:'))]
            entry['interfaces'] = {}
            for a in probed:
                if a.family == 'inet' and _is_management(a.cidr):
                    continue
                slot = entry['interfaces'].setdefault(a.iface, {})
                if a.family == 'inet':
                    slot['ipv4'] = a.cidr
                elif not a.cidr.lower().startswith('fe80:'):
                    slot['ipv6'] = a.cidr
            devices.append(entry)
        else:
            devices.append(_fallback(name, mgmt_ip))
            unprobed.append(name)
    for index, ip in enumerate(conf.device_ips):
        name = conf.device_names[index] if index < len(conf.device_names) else f'APV{index}'
        probed = host_addresses.get(name)
        if probed:
            entry = {'name': name, 'type': '负载均衡'}
            entry['ipv4'] = [a.cidr for a in probed if a.family == 'inet' and (not _is_management(a.cidr))]
            entry['ipv6'] = [a.cidr for a in probed if a.family == 'inet6' and (not a.cidr.lower().startswith('fe80:'))]
            entry['interfaces'] = {}
            for a in probed:
                if a.family == 'inet' and _is_management(a.cidr):
                    continue
                slot = entry['interfaces'].setdefault(a.iface, {})
                if a.family == 'inet':
                    slot['ipv4'] = a.cidr
                elif not a.cidr.lower().startswith('fe80:'):
                    slot['ipv6'] = a.cidr
            devices.append(entry)
        else:
            devices.append(_fallback(name, ip))
            unprobed.append(name)
    known = {d['name'] for d in devices}
    for extra in bound_overlay.get('devices', []):
        if isinstance(extra, dict) and extra.get('name') not in known:
            devices.append(dict(extra))
    payload: dict[str, Any] = {'_comment': f'网络拓扑事实源(权威JSON)。可达性判据=IP落在任一设备子网内或精确等于某设备IP。**本文件由 scripts/gen_network_topology.py 整份重写，{_REGENERATED_WARNING}**——要改内容改生成器或 topology_overlay.json。', '_provenance': '跳板机 conf [env]/[comm] + ip -o addr + arp -an，并经跳板机一跳 ssh 取各机自述接口', '_l2_domains': [{'name': d.name, 'jumphost_iface': d.iface, 'subnets': list(d.subnets), 'members': list(d.members)} for d in domains], 'devices': devices}
    if conf.mysql_ip:
        payload['_result_channel_mysql_ip'] = conf.mysql_ip
    payload['_unprobed_this_run'] = sorted(unprobed)
    return payload

def render_rag_md(topology: Mapping[str, Any]) -> str:
    """渲染散文版。device-verify skill 逐字读它取设备地址。"""
    devices = list(topology.get('devices') or [])
    domains = list(topology.get('_l2_domains') or [])
    lines: list[str] = ['# 网络拓扑结构文档', '', '> 本文件由 `scripts/gen_network_topology.py` 从跳板机现探整份重写。', f'> {_REGENERATED_WARNING}；要改内容改生成器，或把探不到的事实写进', '> `knowledge/data/auto_env/topology_overlay.json`。', '', f'共 {len(devices)} 台设备，{len(domains)} 个二层域。', '', '---', '', '## 一、设备与地址', '', '| 设备名称 | 类型 | IPv4 | IPv6 |', '|---------|------|------|------|']
    for dev in devices:
        v4 = '<br>'.join(dev.get('ipv4') or []) or '—'
        v6 = '<br>'.join(dev.get('ipv6') or []) or '—'
        lines.append(f"| {dev.get('name')} | {dev.get('type', '')} | {v4} | {v6} |")
    lines += ['', '## 二、接口名 ↔ 地址', '']
    any_iface = False
    for dev in devices:
        ifaces = dev.get('interfaces') or {}
        if not ifaces:
            continue
        any_iface = True
        lines.append(f"### {dev.get('name')}")
        lines.append('')
        lines.append('| 接口 | IPv4 | IPv6 |')
        lines.append('|------|------|------|')
        for iface, slot in sorted(ifaces.items()):
            lines.append(f"| {iface} | {slot.get('ipv4', '—')} | {slot.get('ipv6', '—')} |")
        lines.append('')
    if not any_iface:
        lines += ['（本轮没有取到任何设备的逐接口自述。）', '']
    else:
        lines += ['写 `ip address <接口名> …` 这类要接口名的命令时取这张表。**不要**按上面', 'IPv4/IPv6 列表的顺序去猜——两者不对应，实测有过 port1↔port3 相反的情况。', '']
    lines += ['## 三、二层域（谁和谁在同一个广播域）', '']
    if domains:
        lines += ['| 域 | 跳板机物理口 | 网段 | 成员 |', '|----|-------------|------|------|']
        for dom in domains:
            members = '、'.join(dom.get('members') or []) or '—'
            subnets = '<br>'.join(dom.get('subnets') or []) or '—'
            lines.append(f"| {dom.get('name')} | {dom.get('jumphost_iface')} | {subnets} | {members} |")
        lines += ['', '域名按网段号机械生成。交换机本身是二层设备、没有管理 IP，在本床还是', 'VMware 虚拟交换机（邻居 MAC 全为 VMware OUI、各网段 `.1` 无应答），', '它在虚拟化层叫什么从客户机侧探不到——但那只是标签，判据读的是成员与网段。', '']
    else:
        lines += ['（本轮没有取到二层域分组。）', '']
    return '\n'.join(lines).rstrip() + '\n'
_HOST_PROBE_CMD = 'ip -o addr show 2>/dev/null || ifconfig -a'
_REMOTE_READ_MAX = 4 * 1024 * 1024

def _exec(client: Any, command: str, timeout: int=30) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read(_REMOTE_READ_MAX).decode('utf-8', 'replace')
    err = stderr.read(_REMOTE_READ_MAX).decode('utf-8', 'replace')
    return out + err

def probe_jumphost(client: Any, *, apv_src: str, conf_override: str='') -> tuple[ConfFacts, tuple[Address, ...], tuple[tuple[str, str], ...]]:
    """取跳板机那三样：conf、自身接口、ARP 邻居。"""
    ip_text = _exec(client, 'ip -o addr show')
    conf_name = derive_conf_name(ip_text, conf_override)
    conf_text = _exec(client, 'cat ' + shlex.quote(f'{apv_src}/conf/{conf_name}'))
    if '[env]' not in conf_text and '[comm]' not in conf_text:
        raise TopologyProbeError(f'跳板机 conf/{conf_name} 读不到或不含 [env]/[comm] 段')
    arp_text = _exec(client, 'arp -an')
    return (parse_conf(conf_text), parse_ip_addr(ip_text), parse_arp(arp_text))
_HOST_KEY_PINS = _ROOT / 'runtime' / 'bed_host_key_pins.json'

def _load_pins() -> dict[str, str]:
    try:
        payload = json.loads(_HOST_KEY_PINS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in payload.items()} if isinstance(payload, dict) else {}

def _save_pins(pins: Mapping[str, str]) -> None:
    _HOST_KEY_PINS.parent.mkdir(parents=True, exist_ok=True)
    _HOST_KEY_PINS.write_text(json.dumps(dict(sorted(pins.items())), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

class _PinningPolicy:
    """首轮记录、之后比对。密钥变了抛，不把口令递过去。"""

    def __init__(self, pins: dict[str, str], ip: str) -> None:
        self._pins = pins
        self._ip = ip
        self.recorded = False

    def missing_host_key(self, _client: Any, _hostname: str, key: Any) -> None:
        import hashlib
        digest = hashlib.sha256(key.asbytes()).hexdigest()
        known = self._pins.get(self._ip)
        if known is None:
            self._pins[self._ip] = digest
            self.recorded = True
            return
        if known != digest:
            raise BedHostKeyMismatch(f'床内主机 {self._ip} 的密钥与已钉扎的不一致，拒绝递送凭据')

def probe_hosts(client: Any, targets: Mapping[str, str], *, username: str, password: str, timeout: int=20, failures: dict[str, str] | None=None) -> dict[str, tuple[Address, ...]]:
    """经跳板机一跳问各机接口；单台连不上只跳过，不让整份产物作废。

    主机密钥首轮记录、之后比对（`runtime/bed_host_key_pins.json`）：这条路每次
    批入口都跑一次且会递送框架共享口令，不能对任何应答者照单全收。

    传 `failures` 就按 conf key 填失败分类：`host_key_mismatch`（密钥与钉扎不一致，
    安全信号）或 `unreachable`（连不上／回显取不到）。两者都会让这台机进「未探到」
    清单，但用户面要分得开——「有别的东西在那个地址上应答」不能显示成「没开机」。
    """
    import paramiko
    out: dict[str, tuple[Address, ...]] = {}
    transport = client.get_transport()
    pins = _load_pins()
    changed = False
    for name, ip in targets.items():
        inner = paramiko.SSHClient()
        policy = _PinningPolicy(pins, ip)
        inner.set_missing_host_key_policy(policy)
        try:
            channel = transport.open_channel('direct-tcpip', (ip, 22), ('127.0.0.1', 0))
            inner.connect(ip, username=username, password=password, sock=channel, timeout=timeout, look_for_keys=False, allow_agent=False)
            out[name] = parse_ip_addr(_exec(inner, _HOST_PROBE_CMD, timeout=timeout))
            changed = changed or policy.recorded
        except Exception as exc:
            mismatch = isinstance(exc, BedHostKeyMismatch)
            if failures is not None:
                failures[name] = 'host_key_mismatch' if mismatch else 'unreachable'
            if mismatch:
                logger.warning('探测 %s 拒绝递送凭据：%s', name, exc)
            else:
                logger.warning('探测 %s 失败：%s', name, type(exc).__name__)
            continue
        finally:
            try:
                inner.close()
            except Exception:
                pass
    if changed:
        _save_pins(pins)
    return out

def _load_overlay() -> dict[str, Any]:
    """读人工登记的床事实。文件不在是正常的；在而读不动必须抛——静默跳过
    会让它登记的设备从产物里无声消失，且没有第二处能对出来。"""
    if not _OVERLAY.is_file():
        return {}
    try:
        payload = json.loads(_OVERLAY.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise TopologyProbeError(f'{_OVERLAY.name} 在但读不动（{type(exc).__name__}）——它登记的是探不到的设备，跳过会让它们从产物里无声消失') from exc
    if not isinstance(payload, dict):
        raise TopologyProbeError(f'{_OVERLAY.name} 不是 JSON 对象')
    devices = payload.get('devices', [])
    if not isinstance(devices, list):
        raise TopologyProbeError(f'{_OVERLAY.name} 的 devices 不是数组')
    for entry in devices:
        if not isinstance(entry, dict) or not str(entry.get('name') or '').strip():
            raise TopologyProbeError(f'{_OVERLAY.name} 里有条目缺 name')
    return payload

def generate(*, dry_run: bool=False, conf_override: str='') -> dict[str, Any]:
    """跑一次完整探测并整份重写两份产物。"""
    import os
    from cex_core.engine.case_compiler.device_mcp_client import _connect
    apv_src = (os.environ.get('IST_APV_SRC') or '/home/test/apv_src').strip()
    client = _connect()
    try:
        conf, addresses, neighbors = probe_jumphost(client, apv_src=apv_src, conf_override=conf_override)
        domains = group_l2_domains(addresses, neighbors)
        targets = dict(conf.hosts)
        credentials = _host_credentials()
        probe_failures: dict[str, str] = {}
        host_addresses = probe_hosts(client, targets, username=credentials[0], password=credentials[1], failures=probe_failures) if credentials[0] else {}
    finally:
        try:
            client.close()
        except Exception:
            pass
    previous: dict[str, Any] = {}
    if _JSON_OUT.is_file():
        try:
            previous = json.loads(_JSON_OUT.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            previous = {}
    topology = build_topology(conf=conf, jumphost_addresses=addresses, domains=domains, host_addresses=host_addresses, overlay=_load_overlay(), previous=previous)
    assign_domain_members(domains, topology['devices'])
    for record, domain in zip(topology['_l2_domains'], domains, strict=True):
        record['members'] = list(domain.members)
    observation = {'_comment': '本轮探测观察。随 ARP 老化与单台 ssh 结果抖动，**不入 knowledge/**——那一层是编译上下文的密封轴，每批重写会让同名续跑整批归档重编。', 'unprobed_devices': topology.pop('_unprobed_this_run', []), 'host_key_mismatch_devices': sorted((canonical_device_name(key) for key, reason in probe_failures.items() if reason == 'host_key_mismatch')), 'unregistered_neighbours': unregistered_neighbours(domains, neighbors, topology['devices'])}
    if not dry_run:
        _write_if_changed(_JSON_OUT, json.dumps(topology, ensure_ascii=False, indent=2) + '\n')
        _write_if_changed(_RAG_OUT, render_rag_md(topology))
        _OBSERVATION_OUT.parent.mkdir(parents=True, exist_ok=True)
        _OBSERVATION_OUT.write_text(json.dumps(observation, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    topology['_observation'] = observation
    return topology

def _write_if_changed(path: Path, text: str) -> bool:
    """字节相同就不落笔——ARP 邻居会老化，无谓重写会把工作树弄脏。"""
    try:
        if path.is_file() and path.read_text(encoding='utf-8') == text:
            return False
    except OSError:
        pass
    path.write_text(text, encoding='utf-8')
    return True

def _host_credentials() -> tuple[str, str]:
    """从 mirror 源码现取框架连各机的凭据，不落本仓常量。取不到返回空。

    按 AST 取**同一个 `connect(...)` 调用**的两个关键字：两条独立正则各自扫全文，
    mirror 里再出现一个别的 connect 就会把 A 处的 user 配上 B 处的 password，
    而这对凭据是要递到床内每台机器上的。
    """
    import ast
    src = _ROOT / 'knowledge' / 'framework' / 'mirror' / 'lib' / 'ssh_server.py'
    if not src.is_file():
        return ('', '')
    try:
        tree = ast.parse(src.read_text(encoding='utf-8', errors='replace'))
    except SyntaxError:
        return ('', '')
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == 'connect'):
            continue
        pair: dict[str, str] = {}
        for keyword in node.keywords:
            if keyword.arg in {'username', 'password'} and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                pair[keyword.arg] = keyword.value.value
        if len(pair) == 2:
            found.append((pair['username'], pair['password']))
    if len(found) != 1:
        logger.warning('mirror ssh_server 里字面凭据的 connect 有 %d 处，不取', len(found))
        return ('', '')
    return found[0]

def main(argv: Sequence[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='只探测并打印摘要，不落盘')
    parser.add_argument('--conf-name', default='', help='显式指定跳板机 conf 文件名')
    args = parser.parse_args(argv)
    from cex_core.engine.langchain_env import langchain_load_dotenv_if_present
    langchain_load_dotenv_if_present()
    try:
        topology = generate(dry_run=args.dry_run, conf_override=args.conf_name)
    except TopologyProbeError as exc:
        print(f'拓扑探测失败：{exc}', file=sys.stderr)
        return 1
    devices = topology.get('devices') or []
    domains = topology.get('_l2_domains') or []
    observation = topology.get('_observation') or {}
    unprobed = observation.get('unprobed_devices') or []
    mismatched = observation.get('host_key_mismatch_devices') or []
    print(f'设备 {len(devices)} 台，二层域 {len(domains)} 个', end='')
    print(f'，未逐台探到 {len(unprobed)} 台' if unprobed else '')
    if mismatched:
        print(f"其中 {len(mismatched)} 台主机密钥与已钉扎的不一致（{'、'.join((str(n) for n in mismatched))}），已拒绝递送凭据", file=sys.stderr)
    if args.dry_run:
        print('(--dry-run，未落盘)')
    else:
        print(f'已重写 {_JSON_OUT.relative_to(_ROOT)}')
        print(f'已重写 {_RAG_OUT.relative_to(_ROOT)}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
