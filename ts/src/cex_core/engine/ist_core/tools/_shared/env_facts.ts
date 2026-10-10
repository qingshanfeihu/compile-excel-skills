import fs from "node:fs";

const logger = {
  warning: (...args: any[]) => console.warn(...args),
};

const _kp = require("../../../knowledge_paths");
const _TOPOLOGY_JSON: string = _kp.KNOWLEDGE_AUTO_ENV_TOPOLOGY_JSON;
const _ACTIONS_JSON: string = _kp.KNOWLEDGE_AUTO_ENV_ACTIONS_JSON;

const _IPV4_RE = /\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b/g;
const _NON_HOST_IPV4S = new Set(["0.0.0.0", "255.255.255.255"]);
const _IPV6_TOKEN_RE = /[0-9A-Fa-f:.]{2,}/g;

function _ipv4ToInt(ip: string): number | null {
  const parts = ip.split(".");
  if (parts.length !== 4) {
    return null;
  }
  let value = 0;
  for (const p of parts) {
    if (!/^\d{1,3}$/.test(p)) {
      return null;
    }
    const n = parseInt(p, 10);
    if (n > 255) {
      return null;
    }
    value = (value << 8) >>> 0;
    value = (value + n) >>> 0;
  }
  return value >>> 0;
}

function _intToIpv4(value: number): string {
  return [(value >>> 24) & 0xff, (value >>> 16) & 0xff, (value >>> 8) & 0xff, value & 0xff].join(".");
}

class IPv4Address {
  readonly value: number;
  readonly version = 4;

  constructor(ip: string) {
    const v = _ipv4ToInt(ip);
    if (v === null) {
      throw new Error(`invalid IPv4 address: ${ip}`);
    }
    this.value = v;
  }

  toString(): string {
    return _intToIpv4(this.value);
  }
}

class IPv6Address {
  readonly groups: bigint;
  readonly version = 6;

  constructor(ip: string) {
    this.groups = _parseIpv6(ip);
  }

  toString(): string {
    return _formatIpv6(this.groups);
  }
}

function _parseIpv6(ip: string): bigint {
  let text = ip;
  if (text.includes(".")) {
    const lastColon = text.lastIndexOf(":");
    if (lastColon < 0) {
      throw new Error(`invalid IPv6 address: ${ip}`);
    }
    const v4 = _ipv4ToInt(text.slice(lastColon + 1));
    if (v4 === null) {
      throw new Error(`invalid IPv6 address: ${ip}`);
    }
    const hi = (v4 >>> 16) & 0xffff;
    const lo = v4 & 0xffff;
    text = text.slice(0, lastColon + 1) + hi.toString(16) + ":" + lo.toString(16);
  }
  const halves = text.split("::");
  if (halves.length > 2) {
    throw new Error(`invalid IPv6 address: ${ip}`);
  }
  const parseSide = (side: string): number[] => {
    if (side === "") {
      return [];
    }
    return side.split(":").map((g) => {
      if (!/^[0-9A-Fa-f]{1,4}$/.test(g)) {
        throw new Error(`invalid IPv6 address: ${ip}`);
      }
      return parseInt(g, 16);
    });
  };
  let head = parseSide(halves[0]);
  let tail = halves.length === 2 ? parseSide(halves[1]) : [];
  if (halves.length === 2) {
    const missing = 8 - head.length - tail.length;
    if (missing < 0) {
      throw new Error(`invalid IPv6 address: ${ip}`);
    }
    head = head.concat(new Array(missing).fill(0), tail);
  } else if (head.length !== 8) {
    throw new Error(`invalid IPv6 address: ${ip}`);
  }
  let value = 0n;
  for (const g of head) {
    value = (value << 16n) | BigInt(g);
  }
  return value;
}

