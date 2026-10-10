import fs from "node:fs";

type Dict = Record<string, any>;

const _MAX_HEAD_TOKENS = 8;
const _REDACTED_ARGUMENT_TYPE = "REDACTED_SENSITIVE";
const _CLOSED_SET_ENUM_SOURCES = new Set(["xml_limit", "manual_table", "footprint"]);

export const XML_COMMAND_NOT_FOUND = "command_not_found";

function isPlainObject(value: unknown): value is Dict {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asList(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

function casefold(text: string): string {
  return text.toLowerCase();
}

export function norm_command_tokens(cmd: string): string[] {
  return _norm_tokens(cmd);
}

export function strip_token_quotes(token: string): string {
  const text = String(token ?? "").trim();
  if (text.length >= 2 && text[0] === text[text.length - 1] && (text[0] === '"' || text[0] === "'")) {
    return text.slice(1, -1);
  }
  return text;
}

export function match_command_head(tokens: string[], heads: Dict): [string, Dict] | null {
  return _try_match(tokens, heads);
}

function shlexSplit(value: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let has = false;
  let quote: string | null = null;
  let escaped = false;
  for (const ch of value) {
    if (escaped) {
      current += ch;
      escaped = false;
      continue;
    }
    if (quote !== null) {
      if (ch === "\\") {
        escaped = true;
        continue;
      }
      if (ch === quote) {
        quote = null;
        continue;
      }
      current += ch;
      continue;
    }
    if (ch === "\\") {
      escaped = true;
      has = true;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      has = true;
      continue;
    }
    if (/\s/.test(ch)) {
      if (has) {
        tokens.push(current);
        current = "";
        has = false;
      }
      continue;
    }
    current += ch;
    has = true;
  }
  if (escaped) {
    throw new Error("No escaped character");
  }
  if (quote !== null) {
    throw new Error("No closing quotation");
  }
  if (has) {
    tokens.push(current);
  }
  return tokens;
}

function _norm_tokens(cmd: string): string[] {
  const value = String(cmd ?? "").trim();
  if (!value) {
    return [];
  }
  try {
    return shlexSplit(value).map((token) => token.toLowerCase());
  } catch {
    return value
      .toLowerCase()
      .replace(/\s+/g, " ")
      .split(" ")
      .filter((part) => part)
      .map((part) => strip_token_quotes(part).toLowerCase());
  }
}

function _head_candidate(tokens: string[], heads: Dict): [string, Dict, string[]] | null {
  for (let k = Math.min(tokens.length, _MAX_HEAD_TOKENS); k > 0; k--) {
    const head = tokens.slice(0, k).join(" ");
    const entry = heads[head];
    if (isPlainObject(entry)) {
      return [head, entry, tokens.slice(k)];
    }
  }
  return null;
}

function isValidIpv4(value: string): boolean {
  const m = /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/.exec(value);
  if (!m) {
    return false;
  }
  for (let i = 1; i <= 4; i++) {
    const part = m[i];
    if (part.length > 1 && part[0] === "0") {
      return false;
    }
    if (parseInt(part, 10) > 255) {
      return false;
    }
  }
  return true;
}

function isValidIpv6(value: string): boolean {
  let v = value;
  if (v.includes(".")) {
    const idx = v.lastIndexOf(":");
    if (idx < 0) {
      return false;
    }
    const tail = v.slice(idx + 1);
    if (!isValidIpv4(tail)) {
      return false;
    }
    v = v.slice(0, idx + 1) + "0:0";
  }
  const halves = v.split("::");
  if (halves.length > 2) {
    return false;
  }
  const isHexGroup = (g: string) => /^[0-9A-Fa-f]{1,4}$/.test(g);
  const left = halves[0] === "" ? [] : halves[0].split(":");
  const right = halves.length === 2 ? (halves[1] === "" ? [] : halves[1].split(":")) : [];
  if (!left.every(isHexGroup) || !right.every(isHexGroup)) {
    return false;
  }
  if (halves.length === 2) {
    return left.length + right.length <= 8;
  }
  return left.length === 8;
}

function parseIpVersion(value: string): number {
  if (value.includes(":")) {
    return isValidIpv6(value) ? 6 : 0;
  }
  return isValidIpv4(value) ? 4 : 0;
}

function isIpv4Netmask(value: string): boolean {
  const m = /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/.exec(value);
  if (!m) {
    return false;
  }
  let bits = 0;
  for (let i = 1; i <= 4; i++) {
    const part = m[i];
    if (part.length > 1 && part[0] === "0") {
      return false;
    }
    const n = parseInt(part, 10);
    if (n > 255) {
      return false;
    }
    bits = bits * 256 + n;
  }
  bits = bits >>> 0;
  const inv = ~bits >>> 0;
  return (inv & (inv + 1)) === 0;
}

function _value_matches_type(value: string, argType: string): boolean {
  if (argType === "STRING") {
    return true;
  }
  if (argType === "XSTRING") {
    return Boolean(value);
  }
  if (argType === "U16" || argType === "U32") {
    if (!/^\d+$/.test(value)) {
      return false;
    }
    const number = parseInt(value, 10);
    return number <= (argType === "U16" ? 65535 : 4294967295);
  }
  if (argType === "IPADDR" || argType === "DOTTEDIP") {
    const version = parseIpVersion(value);
    if (version === 0) {
      return false;
    }
    return argType === "IPADDR" || version === 4;
  }
  if (argType === "IPMASK") {
    if (/^\d+$/.test(value)) {
      const n = parseInt(value, 10);
      return 0 <= n && n <= 128;
    }
    return isIpv4Netmask(value);
  }
  return false;
}

function _value_domain_error(value: string, arg: Dict, index: number): Dict | null {
  const domain = arg["value_domain"];
  if (!isPlainObject(domain)) {
    return null;
  }
  const folded = casefold(value);
  for (const claim of asList(domain["default"])) {
    if (folded === casefold(claim["value"] ? String(claim["value"]) : "")) {
      return null;
    }
  }
  const allEnumClaims = asList(domain["enum"]).filter(isPlainObject);
  const enumClaims = allEnumClaims.filter((claim) =>
    _CLOSED_SET_ENUM_SOURCES.has(String(claim["source"]))
  );
  const rangeClaims = asList(domain["range"]).filter(isPlainObject);
  if (!enumClaims.length && !rangeClaims.length) {
    return null;
  }
  const allMembers = new Set<string>();
  for (const claim of allEnumClaims) {
    for (const item of asList(claim["values"])) {
      allMembers.add(casefold(String(item)));
    }
  }
  if (allMembers.has(folded)) {
    return null;
  }
  const unionSeparators = [
    ...new Set(
      asList(domain["union"])
        .filter((claim) => isPlainObject(claim) && (claim["separator"] ? String(claim["separator"]) : ""))
        .map((claim) => String(claim["separator"]))
    ),
  ].sort();
  for (const separator of unionSeparators) {
    const parts = folded.split(separator);
    if (parts.length >= 2 && parts.every((part) => part && allMembers.has(part))) {
      return null;
    }
  }
  let number: number | null = null;
  const trimmed = value.trim();
  if (/^[+-]?\d+$/.test(trimmed)) {
    number = parseInt(trimmed, 10);
  }
  if (rangeClaims.length && number === null) {
    if (!enumClaims.length) {
      return null;
    }
  }
  for (const claim of rangeClaims) {
    if (
      number !== null &&
      Math.trunc(Number(claim["min"])) <= number &&
      number <= Math.trunc(Number(claim["max"]))
    ) {
      return null;
    }
  }
  if (enumClaims.length) {
    const error: Dict = {
      code: "enum_mismatch",
      argument_index: index,
      allowed_enums: [
        ...new Set(
          allEnumClaims.flatMap((claim) => asList(claim["values"]).map((item) => String(item)))
        ),
      ].sort(),
      value_domain_sources: [...new Set(allEnumClaims.map((claim) => String(claim["source"])))].sort(),
    };
    if (unionSeparators.length) {
      error["union_separators"] = unionSeparators;
    }
    return error;
  }
  return {
    code: "range_mismatch",
    argument_index: index,
    allowed_ranges: rangeClaims.map((claim) => ({
      min: Math.trunc(Number(claim["min"])),
      max: Math.trunc(Number(claim["max"])),
    })),
    value_domain_sources: [...new Set(rangeClaims.map((claim) => String(claim["source"])))].sort(),
  };
}

function _argument_variants(entry: Dict): Dict[][] {
  const variants: Dict[][] = [];
  const primary = entry["args"];
  if (Array.isArray(primary)) {
    variants.push(primary);
  }
  for (const candidate of asList(entry["arg_variants"])) {
    if (Array.isArray(candidate) && !variants.some((v) => JSON.stringify(v) === JSON.stringify(candidate))) {
      variants.push(candidate);
    }
  }
  return variants;
}

function _parameter_contract_error(rem: string[], entry: Dict): Dict | null {
  const variants = _argument_variants(entry);
  if (!variants.length) {
    const pmax = entry["pmax"] ? Math.trunc(Number(entry["pmax"])) : 0;
    if (rem.length > pmax) {
      return { code: "arity_too_many", actual_count: rem.length, pmax };
    }
    return null;
  }

  const failures: Dict[] = [];
  let accepted = false;
  for (const args of variants) {
    const required = args.filter((arg) => !arg["optional"]).length;
    const maximum = args.length;
    if (rem.length < required) {
      failures.push({
        code: "arity_too_few",
        actual_count: rem.length,
        required_min: required,
        pmax: maximum,
      });
      continue;
    }
    if (rem.length > maximum) {
      failures.push({
        code: "arity_too_many",
        actual_count: rem.length,
        required_min: required,
        pmax: maximum,
      });
      continue;
    }
    let mismatch: Dict | null = null;
    for (let index = 0; index < rem.length; index++) {
      const value = rem[index];
      const arg = args[index];
      const argType = arg["type"] ? String(arg["type"]) : "";
      if (argType === _REDACTED_ARGUMENT_TYPE && arg["executable"] === false) {
        mismatch = { code: "sensitive_parameter_unexecutable", argument_index: index + 1 };
        break;
      }
      if (!_value_matches_type(value, argType)) {
        mismatch = { code: "type_mismatch", argument_index: index + 1, expected_type: argType };
        break;
      }
      const domainError = _value_domain_error(value, arg, index + 1);
      if (domainError !== null) {
        mismatch = domainError;
        break;
      }
    }
    if (mismatch === null) {
      accepted = true;
    } else {
      failures.push(mismatch);
    }
  }
  const sensitive = failures.find((item) => item["code"] === "sensitive_parameter_unexecutable");
  if (sensitive !== undefined) {
    return sensitive;
  }
  if (accepted) {
    return null;
  }
  for (const code of ["type_mismatch", "enum_mismatch", "range_mismatch"]) {
    const preferred = failures.find((item) => item["code"] === code);
    if (preferred !== undefined) {
      return preferred;
    }
  }
  return failures[0];
}

function _try_match(tokens: string[], heads: Dict): [string, Dict] | null {
  const candidate = _head_candidate(tokens, heads);
  if (candidate === null) {
    return null;
  }
  const [head, entry, rem] = candidate;
  if ("manual_pmax" in entry && "vendor_pmax" in entry) {
    const manualPmax = entry["manual_pmax"] ? Math.trunc(Number(entry["manual_pmax"])) : 0;
    const vendorPmax = entry["vendor_pmax"] ? Math.trunc(Number(entry["vendor_pmax"])) : 0;
    if (Math.min(manualPmax, vendorPmax) < rem.length && rem.length <= Math.max(manualPmax, vendorPmax)) {
      return [head, entry];
    }
    return null;
  }
  return _parameter_contract_error(rem, entry) === null ? [head, entry] : null;
}

export function resolve_vendor_command(cmd: string, inv: Dict | null): Dict {
  if (inv === null) {
    return {
      decided: false, hit: false, head: "", src: "",
      version: "", device_build: "", origin: "",
    };
  }
  const heads = inv["heads"];
  const tokens = _norm_tokens(cmd);
  if (!tokens.length || !/^[a-z\[]/.test(tokens[0])) {
    return {
      decided: false, hit: false, head: "", src: "",
      version: inv["version"] ?? "",
      device_build: inv["device_os_build"] ?? "",
      origin: "",
    };
  }
  const candidate = _head_candidate(tokens, heads);
  if (candidate === null) {
    return {
      decided: true, hit: false, head: "", src: "",
      version: inv["version"] ?? "",
      device_build: inv["device_os_build"] ?? "",
      origin: "", reason_code: XML_COMMAND_NOT_FOUND,
    };
  }
  const [head, entry, rem] = candidate;
  const parameterError = _parameter_contract_error(rem, entry);
  if (parameterError !== null) {
    return {
      decided: true, hit: false, head,
      src: String(entry["src"] ?? ""),
      version: inv["version"] ?? "",
      device_build: inv["device_os_build"] ?? "",
      origin: entry["origin"] ? String(entry["origin"]) : "",
      reason_code: "parameter_contract_violation",
      parameter_error: parameterError,
    };
  }
  return {
    decided: true, hit: true, head,
    src: String(entry["src"] ?? ""),
    version: inv["version"] ?? "",
    device_build: inv["device_os_build"] ?? "",
    origin: entry["origin"] ? String(entry["origin"]) : "",
  };
}

function _pyListRepr(items: string[]): string {
  return "[" + items.map((s) => `'${s.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`).join(", ") + "]";
}

export function load_projection(path: string): Dict {
  const data: unknown = JSON.parse(fs.readFileSync(path, "utf8"));
  if (!isPlainObject(data)) {
    throw new Error(`${path} 不是命令树投影`);
  }
  let out: Dict = data;
  const headers = out["headers"];
  const manual = out["manual_declarations"];
  if (isPlainObject(headers) && isPlainObject(manual)) {
    const overlap = Object.keys(headers).filter((k) => k in manual).sort();
    if (overlap.length) {
      throw new Error(`${path} 的 headers 与 manual_declarations 有同名条目：${_pyListRepr(overlap.slice(0, 5))}`);
    }
    out = { ...out, heads: { ...headers, ...manual } };
  }
  if (!isPlainObject(out["heads"])) {
    throw new Error(`${path} 不是命令树投影（缺 headers / manual_declarations）`);
  }
  return out;
}

export const normCommandTokens = norm_command_tokens;
export const stripTokenQuotes = strip_token_quotes;
export const matchCommandHead = match_command_head;
export const resolveVendorCommand = resolve_vendor_command;
export const loadProjection = load_projection;