function _formatIpv6(value: bigint): string {
  const groups: number[] = [];
  let v = value;
  for (let i = 0; i < 8; i++) {
    groups.unshift(Number(v & 0xffffn));
    v >>= 16n;
  }
  let bestStart = -1;
  let bestLen = 0;
  let curStart = -1;
  let curLen = 0;
  for (let i = 0; i < 8; i++) {
    if (groups[i] === 0) {
      if (curStart < 0) {
        curStart = i;
        curLen = 0;
      }
      curLen += 1;
      if (curLen > bestLen) {
        bestLen = curLen;
        bestStart = curStart;
      }
    } else {
      curStart = -1;
      curLen = 0;
    }
  }
  if (bestLen < 2) {
    bestStart = -1;
  }
  const parts: string[] = [];
  let i = 0;
  while (i < 8) {
    if (i === bestStart) {
      parts.push("");
      i += bestLen;
      if (i >= 8) {
        parts.push("");
      }
      continue;
    }
    parts.push(groups[i].toString(16));
    i += 1;
  }
  let out = parts.join(":");
  if (out.startsWith(":") && !out.startsWith("::")) {
    out = ":" + out;
  }
  if (out.endsWith(":") && !out.endsWith("::")) {
    out = out + ":";
  }
  return out;
}

class IpNetwork {
  readonly version: number;
  readonly networkValue: bigint;
  readonly prefixlen: number;

  constructor(cidr: string, opts: { strict?: boolean } = {}) {
    const strict = opts.strict ?? true;
    const slash = cidr.indexOf("/");
    if (slash < 0) {
      throw new Error(`invalid network: ${cidr}`);
    }
    const addrPart = cidr.slice(0, slash);
    const prefix = parseInt(cidr.slice(slash + 1), 10);
    if (addrPart.includes(":")) {
      this.version = 6;
      if (!Number.isInteger(prefix) || prefix < 0 || prefix > 128) {
        throw new Error(`invalid network: ${cidr}`);
      }
      this.prefixlen = prefix;
      const addr = _parseIpv6(addrPart);
      const bits = 128n;
      const mask = prefix === 0 ? 0n : ((1n << BigInt(prefix)) - 1n) << (bits - BigInt(prefix));
      const network = addr & mask;
      if (strict && network !== addr) {
        throw new Error(`invalid network: ${cidr}`);
      }
      this.networkValue = network;
    } else {
      this.version = 4;
      if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32) {
        throw new Error(`invalid network: ${cidr}`);
      }
      this.prefixlen = prefix;
      const addrInt = _ipv4ToInt(addrPart);
      if (addrInt === null) {
        throw new Error(`invalid network: ${cidr}`);
      }
      const addr = BigInt(addrInt >>> 0);
      const mask = prefix === 0 ? 0n : ((1n << BigInt(prefix)) - 1n) << (32n - BigInt(prefix));
      const network = addr & mask;
      if (strict && network !== addr) {
        throw new Error(`invalid network: ${cidr}`);
      }
      this.networkValue = network;
    }
  }

  contains(addr: IPv4Address | IPv6Address): boolean {
    if (addr.version !== this.version) {
      return false;
    }
    const bits = this.version === 4 ? 32n : 128n;
    const mask = this.prefixlen === 0 ? 0n : ((1n << BigInt(this.prefixlen)) - 1n) << (bits - BigInt(this.prefixlen));
    const addrValue = addr instanceof IPv4Address ? BigInt(addr.value >>> 0) : addr.groups;
    return (addrValue & mask) === this.networkValue;
  }

  toString(): string {
    if (this.version === 4) {
      return `${_intToIpv4(Number(this.networkValue))}/${this.prefixlen}`;
    }
    return `${_formatIpv6(this.networkValue)}/${this.prefixlen}`;
  }
}

function _parseIpAddress(text: string): IPv4Address | IPv6Address {
  if (text.includes(":")) {
    return new IPv6Address(text);
  }
  return new IPv4Address(text);
}

function _parseIpInterface(cidr: string): { version: number; toString(): string } {
  const bare = cidr.split("/")[0];
  _parseIpAddress(bare);
  return { version: bare.includes(":") ? 6 : 4, toString: () => cidr };
}

function _is_contiguous_netmask(ip: string): boolean {
  let value: number;
  try {
    value = new IPv4Address(ip).value;
  } catch {
    return false;
  }
  const inverted = (value ^ 0xffffffff) >>> 0;
  return (inverted & ((inverted + 1) >>> 0)) === 0;
}

export function normalize_ip_literal(value: any): string {
  let text = String(value || "").trim();
  if (text.startsWith("[") && text.endsWith("]")) {
    text = text.slice(1, -1);
  }
  if (!text) {
    return "";
  }
  text = text.split("%")[0].split("/")[0];
  try {
    return _parseIpAddress(text).toString();
  } catch {
    return "";
  }
}

const _SERVER_TYPES = ["服务器"];
const _LB_TYPES = ["负载均衡"];
const _TRIGGER_TYPES = ["路由器", "客户端"];

export class EnvFacts {
  private _doc: Record<string, any>;
  devices: Record<string, any>[];
  private _exact_ips: Set<string> = new Set();
  private _subnets: IpNetwork[] = [];
  private _subnets6: IpNetwork[] = [];
  private _dev_nets: Record<string, IpNetwork[]> = {};
  private _dev_exact: Record<string, Set<string>> = {};
  private _dev_ifaces: Record<string, Record<string, string[]>> = {};
  private _driver_names: Set<string> = new Set();
  private _display_name: Record<string, string> = {};
  private _routes: Array<[string, IpNetwork]> = [];
  private _routes_uninterpretable = false;

  constructor(doc: Record<string, any>) {
    this._doc = doc;
    this.devices = doc.devices ?? [];
    this._build();
    this._build_routes(doc);
  }

  private _build(): void {
    const seen_subnets = new Set<string>();
    for (const dev of this.devices) {
      const name_l = String(dev.name ?? "").trim().toLowerCase();
      if (name_l) {
        if (!(name_l in this._display_name)) {
          this._display_name[name_l] = String(dev.name ?? "").trim();
        }
        this._dev_nets[name_l] ??= [];
        this._dev_exact[name_l] ??= new Set();
        this._dev_ifaces[name_l] ??= {};
        const interfaces = dev.interfaces || {};
        for (const [iface, spec] of Object.entries(interfaces)) {
          if (spec === null || typeof spec !== "object" || Array.isArray(spec)) {
            continue;
          }
          const specRec = spec as Record<string, any>;
          const declared = ["ipv4", "ipv6"].map((family) => String(specRec[family] || "").trim());
          const kept = declared.filter((item) => item);
          if (kept.length > 0) {
            this._dev_ifaces[name_l][String(iface).trim()] = kept;
          }
        }
        if (_TRIGGER_TYPES.some((t) => String(dev.type ?? "").includes(t))) {
          this._driver_names.add(name_l);
        }
      }
      for (const cidr of dev.ipv4 ?? []) {
        const bare = String(cidr).split("/")[0];
        this._exact_ips.add(bare);
        if (name_l) {
          this._dev_exact[name_l].add(bare);
        }
        if (String(cidr).includes("/")) {
          let net: IpNetwork;
          try {
            net = new IpNetwork(String(cidr), { strict: false });
          } catch {
            continue;
          }
          if (!seen_subnets.has(net.toString())) {
            seen_subnets.add(net.toString());
            this._subnets.push(net);
          }
          if (name_l && !this._dev_nets[name_l].some((n) => n.toString() === net.toString())) {
            this._dev_nets[name_l].push(net);
          }
        }
      }
      for (const v6 of dev.ipv6 ?? []) {
        const bare6 = String(v6).split("/")[0];
        this._exact_ips.add(bare6);
        if (name_l) {
          this._dev_exact[name_l].add(bare6);
        }
        if (String(v6).includes("/")) {
          let net6: IpNetwork;
          try {
            net6 = new IpNetwork(String(v6), { strict: false });
          } catch {
            continue;
          }
          if (!this._subnets6.some((n) => n.toString() === net6.toString())) {
            this._subnets6.push(net6);
          }
          if (name_l && !this._dev_nets[name_l].some((n) => n.toString() === net6.toString())) {
            this._dev_nets[name_l].push(net6);
          }
        }
      }
    }
  }

  private _build_routes(doc: Record<string, any>): void {
    const raw = doc.routes;
    if (raw === null || raw === undefined) {
      return;
    }
    if (!Array.isArray(raw)) {
      this._routes_uninterpretable = true;
      logger.warning("拓扑 routes 字段存在但不是数组——驱动侧路径判据降级放行(防误杀)。");
      return;
    }
    for (const entry of raw) {
      try {
        const dev_l = String(entry.device).trim().toLowerCase();
        const net = new IpNetwork(String(entry.destination), { strict: false });
        if (dev_l) {
          this._routes.push([dev_l, net]);
        }
      } catch {
        this._routes_uninterpretable = true;
        logger.warning(`拓扑 routes 条目无法按最小 schema {device,destination} 解析:${JSON.stringify(entry)}——驱动侧路径判据降级放行(防误杀)。`);
        return;
      }
    }
  }

  is_reachable(ip: string): boolean {
    const bare = String(ip || "").split("/")[0].trim();
    if (this._exact_ips.has(bare)) {
      return true;
    }
    let addr: IPv4Address;
    try {
      addr = new IPv4Address(bare);
    } catch {
      return false;
    }
    return this._subnets.some((net) => net.contains(addr));
  }

  unreachable_ipv4s(text: string): string[] {
    const out: string[] = [];
    const src = text || "";
    let previous_was_ip = false;
    let previous_end = -1;
    for (const m of src.matchAll(_IPV4_RE)) {
      const ip = m[1];
      const start = m.index ?? 0;
      const gap = src.slice(previous_end, start).replace(/[ \t/,]/g, "");
      const adjacent = previous_was_ip && gap === "";
      previous_was_ip = true;
      previous_end = start + m[0].length;
      if (_NON_HOST_IPV4S.has(ip)) {
        continue;
      }
      if (adjacent && _is_contiguous_netmask(ip)) {
        continue;
      }
      if (!out.includes(ip) && !this.is_reachable(ip)) {
        out.push(ip);
      }
    }
    return out;
  }

  private *_iter_ipv6_literals(text: string): Generator<[string, IPv6Address]> {
    for (const m of (text || "").matchAll(_IPV6_TOKEN_RE)) {
      let tok = m[0];
      if (tok.startsWith("[") && tok.endsWith("]")) {
        tok = tok.slice(1, -1);
      }
      if ((tok.match(/:/g) || []).length < 2) {
        continue;
      }
      tok = tok.split("%")[0];
      for (const cand of [tok, tok.replace(/\.+$/, ""), tok.replace(/\.+$/, "").replace(/:+$/, "")]) {
        if ((cand.match(/:/g) || []).length < 2) {
          break;
        }
        let addr: IPv6Address;
        try {
          addr = new IPv6Address(cand);
        } catch {
          continue;
        }
        yield [cand, addr];
        break;
      }
    }
  }

  unreachable_ipv6s(text: string): string[] {
    const out: string[] = [];
    for (const [lit, addr] of this._iter_ipv6_literals(text)) {
      if (addr.groups === 0n) {
        continue;
      }
      const bare = addr.toString();
      if (this._exact_ips.has(lit) || this._exact_ips.has(bare)) {
        continue;
      }
      if (this._subnets6.some((net) => net.contains(addr))) {
        continue;
      }
      if (!out.includes(lit)) {
        out.push(lit);
      }
    }
    return out;
  }

  service_ips(): string[] {
    const out: string[] = [];
    for (const dev of this.devices) {
      if (_SERVER_TYPES.some((t) => String(dev.type ?? "").includes(t))) {
        for (const cidr of dev.ipv4 ?? []) {
          const bare = String(cidr).split("/")[0];
          if (!out.includes(bare)) {
            out.push(bare);
          }
        }
      }
    }
    return out;
  }

  reachable_subnets(): string[] {
    return this._subnets.map((n) => n.toString());
  }

  infra_ips(): Set<string> {
    const out = new Set<string>();
    for (const ip of this._exact_ips) {
      try {
        new IPv4Address(ip);
        out.add(ip);
      } catch {
        continue;
      }
    }
    return out;
  }

  private _types_per_subnet(): Record<string, Set<string>> {
    const out: Record<string, Set<string>> = {};
    for (const n of this._subnets) {
      out[n.toString()] = new Set();
    }
    for (const dev of this.devices) {
      const t = String(dev.type ?? "");
      for (const cidr of dev.ipv4 ?? []) {
        let addr: IPv4Address;
        try {
          addr = new IPv4Address(String(cidr).split("/")[0]);
        } catch {
          continue;
        }
        for (const net of this._subnets) {
          if (net.contains(addr)) {
            out[net.toString()].add(t);
          }
        }
      }
    }
    return out;
  }

  private _lb_ips_with_subnet(): Array<[string, IpNetwork]> {
    const out: Array<[string, IpNetwork]> = [];
    for (const dev of this.devices) {
      if (!_LB_TYPES.some((t) => String(dev.type ?? "").includes(t))) {
        continue;
      }
      for (const cidr of dev.ipv4 ?? []) {
        let addr: IPv4Address;
        try {
          addr = new IPv4Address(String(cidr).split("/")[0]);
        } catch {
          continue;
        }
        for (const net of this._subnets) {
          if (net.contains(addr)) {
            out.push([addr.toString(), net]);
            break;
          }
        }
      }
    }
    return out;
  }

  listener_ips(): string[] {
    const types = this._types_per_subnet();
    const out: string[] = [];
    for (const [ip, net] of this._lb_ips_with_subnet()) {
      const present = types[net.toString()] ?? new Set<string>();
      if ([...present].some((p) => _TRIGGER_TYPES.some((tt) => p.includes(tt)))) {
        if (!out.includes(ip)) {
          out.push(ip);
        }
      }
    }
    return out;
  }

  unreachable_lb_ips(): string[] {
    const types = this._types_per_subnet();
    const out: string[] = [];
    for (const [ip, net] of this._lb_ips_with_subnet()) {
      const present = types[net.toString()] ?? new Set<string>();
      if (![...present].some((p) => _TRIGGER_TYPES.some((tt) => p.includes(tt)))) {
        if (!out.includes(ip)) {
          out.push(ip);
        }
      }
    }
    return out;
  }

  listener_trigger_pairs(): Array<[string, string[]]> {
    const out: Array<[string, string[]]> = [];
    const seen = new Set<string>();
    for (const lb of this.devices) {
      if (!_LB_TYPES.some((t) => String(lb.type ?? "").includes(t))) {
        continue;
      }
      for (const cidr of [...(lb.ipv4 || []), ...(lb.ipv6 || [])]) {
        const bare = String(cidr).split("/")[0].trim();
        if (!bare || seen.has(bare)) {
          continue;
        }
        let addr: IPv4Address | IPv6Address;
        try {
          addr = _parseIpAddress(bare);
        } catch {
          continue;
        }
        const trig: string[] = [];
        for (const dev of this.devices) {
          if (!_TRIGGER_TYPES.some((t) => String(dev.type ?? "").includes(t))) {
            continue;
          }
          const name = String(dev.name ?? "").trim().toLowerCase();
          if (!name) {
            continue;
          }
          const nets = this._dev_nets[name] ?? [];
          if (nets.some((net) => addr.version === net.version && net.contains(addr)) && !trig.includes(name)) {
            trig.push(name);
          }
        }
        if (trig.length > 0) {
          seen.add(bare);
          out.push([bare, trig]);
        }
      }
    }
    return out;
  }

  private _resolve_device_key(name: string): string {
    const raw = String(name || "").trim().toLowerCase();
    if (!raw) {
      return "";
    }
    if (raw in this._dev_exact) {
      return raw;
    }
    const folded = raw.replace(/[^a-z0-9]/g, "");
    const candidates = Object.keys(this._dev_exact).filter((item) => item.replace(/[^a-z0-9]/g, "") === folded);
    return candidates.length === 1 ? candidates[0] : "";
  }

  device_carried_addresses(name: string): string[] {
    const key = this._resolve_device_key(name);
    return key ? [...(this._dev_exact[key] ?? new Set())].sort() : [];
  }

  device_interface_addresses(name: string): Record<string, any[]> {
    const key = this._resolve_device_key(name);
    const out: Record<string, any[]> = {};
    for (const [iface, addresses] of Object.entries(this._dev_ifaces[key] || {})) {
      const parsed: any[] = [];
      for (const cidr of addresses) {
        try {
          parsed.push(_parseIpInterface(cidr));
        } catch {
          continue;
        }
      }
      if (parsed.length > 0) {
        out[iface] = parsed;
      }
    }
    return out;
  }

  carried_address_rows(): Record<string, any>[] {
    const rows: Record<string, any>[] = [];
    for (const key of Object.keys(this._dev_exact).sort()) {
      const addresses = [...(this._dev_exact[key] ?? new Set<string>())].sort();
      if (addresses.length > 0) {
        rows.push({ device: this._display_name[key] ?? key, addresses });
      }
    }
    return rows;
  }

  is_driver_device(name: string): boolean {
    return this._driver_names.has(String(name || "").trim().toLowerCase());
  }

  device_declared_networks(name: string): string[] {
    return (this._dev_nets[String(name || "").trim().toLowerCase()] ?? []).map((n) => n.toString());
  }

  executor_path_verdict(executor: string, dest_ip: string): Record<string, any> | null {
    const name = String(executor || "").trim().toLowerCase();
    if (!name) {
      return null;
    }
    let bare = String(dest_ip || "").split("/")[0].split("%")[0].trim();
    if (bare.startsWith("[") && bare.endsWith("]")) {
      bare = bare.slice(1, -1);
    }
    let addr: IPv4Address | IPv6Address;
    try {
      addr = _parseIpAddress(bare);
    } catch {
      return null;
    }
    const addrInt = addr instanceof IPv4Address ? BigInt(addr.value >>> 0) : addr.groups;
    if (_NON_HOST_IPV4S.has(bare) || addrInt === 0n) {
      return null;
    }
    if ((this._dev_exact[name] ?? new Set()).has(bare)) {
      return null;
    }
    if (this._routes_uninterpretable) {
      return null;
    }
    const nets = this._dev_nets[name] ?? [];
    if (nets.length === 0) {
      return {
        executor: this._display_name[name] ?? executor,
        executor_networks: [],
        dest: bare,
        dest_segments: this._segments_of(addr),
        reachable_drivers: this._drivers_reaching(addr),
        networks_undeclared: true,
      };
    }
    for (const net of nets) {
      if (addr.version === net.version && net.contains(addr)) {
        return null;
      }
    }
    for (const [dev_l, net] of this._routes) {
      if (dev_l === name && addr.version === net.version && net.contains(addr)) {
        return null;
      }
    }
    return {
      executor: this._display_name[name] ?? executor,
      executor_networks: this.device_declared_networks(name),
      dest: bare,
      dest_segments: this._segments_of(addr),
      reachable_drivers: this._drivers_reaching(addr),
    };
  }

  private _segments_of(addr: IPv4Address | IPv6Address): string[] {
    const dest_segments: string[] = [];
    for (const dev of this.devices) {
      for (const cidr of [...(dev.ipv4 ?? []), ...(dev.ipv6 ?? [])]) {
        if (!String(cidr).includes("/")) {
          continue;
        }
        let net: IpNetwork;
        try {
          net = new IpNetwork(String(cidr), { strict: false });
        } catch {
          continue;
        }
        if (addr.version === net.version && net.contains(addr) && !dest_segments.includes(net.toString())) {
          dest_segments.push(net.toString());
        }
      }
    }
    return dest_segments;
  }

  private _drivers_reaching(addr: IPv4Address | IPv6Address): string[] {
    return [...this._driver_names]
      .filter((dl) => (this._dev_nets[dl] ?? []).some((n) => addr.version === n.version && n.contains(addr)))
      .map((dl) => this._display_name[dl] ?? dl)
      .sort();
  }

  driver_path_verdict(executor: string, dest_ip: string): Record<string, any> | null {
    const name = String(executor || "").trim().toLowerCase();
    if (!this._driver_names.has(name)) {
      return null;
    }
    return this.executor_path_verdict(name, dest_ip);
  }

  service_ips6(): string[] {
    const out: string[] = [];
    for (const dev of this.devices) {
      if (_SERVER_TYPES.some((t) => String(dev.type ?? "").includes(t))) {
        for (const v6 of dev.ipv6 ?? []) {
          const bare6 = String(v6).split("/")[0];
          if (!out.includes(bare6)) {
            out.push(bare6);
          }
        }
      }
    }
    return out;
  }

  listener_ips6(): string[] {
    const driver_v6 = [...this._driver_names].flatMap((dl) => (this._dev_nets[dl] ?? []).filter((n) => n.version === 6));
    const out: string[] = [];
    for (const dev of this.devices) {
      if (!_LB_TYPES.some((t) => String(dev.type ?? "").includes(t))) {
        continue;
      }
      for (const v6 of dev.ipv6 ?? []) {
        const bare6 = String(v6).split("/")[0];
        let addr: IPv4Address | IPv6Address;
        try {
          addr = _parseIpAddress(bare6);
        } catch {
          continue;
        }
        if (driver_v6.some((n) => n.contains(addr)) && !out.includes(bare6)) {
          out.push(bare6);
        }
      }
    }
    return out;
  }

  v6_lb_ips_without_driver_prefix(): string[] {
    const driver_v6 = [...this._driver_names].flatMap((dl) => (this._dev_nets[dl] ?? []).filter((n) => n.version === 6));
    const out: string[] = [];
    for (const dev of this.devices) {
      if (!_LB_TYPES.some((t) => String(dev.type ?? "").includes(t))) {
        continue;
      }
      for (const v6 of dev.ipv6 ?? []) {
        const bare6 = String(v6).split("/")[0];
        let addr: IPv4Address | IPv6Address;
        try {
          addr = _parseIpAddress(bare6);
        } catch {
          continue;
        }
        if (!driver_v6.some((n) => n.contains(addr)) && !out.includes(bare6)) {
          out.push(bare6);
        }
      }
    }
    return out;
  }

  summary_for_agent(): string {
    const listener = this.listener_ips();
    const listener6 = this.listener_ips6();
    const shown_listener = [...listener, ...listener6.filter((ip) => !listener.includes(ip))];
    const blind = this.unreachable_lb_ips();
    const lines = ["=== 本测试床网络事实源(写 IP 只能用这里的真实可达值)==="];
    lines.push(`可达子网(IP 必须落在其中之一): ${this.reachable_subnets().join(", ")}`);
    lines.push(`后端服务器真实 IP(service/pool 后端用): ${this.service_ips().join(", ")}`);
    if (shown_listener.length > 0) {
      lines.push("★ 复用现有接口作 listener/VIP 时,用这些 APV 接口 IP(触发设备 dig/curl 够得着的网段): " + shown_listener.join(", "));
      lines.push("  若用例要测**新建接口类型**(VLAN 子接口、新网段 listener 等):事实源只记录了上述预置接口,未记录新建接口的连通性(VLAN trunk/触发机对接)——猜一个新 IP 大概率上机不解析。这属数据缺口,用 compile_report_underdetermined 如实呈报(obstacle=事实源缺该接口类型的拓扑/连通数据),不要猜 IP 硬编。");
    }
    const carried = this.carried_address_rows();
    if (carried.length > 0) {
      lines.push("Exact carried-address inventory by target device (topology evidence for authoring, not a parameter-role verdict or expected-value signer; determine the endpoint role from the case intent and versioned parameter/manual text):");
      for (const row of carried) {
        lines.push(`  ${row.device}: ${(row.addresses as any[]).map((x) => String(x)).join(", ")}`);
      }
    }
    const pairs = this.listener_trigger_pairs();
    if (pairs.length > 0) {
      lines.push("★ 触发机配对(dig/curl 必须从**与目标 listener 同段**的触发机发起,否则上机 'no servers could be reached'、断言全 fail):");
      for (const [ip, trig] of pairs) {
        lines.push(`    dig/curl 目标 ${ip} → 必须用 test_env 主机 ${trig.join(" 或 ")}`);
      }
    }
    if (blind.length > 0) {
      lines.push("注意：这些 APV 接口 IP 禁止配 listener/VIP(所在网段没有路由器/客户端,dig/curl 源够不着,上机必不解析): " + blind.join(", "));
    }
    const blind_v6 = this.v6_lb_ips_without_driver_prefix();
    if (blind_v6.length > 0) {
      lines.push("注意：这些被测设备 IPv6 接口地址与**任何**触发设备(路由器/客户端)都不共享声明前缀——dig/curl 从驱动侧发起必然无路、上机空返回,禁止选作触发目标: " + blind_v6.join(", "));
    }
    lines.push("设备清单:");
    for (const dev of this.devices) {
      const ips = (dev.ipv4 ?? []).join(", ");
      const v6s = (dev.ipv6 ?? []).join(", ");
      let line = `  ${dev.name} [${dev.type}]: ${ips}`;
      if (v6s) {
        line += `; IPv6: ${v6s}`;
      }
      lines.push(line);
    }
    lines.push("选址规则:listener/VIP 的 IP、以及 check 步骤里 dig/curl 的目标 IP 必须一致且来自上面的 ★ 列表;后端用服务器真实 IP。**dig/curl 步骤的 test_env 主机(F 列)必须按上面「★ 触发机配对」选,且用小写**——目标 IP 在哪段就用哪台同段触发机(如 .32 段用 routerb、.34 段用 routera);框架按方法名精确分派(不转小写),写成 routerB 大写会 AttributeError、dig 不执行。选错段必不解析。");
    lines.push("禁止裸用 1.1.1.1/2.2.2.2/10.x/192.168.x 等示例 IP——它们不可达,上机 dig 必失败。");
    return lines.join("\n");
  }
}

export class EnvFactsUnavailable extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "EnvFactsUnavailable";
  }
}

let _env_facts_cache: EnvFacts | null = null;

export function get_env_facts(): EnvFacts {
  if (_env_facts_cache !== null) {
    return _env_facts_cache;
  }
  if (!fs.existsSync(_TOPOLOGY_JSON)) {
    logger.warning(`env facts JSON 不存在: ${_TOPOLOGY_JSON};判据入口会抛 EnvFactsUnavailable。`);
    _env_facts_cache = new EnvFacts({ devices: [] });
    return _env_facts_cache;
  }
  let doc: Record<string, any>;
  try {
    doc = JSON.parse(fs.readFileSync(_TOPOLOGY_JSON, "utf8"));
  } catch (exc) {
    logger.warning(`env facts JSON 解析失败: ${exc};判据入口会抛 EnvFactsUnavailable。`);
    _env_facts_cache = new EnvFacts({ devices: [] });
    return _env_facts_cache;
  }
  _env_facts_cache = new EnvFacts(doc);
  return _env_facts_cache;
}

export function get_env_facts_cache_clear(): void {
  _env_facts_cache = null;
}

export function require_env_facts(): EnvFacts {
  const facts = get_env_facts();
  if (facts.devices.length === 0) {
    const name = _TOPOLOGY_JSON.split(/[\\/]/).pop();
    throw new EnvFactsUnavailable(`床事实不可用（${name}）；它由环境收敛生成，先跑一次入口`);
  }
  return facts;
}

export function is_reachable(ip: string): boolean {
  return require_env_facts().is_reachable(ip);
}
