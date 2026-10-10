#!/usr/bin/env node
// 生成：tools/extract_engine.py ← InfoTest scripts/maintenance/build_vendor_stdlib.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../../_root";
import { atomic_write_bytes_nofollow, open_directory_nofollow, read_regular_at_nofollow, read_regular_nofollow } from "../../case_compiler/_sealed_io";
import { is_credential_argument, is_placeholder_default_literal, matching_credential_literal_count, mirror_credential_literals, MirrorCredentialLiteralError } from "../../case_compiler/credential_literals";
import { catalog_alternate_row_enum_is_closed_set, catalog_enum_is_closed_set, catalog_manual_claims, catalog_row_describes_one_parameter, load_coupled_catalog, manual_root as _default_manual_root } from "../../kms/manual_catalog_store";
import { preflight_command_tree_xml, projection_policy_identity, projection_xml_default_literal_count, xml_sensitive_literal_count, xml_sensitive_literal_replace } from "../../sync/command_tree_sync";

const ROOT = _cex_data_path("");
const PLACEHOLDER = /[<[]([^<>[\]]+)[>\]]/g;
const ENUM = /\{([^{}]+)\}/g;
const _LEDGER_FILE_RE = /^[a-z][a-z0-9_-]{0,63}\.jsonl$/;
const _FOOTPRINT_MAX_FILES = 8192;
const _DOMAIN_MAX_TEXT_CHARS = 4096;
const _ENUM_MAX_MEMBERS = 64;
const _NUMERIC_ARGUMENT_TYPES = new Set(["U16", "U32"]);
const _TEXT_ARGUMENT_TYPES = new Set(["STRING", "XSTRING"]);
const _VALUE_DOMAIN_SOURCE_RANK: Record<string, number> = { xml_limit: 0, xml_help: 1, manual_table: 2, footprint: 3 };
const _XML_DERIVED_VALUE_DOMAIN_SOURCES = new Set(["xml_limit", "xml_help"]);
const _SENTENCE_SPLIT_RE = /(?:<br\s*\/?>|。|；|;|\n)/;
const _LENGTH_WORDS = ["长度", "字节", "字符", "byte", "character"];
const _ALTERNATION_WORDS = ["或", "|", "以及", " or "];
const _CONDITIONAL_WORDS = ["当", "如果", "若", "除非", "仅当"];
const _VALUE_STATEMENT_WORDS = ["取值", "范围", "之间"];
const _DOMAIN_NUMBER = "\\d[\\d,]*";
const _RANGE_CORE_RE = new RegExp(`(?<lo>${_DOMAIN_NUMBER})\\s*(?:到|至|~|～)\\s*(?<hi>${_DOMAIN_NUMBER})`, "g");
const _RANGE_WHOLE_RE = new RegExp(`^\\s*(?<lo>${_DOMAIN_NUMBER})\\s*(?:到|至|~|～|-|—)\\s*(?<hi>${_DOMAIN_NUMBER})\\s*(?:之间的整数|之间|的整数|)\\s*$`);
const _LENGTH_RE = new RegExp(`长度不?(?:大于|超过|多于|得超过)\\s*(?<hi>${_DOMAIN_NUMBER})\\s*个?\\s*(?:字节|字符)`);
const _XML_LIMIT_RE = new RegExp(`^\\[\\s*(?<lo>${_DOMAIN_NUMBER})\\s*-\\s*(?<hi>${_DOMAIN_NUMBER})\\s*\\]$`);
const _DOMAIN_LITERAL_RE = /^[A-Za-z0-9_.:+-]+$/;
const _ENUM_SEPARATOR_RE = /\s*(?:、|｜|\||，|,|或者|或)\s*/g;
const _ENUM_LEAD_RE = /(?:取值(?:必须|只能)?为|取值是|可选值(?:为|是))\s*(?<body>.+)$/;
const _XML_HELP_ALTERNATION_RE = /(?:[A-Za-z0-9_.:+-]+[ \t]*\|[ \t]*)+[A-Za-z0-9_.:+-]+/g;
const _XML_HELP_MIN_ALTERNATIVES = 3;
const _XML_HELP_UNION_RE = /union\s+by\s+\w+\s*\(\s*(?<sep>[^\w\s])\s*\)/i;
const _XML_HELP_UNION_DEFAULT_RE = /default\s+(?:is|=)\s*(?<body>[A-Za-z0-9]+(?:[^\w\s][A-Za-z0-9]+)+)/gi;
const _DEFAULT_RE = /默认(?:值)?(?:为|是|＝|=)\s*[""\"'`]?(?<v>[^""\"'`，。；、\s]+)[""\"'`]?/;

function _xml_sensitive_literal_count(text: string, values: Set<string>): number {
  return xml_sensitive_literal_count(text, values);
}

function _xml_sensitive_literal_redact(text: string, values: Set<string>): string {
  return xml_sensitive_literal_replace(text, values);
}

export function xml_default_value_closure(root: any): Set<string> {
  const defaults = new Set<string>();
  function walk(node: any): void {
    if (node.tagName === "arg") {
      const name = node.getAttribute?.("name");
      const type = node.getAttribute?.("type");
      const help = node.getAttribute?.("help_string");
      const defaultValue = node.getAttribute?.("default_value");
      if (defaultValue && is_credential_argument({ name, arg_type: type, help_string: help }) && !is_placeholder_default_literal(defaultValue)) {
        defaults.add(defaultValue.trim());
      }
    }
    for (const child of node.children ?? []) {
      walk(child);
    }
  }
  walk(root);
  return defaults;
}

export function build_behavior_ledger_identity(ledgerDir: string, deviceOsBuild: string): [Array<Record<string, any>>, Record<string, any>] {
  const expectedBuild = String(deviceOsBuild ?? "").trim();
  const files = fs.readdirSync(ledgerDir).filter((f) => f.endsWith(".jsonl")).sort();
  if (!files.length || files.some((f) => !_LEDGER_FILE_RE.test(f))) {
    throw new Error("behavior ledger must contain safely named module jsonl files");
  }
  const rows: Array<Record<string, any>> = [];
  const fileIdentities: Record<string, any> = {};
  for (const fileName of files) {
    const filePath = path.join(ledgerDir, fileName);
    const raw = fs.readFileSync(filePath);
    if (!raw.toString("utf8").trim()) {
      throw new Error(`behavior ledger file is empty: ${fileName}`);
    }
    const parsed: Array<Record<string, any>> = [];
    let lines: string[];
    try {
      lines = raw.toString("utf8").split(/\r?\n/);
    } catch (exc) {
      throw new Error(`behavior ledger file is not utf-8: ${fileName}`);
    }
    for (let lineNumber = 0; lineNumber < lines.length; lineNumber++) {
      const line = lines[lineNumber];
      if (!line.trim()) {
        continue;
      }
      let row: any;
      try {
        row = JSON.parse(line);
      } catch {
        throw new Error(`behavior ledger row is not json: ${fileName}:${lineNumber + 1}`);
      }
      if (typeof row !== "object" || row === null) {
        throw new Error(`behavior ledger row is not an object: ${fileName}:${lineNumber + 1}`);
      }
      const rowBuild = String(row.device_os_build ?? row.build ?? "").trim();
      if (!String(row.command ?? "").trim() || !String(row.status ?? "").trim() || !rowBuild || (!rowBuild.endsWith(`_${expectedBuild}`) && rowBuild !== expectedBuild)) {
        throw new Error(`behavior ledger row identity mismatch: ${fileName}:${lineNumber + 1}`);
      }
      parsed.push({ ...row, _ledger_source_file: fileName, _ledger_line_number: lineNumber + 1 });
    }
    if (!parsed.length) {
      throw new Error(`behavior ledger file has no records: ${fileName}`);
    }
    rows.push(...parsed);
    fileIdentities[fileName] = { entry_count: parsed.length, sha256: crypto.createHash("sha256").update(raw).digest("hex") };
  }
  return [rows, { schema: "ist.behavior-ledger.identity", device_os_build: expectedBuild, entry_count: rows.length, files: fileIdentities }];
}

function _register(heads: Record<string, any>, head: string, src: string, pmax: number, credentialValues: Set<string>, suppressedHeads: Set<string> | null = null, args: Array<Record<string, any>> | null = null, results: Array<Record<string, any>> | null = null): void {
  if (matching_credential_literal_count(head, credentialValues)) {
    if (suppressedHeads !== null) {
      suppressedHeads.add(head);
    }
    return;
  }
  const e = heads[head];
  if (e === undefined) {
    heads[head] = { src, pmax };
    if (args !== null) {
      heads[head].args = args;
    }
    if (results) {
      heads[head].results = results;
    }
  } else {
    e.pmax = Math.max(e.pmax, pmax);
    if (args !== null && JSON.stringify(e.args) !== JSON.stringify(args)) {
      const variants = e.arg_variants ??= [];
      if (!variants.some((v: any) => JSON.stringify(v) === JSON.stringify(args)) && JSON.stringify(args) !== JSON.stringify(e.args)) {
        variants.push(args);
      }
    }
    if (results) {
      const mergedResults = e.results ??= [];
      for (const result of results) {
        if (!mergedResults.some((r: any) => JSON.stringify(r) === JSON.stringify(result))) {
          mergedResults.push(result);
        }
      }
    }
  }
}

const MANUAL_CATALOG_FAMILIES = ["cli", "app"];

export function resolve_manual_catalog_version(version: string, root?: string): string {
  const base = root ?? _default_manual_root();
  const ver = String(version ?? "").trim();
  if (!ver) {
    throw new Error("manual catalog version resolution requires a version");
  }
  let names: string[];
  try {
    names = fs.readdirSync(base).filter((name) => fs.statSync(path.join(base, name)).isDirectory() && (name === ver || name.startsWith(`${ver}.`))).sort();
  } catch {
    names = [];
  }
  const coupled = names.filter((name) => MANUAL_CATALOG_FAMILIES.some((family) => load_coupled_catalog(name, family, base)[1].status === "ok"));
  if (!coupled.length) {
    throw new Error(`manual_catalog_version_unresolved: ${ver} 在 manual 根下没有任何耦合 catalog 的版本目录（扫描到 ${names}）`);
  }
  if (coupled.length > 1) {
    throw new Error(`manual_catalog_version_ambiguous: ${ver} 命中多个耦合 catalog 的版本目录 ${coupled}，拒绝猜测`);
  }
  return coupled[0];
}

export function catalog_value_domain_index(catalogs: Record<string, Record<string, any>>): Record<string, Array<Record<string, any>>> {
  const index: Record<string, Array<Record<string, any>>> = {};
  for (const catalog of Object.values(catalogs)) {
    const paramsByHead: Record<string, string[]> = {};
    for (const signature of catalog.signatures ?? []) {
      if (typeof signature !== "object" || signature === null) {
        continue;
      }
      const tokens = signature.head_tokens ?? [];
      const headKey = tokens.map((t: any) => String(t)).join(" ").trim().toLowerCase().replace(/\s+/g, " ");
      if (!headKey || headKey in paramsByHead) {
        continue;
      }
      paramsByHead[headKey] = (signature.params ?? []).filter((p: any) => typeof p === "object" && p !== null).map((p: any) => String(p.name ?? "").trim());
    }
    for (const row of catalog.value_domains ?? []) {
      if (typeof row !== "object" || row === null) {
        continue;
      }
      const head = String(row.head ?? "").trim().toLowerCase().replace(/\s+/g, " ");
      if (!head) {
        continue;
      }
      const param = String(row.param ?? "").trim();
      const names = paramsByHead[head] ?? [];
      const matches = names.map((name, pos) => ({ name, pos })).filter(({ name }) => name.toLowerCase() === param.toLowerCase()).map(({ pos }) => pos);
      index[head] ??= [];
      index[head].push({
        param,
        param_index: matches.length === 1 ? matches[0] : null,
        param_count: names.length,
        enums: row.enums ?? [],
        desc: String(row.desc ?? ""),
        src: String(row.src ?? "").trim(),
      });
    }
  }
  return index;
}

function _catalog_enum_members(values: any): string[] {
  if (!Array.isArray(values)) {
    return [];
  }
  const members = values.map((item: any) => String(item).trim()).filter(Boolean);
  if (members.length < 2 || members.length > _ENUM_MAX_MEMBERS) {
    return [];
  }
  if (!members.every((m) => _DOMAIN_LITERAL_RE.test(m))) {
    return [];
  }
  if (members.some((m) => /^\d+\s*-\s*\d+$/.test(m))) {
    return [];
  }
  if (new Set(members.map((m) => m.toLowerCase())).size !== members.length) {
    return [];
  }
  return members;
}

function _load_manual_catalog_side(version: string, manualVersion: string | null, root?: string): [string, Record<string, Record<string, any>>, Record<string, Array<Record<string, any>>>, Record<string, string>, Record<string, Record<string, string>>] {
  const base = root ?? _default_manual_root();
  const resolved = String(manualVersion ?? "").trim() || resolve_manual_catalog_version(version, base);
  const catalogs: Record<string, Record<string, any>> = {};
  const statuses: Record<string, string> = {};
  const identities: Record<string, Record<string, string>> = {};
  for (const family of MANUAL_CATALOG_FAMILIES) {
    const [catalog, verdict] = load_coupled_catalog(resolved, family, base);
    const status = String(verdict.status ?? "");
    statuses[family] = status;
    if (status === "ok") {
      catalogs[family] = catalog!;
      identities[family] = { catalog_sha256: String(verdict.catalog_sha256 ?? ""), md_sha256: String(verdict.md_sha256 ?? "") };
    } else if (status === "md_missing") {
      continue;
    } else {
      throw new Error(`manual catalog 未生效（${status}: ${family}@${resolved}），拒绝生成 vendor 投影: ${String(verdict.detail ?? "")}`);
    }
  }
  if (!Object.keys(catalogs).length) {
    throw new Error(`manual catalog 未生效（no_coupled_family: cli=${statuses.cli}, app=${statuses.app}@${resolved}），拒绝生成 vendor 投影`);
  }
  const claims: Record<string, Record<string, any>> = {};
  for (const family of MANUAL_CATALOG_FAMILIES) {
    const catalog = catalogs[family];
    if (catalog === undefined) {
      continue;
    }
    for (const [head, entry] of Object.entries(catalog_manual_claims(catalog))) {
      claims[head] ??= entry;
    }
  }
  return [resolved, claims, catalog_value_domain_index(catalogs), statuses, identities];
}

function _domain_int(text: string): number | null {
  try {
    return parseInt(String(text).replace(/,/g, ""), 10);
  } catch {
    return null;
  }
}

function _domain_sentences(text: string): string[] {
  return String(text ?? "").split(_SENTENCE_SPLIT_RE).map((s) => s.trim()).filter(Boolean);
}

function _domain_mentions(text: string, words: string[]): boolean {
  const folded = text.toLowerCase();
  return words.some((word) => folded.includes(word));
}

export function parse_enum_alternatives(body: string): string[] {
  const text = String(body ?? "").trim().replace(/[。.;；,，]+$/, "");
  if (!text) {
    return [];
  }
  const normalized = text.replace(_ENUM_SEPARATOR_RE, "\0");
  const parts = normalized.split("\0").map((part) => part.trim().replace(/^["'"'`]+|["'"'`]+$/g, "")).filter(Boolean);
  if (parts.length < 2 || parts.length > _ENUM_MAX_MEMBERS) {
    return [];
  }
  if (!parts.every((p) => _DOMAIN_LITERAL_RE.test(p))) {
    return [];
  }
  if (parts.some((p) => /^\d+\s*-\s*\d+$/.test(p))) {
    return [];
  }
  if (new Set(parts.map((p) => p.toLowerCase())).size !== parts.length) {
    return [];
  }
  return parts;
}

export function parse_xml_help_alternatives(helpText: string): string[] {
  const text = String(helpText ?? "");
  let best: string[] = [];
  for (const match of text.matchAll(_XML_HELP_ALTERNATION_RE)) {
    const members = match[0].split("|").map((part) => part.trim().replace(/\.$/, "")).filter(Boolean);
    if (members.length < _XML_HELP_MIN_ALTERNATIVES) {
      continue;
    }
    if (members.length > _ENUM_MAX_MEMBERS) {
      continue;
    }
    if (!members.every((m) => _DOMAIN_LITERAL_RE.test(m))) {
      continue;
    }
    if (new Set(members.map((m) => m.toLowerCase())).size !== members.length) {
      continue;
    }
    if (members.length > best.length) {
      best = members;
    }
  }
  return best;
}

export function parse_xml_help_union_separator(helpText: string, members: string[]): string {
  const text = String(helpText ?? "");
  if (!text.trim()) {
    return "";
  }
  const foldedMembers = new Set(members.filter((m) => m).map((m) => m.toLowerCase()));
  if (!foldedMembers.size) {
    return "";
  }
  const match = _XML_HELP_UNION_RE.exec(text);
  if (match !== null && match.groups) {
    return match.groups.sep;
  }
  const normalized = text.replace(/\\[nrt]/g, " ");
  for (const candidate of normalized.matchAll(_XML_HELP_UNION_DEFAULT_RE)) {
    const body = candidate.groups?.body ?? "";
    const separators = new Set([...body].filter((c) => !/[a-zA-Z0-9]/.test(c)));
    if (separators.size !== 1) {
      continue;
    }
    const separator = [...separators][0];
    const parts = body.split(separator).map((p) => p.toLowerCase()).filter(Boolean);
    if (parts.length < 2) {
      continue;
    }
    if (new Set(parts).size !== parts.length) {
      continue;
    }
    if (parts.every((p) => /^\d+$/.test(p))) {
      continue;
    }
    if (parts.every((p) => foldedMembers.has(p))) {
      return separator;
    }
  }
  return "";
}

export function help_witnesses_any(helpText: string, values: string[]): boolean {
  const text = String(helpText ?? "");
  if (!text.trim()) {
    return true;
  }
  const folded = text.replace(/\\[nrt]/g, " ").toLowerCase();
  for (const value of values) {
    const literal = String(value ?? "").toLowerCase();
    if (!literal) {
      continue;
    }
    if (new RegExp(`(?<![a-z0-9])${literal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![a-z0-9])`).test(folded)) {
      return true;
    }
  }
  return false;
}

export function parse_xml_argument_limit(limit: string, argType: string): Record<string, any> {
  const match = _XML_LIMIT_RE.exec(String(limit ?? "").trim());
  if (match === null || !match.groups) {
    return {};
  }
  const low = _domain_int(match.groups.lo);
  const high = _domain_int(match.groups.hi);
  if (low === null || high === null || low > high) {
    return {};
  }
  if (_NUMERIC_ARGUMENT_TYPES.has(argType)) {
    return { range: { min: low, max: high } };
  }
  if (argType === "STRING") {
    return { length: { min: low, max: high } };
  }
  return {};
}

export function parse_prose_value_domain(text: string, wholeString: boolean): Record<string, any> {
  const out: Record<string, any> = {};
  const raw = String(text ?? "").trim();
  if (!raw || raw.length > _DOMAIN_MAX_TEXT_CHARS) {
    return out;
  }
  if (wholeString) {
    const match = _RANGE_WHOLE_RE.exec(raw);
    if (match !== null && match.groups && !_domain_mentions(raw, _LENGTH_WORDS)) {
      const low = _domain_int(match.groups.lo);
      const high = _domain_int(match.groups.hi);
      if (low !== null && high !== null && low <= high) {
        return { range: { min: low, max: high } };
      }
    }
    const members = parse_enum_alternatives(raw);
    if (members.length) {
      return { enum: members };
    }
  }
  const candidates: Array<[number, number]> = [];
  const emittable: Array<[number, number]> = [];
  for (const sentence of _domain_sentences(raw)) {
    if (_domain_mentions(sentence, _LENGTH_WORDS)) {
      continue;
    }
    if (!_domain_mentions(sentence, _VALUE_STATEMENT_WORDS)) {
      continue;
    }
    const publishable = !(_domain_mentions(sentence, _ALTERNATION_WORDS) || _domain_mentions(sentence, _CONDITIONAL_WORDS));
    for (const match of sentence.matchAll(_RANGE_CORE_RE)) {
      const low = _domain_int(match.groups?.lo ?? "");
      const high = _domain_int(match.groups?.hi ?? "");
      if (low === null || high === null || low > high) {
        continue;
      }
      if (!candidates.some(([l, h]) => l === low && h === high)) {
        candidates.push([low, high]);
      }
      if (publishable && !emittable.some(([l, h]) => l === low && h === high)) {
        emittable.push([low, high]);
      }
    }
  }
  if (candidates.length === 1 && emittable.length) {
    out.range = { min: emittable[0][0], max: emittable[0][1] };
  }
  for (const sentence of _domain_sentences(raw)) {
    if (!("length" in out)) {
      const match = _LENGTH_RE.exec(sentence);
      if (match !== null && match.groups) {
        const high = _domain_int(match.groups.hi);
        if (high !== null) {
          out.length = { min: 0, max: high };
        }
      }
    }
    if (!("enum" in out)) {
      const match = _ENUM_LEAD_RE.exec(sentence);
      if (match !== null && match.groups) {
        const members = parse_enum_alternatives(match.groups.body);
        if (members.length) {
          out.enum = members;
        }
      }
    }
    if (!("default" in out)) {
      const match = _DEFAULT_RE.exec(sentence);
      if (match !== null && match.groups) {
        const value = match.groups.v.trim().replace(/^["'"'`]+|["'"'`]+$/g, "");
        if (value && _DOMAIN_LITERAL_RE.test(value)) {
          out.default = value;
        }
      }
    }
  }
  return out;
}

export function value_domain_compatible_with_type(domain: Record<string, any>, argType: string): Record<string, any> {
  const kept = { ...domain };
  if ("range" in kept && !_NUMERIC_ARGUMENT_TYPES.has(argType)) {
    delete kept.range;
  }
  if ("length" in kept && !_TEXT_ARGUMENT_TYPES.has(argType)) {
    delete kept.length;
  }
  const members = kept.enum;
  if (Array.isArray(members) && _NUMERIC_ARGUMENT_TYPES.has(argType) && !members.every((m: any) => /^[+-]?\d+$/.test(String(m).trim()))) {
    delete kept.enum;
  }
  return kept;
}

export function footprint_parameter_tables(footprintDir: string): [Record<string, Record<string, any>>, Record<string, number>] {
  const tables: Record<string, Record<string, any>> = {};
  const stats = { files: 0, commands: 0, parameters: 0 };
  let directoryFd: string;
  try {
    directoryFd = open_directory_nofollow(footprintDir, {
      errorType: Error,
      invalid_message: "footprint directory path is invalid",
      unavailable_message: "footprint directory is unavailable",
    });
  } catch {
    return [tables, stats];
  }
  try {
    const names: string[] = [];
    let enumerated = 0;
    for (const entry of fs.readdirSync(footprintDir, { withFileTypes: true })) {
      enumerated += 1;
      if (enumerated > _FOOTPRINT_MAX_FILES) {
        throw new Error("footprint directory entry count exceeds the parser budget");
      }
      if (entry.name.endsWith(".json")) {
        names.push(entry.name);
      }
    }
    names.sort();
    let totalBytes = 0;
    for (const name of names) {
      const raw = read_regular_at_nofollow(directoryFd, name, {
        errorType: Error,
        open_message: "footprint node is unavailable",
        bounds_message: "footprint node exceeds per-file size budget",
        changed_message: "footprint node changed while reading",
        max_bytes: 4 * 1024 * 1024,
        min_bytes: 1,
      }) as Buffer;
      totalBytes += raw.length;
      if (totalBytes > 256 * 1024 * 1024) {
        throw new Error("footprint corpus exceeds the total parser budget");
      }
      let payload: any;
      try {
        payload = JSON.parse(raw.toString("utf8"));
      } catch {
        continue;
      }
      if (typeof payload !== "object" || payload === null) {
        continue;
      }
      stats.files += 1;
      const featureId = String(payload.feature_id ?? name);
      const commands = (payload.cli ?? {}).commands;
      for (const command of Array.isArray(commands) ? commands : []) {
        if (typeof command !== "object" || command === null) {
          continue;
        }
        const text = String(command.catalog_head ?? command.command ?? "");
        if (!text) {
          continue;
        }
        stats.commands += 1;
        let head = text.replace(PLACEHOLDER, " ").replace(ENUM, " ");
        head = head.replace(/\s+/g, " ").trim().toLowerCase().replace(/[_ ]+$/, "").trim();
        const params = (command.parameters ?? []).filter((p: any) => typeof p === "object" && p !== null);
        stats.parameters += params.length;
        if (!head || head in tables || !params.length) {
          continue;
        }
        tables[head] = {
          placeholders: [...text.matchAll(PLACEHOLDER)].map((m) => m[1].trim()),
          params,
          src: `footprint:${featureId}:${String(command.fact_key ?? "")}`,
        };
      }
    }
  } finally {
    // directoryFd is a path string; no fd to close
  }
  return [tables, stats];
}

function _append_claim(bucket: Record<string, any>, kind: string, payload: Record<string, any>, source: string, locator: string): void {
  const claim = { ...payload, source, locator };
  const claims = bucket[kind] ??= [];
  if (!claims.some((c: any) => JSON.stringify(c) === JSON.stringify(claim))) {
    claims.push(claim);
  }
}

function _claims_from_domain(bucket: Record<string, any>, domain: Record<string, any>, source: string, locator: string): void {
  for (const kind of ["enum", "range", "length", "default"]) {
    if (!(kind in domain)) {
      continue;
    }
    const value = domain[kind];
    if (kind === "enum") {
      _append_claim(bucket, kind, { values: [...value] }, source, locator);
    } else if (kind === "default") {
      _append_claim(bucket, kind, { value: String(value) }, source, locator);
    } else {
      _append_claim(bucket, kind, { min: Number(value.min), max: Number(value.max) }, source, locator);
    }
  }
}

function _sorted_claims(bucket: Record<string, any>): Record<string, any> {
  const ordered: Record<string, any> = {};
  for (const kind of ["enum", "union", "range", "length", "default"]) {
    const claims = bucket[kind];
    if (!claims?.length) {
      continue;
    }
    ordered[kind] = [...claims].sort((a, b) => {
      const rankA = _VALUE_DOMAIN_SOURCE_RANK[a.source] ?? 9;
      const rankB = _VALUE_DOMAIN_SOURCE_RANK[b.source] ?? 9;
      if (rankA !== rankB) return rankA - rankB;
      return String(a.locator ?? "").localeCompare(String(b.locator ?? ""));
    });
  }
  return ordered;
}

export function merge_argument_value_domains(headers: Record<string, Record<string, any>>, manualCatalogDomains: Record<string, Array<Record<string, any>>>, footprintTables: Record<string, Record<string, any>>, credentialValues: Set<string>, xmlSensitiveValues: Set<string> = new Set(), helpWitness: Record<string, Record<number, string[]>> | null = null): Record<string, number> {
  const stats: Record<string, number> = {};
  const witness = helpWitness ?? {};
  for (const [head, entry] of Object.entries(headers)) {
    const signatures = [entry.args ?? [], ...(entry.arg_variants ?? [])];
    const validSignatures = signatures.filter((s: any) => Array.isArray(s) && s.length);
    if (!validSignatures.length) {
      continue;
    }
    const catalogRows = manualCatalogDomains[head] ?? [];
    const footprint = footprintTables[head] ?? {};
    for (const signature of validSignatures) {
      const arity = signature.length;
      const buckets: Record<number, Record<string, any>> = {};
      for (const argument of signature) {
        if (typeof argument !== "object" || argument === null) {
          continue;
        }
        const position = Number(argument.position ?? 0);
        const argType = String(argument.type ?? "");
        if (argType === "REDACTED_SENSITIVE") {
          continue;
        }
        const domain = parse_xml_argument_limit(String(argument.limit ?? ""), argType);
        if (Object.keys(domain).length) {
          stats.xml_limit_args = (stats.xml_limit_args ?? 0) + 1;
          _claims_from_domain(buckets[position] ??= {}, domain, "xml_limit", `${entry.src ?? ""}/arguments/arg:${position}/limit`);
        }
      }
      for (const row of catalogRows) {
        const param = String(row.param ?? "").trim().toLowerCase();
        const rawLocator = String(row.src ?? "").trim();
        const locator = rawLocator ? `manual:${rawLocator}` : "";
        const rawParam = String(row.param ?? "");
        const descText = String(row.desc ?? "");
        const members = _catalog_enum_members(row.enums ?? []);
        let domain: Record<string, any>;
        if (!catalog_row_describes_one_parameter(rawParam)) {
          if (members.length && catalog_alternate_row_enum_is_closed_set(rawParam, members, descText)) {
            domain = { enum: members };
          } else {
            stats.manual_catalog_claims_skipped = (stats.manual_catalog_claims_skipped ?? 0) + 1;
            continue;
          }
        } else {
          domain = parse_prose_value_domain(descText, false);
          if (members.length && catalog_enum_is_closed_set(rawParam, members, descText)) {
            domain = { ...domain, enum: members };
          }
        }
        if (!param || !locator || !Object.keys(domain).length) {
          stats.manual_catalog_claims_skipped = (stats.manual_catalog_claims_skipped ?? 0) + 1;
          continue;
        }
        const named = signature.filter((a: any) => typeof a === "object" && a !== null && String(a.name ?? "").trim().toLowerCase() === param);
        const signatureHasNames = signature.some((a: any) => typeof a === "object" && a !== null && String(a.name ?? "").trim());
        let argument: Record<string, any>;
        if (signatureHasNames) {
          if (named.length !== 1) {
            stats.manual_catalog_claims_skipped = (stats.manual_catalog_claims_skipped ?? 0) + 1;
            continue;
          }
          argument = named[0];
        } else {
          const paramIndex = row.param_index;
          const paramCount = Number(row.param_count ?? 0);
          if (paramIndex === null || paramCount !== arity || paramIndex < 0 || paramIndex >= signature.length) {
            stats.manual_catalog_claims_skipped = (stats.manual_catalog_claims_skipped ?? 0) + 1;
            continue;
          }
          argument = signature[paramIndex];
        }
        if (typeof argument !== "object" || argument === null) {
          stats.manual_catalog_claims_skipped = (stats.manual_catalog_claims_skipped ?? 0) + 1;
          continue;
        }
        if (String(argument.type ?? "") === "REDACTED_SENSITIVE") {
          stats.manual_catalog_claims_skipped = (stats.manual_catalog_claims_skipped ?? 0) + 1;
          continue;
        }
        domain = value_domain_compatible_with_type(domain, String(argument.type ?? ""));
        if (!Object.keys(domain).length) {
          stats.manual_catalog_claims_skipped = (stats.manual_catalog_claims_skipped ?? 0) + 1;
          continue;
        }
        stats.manual_catalog_args = (stats.manual_catalog_args ?? 0) + 1;
        _claims_from_domain(buckets[Number(argument.position ?? 0)] ??= {}, domain, "manual_table", locator);
      }
      if (footprint && (footprint.placeholders ?? []).length === arity) {
        const names = (footprint.params ?? []).map((p: any) => String(p.name ?? ""));
        if (JSON.stringify(names) === JSON.stringify(footprint.placeholders)) {
          stats.footprint_aligned_signatures = (stats.footprint_aligned_signatures ?? 0) + 1;
          for (let index = 0; index < footprint.params.length; index++) {
            const item = footprint.params[index];
            const argument = signature[index];
            if (String(argument.type ?? "") === "REDACTED_SENSITIVE") {
              continue;
            }
            let domain = value_domain_compatible_with_type(parse_prose_value_domain(String(item.value_range ?? ""), true), String(argument.type ?? ""));
            const declared = String(item.default ?? "").trim().replace(/^["']+|["']+$/g, "");
            if (declared && _DOMAIN_LITERAL_RE.test(declared)) {
              domain = { ...domain, default: declared };
            }
            if (Object.keys(domain).length) {
              stats.footprint_args = (stats.footprint_args ?? 0) + 1;
              _claims_from_domain(buckets[index + 1] ??= {}, domain, "footprint", `${footprint.src ?? "footprint:"}:${names[index]}`);
            }
          }
        } else {
          stats.footprint_name_mismatch_signatures = (stats.footprint_name_mismatch_signatures ?? 0) + 1;
        }
      } else if (footprint) {
        stats.footprint_arity_mismatch_signatures = (stats.footprint_arity_mismatch_signatures ?? 0) + 1;
      }
      const headWitness = witness[head] ?? {};
      for (const argument of signature) {
        if (typeof argument !== "object" || argument === null) {
          continue;
        }
        const position = Number(argument.position ?? 0);
        const helps = headWitness[position] ?? [];
        let bucket = buckets[position];
        if (bucket) {
          const kept: Array<Record<string, any>> = [];
          for (const claim of bucket.enum ?? []) {
            const members = (claim.values ?? []).map(String);
            if (helps.length && !helps.some((text) => help_witnesses_any(text, members))) {
              stats.enum_claims_without_help_witness = (stats.enum_claims_without_help_witness ?? 0) + 1;
              continue;
            }
            kept.push(claim);
          }
          if (kept.length) {
            bucket.enum = kept;
          } else {
            delete bucket.enum;
          }
        }
        if (String(argument.type ?? "") !== "REDACTED_SENSITIVE") {
          for (const text of helps) {
            const members = parse_xml_help_alternatives(text);
            if (!members.length) {
              continue;
            }
            stats.xml_help_args = (stats.xml_help_args ?? 0) + 1;
            _append_claim(buckets[position] ??= {}, "enum", { values: members }, "xml_help", `${entry.src ?? ""}/arguments/arg:${position}/help`);
          }
          bucket = buckets[position];
          const declaredMembers = (bucket?.enum ?? []).flatMap((claim: any) => (claim.values ?? []).map(String));
          for (const text of helps) {
            const separator = parse_xml_help_union_separator(text, declaredMembers);
            if (!separator) {
              continue;
            }
            stats.xml_help_union_args = (stats.xml_help_union_args ?? 0) + 1;
            _append_claim(buckets[position] ??= {}, "union", { separator }, "xml_help", `${entry.src ?? ""}/arguments/arg:${position}/help`);
          }
          bucket = buckets[position];
        }
        if (!bucket) {
          continue;
        }
        const ordered = _sorted_claims(bucket);
        const serialized = JSON.stringify(ordered);
        if (matching_credential_literal_count(serialized, credentialValues)) {
          stats.suppressed_credential_value_domains = (stats.suppressed_credential_value_domains ?? 0) + 1;
          continue;
        }
        const literals = [
          ...(ordered.enum ?? []).filter((claim: any) => _XML_DERIVED_VALUE_DOMAIN_SOURCES.has(String(claim.source))).flatMap((claim: any) => (claim.values ?? []).map(String)),
          ...(ordered.default ?? []).filter((claim: any) => _XML_DERIVED_VALUE_DOMAIN_SOURCES.has(String(claim.source))).map((claim: any) => String(claim.value ?? "")),
        ];
        if (literals.some((literal) => _xml_sensitive_literal_count(literal, xmlSensitiveValues))) {
          stats.suppressed_xml_default_value_domains = (stats.suppressed_xml_default_value_domains ?? 0) + 1;
          continue;
        }
        if (Object.keys(ordered).length) {
          argument.value_domain = ordered;
          stats.args_with_value_domain = (stats.args_with_value_domain ?? 0) + 1;
          for (const kind of Object.keys(ordered)) {
            stats[`kind_${kind}`] = (stats[`kind_${kind}`] ?? 0) + 1;
          }
        }
      }
    }
  }
  return stats;
}

function _safe_xml_text(value: string, credentialValues: Set<string>, xmlSensitiveValues: Set<string>, redactionCounter: [number]): string {
  const text = String(value ?? "").trim();
  if (!text) {
    return text;
  }
  if (matching_credential_literal_count(text, credentialValues)) {
    redactionCounter[0] += 1;
    return "[redacted by credential closure]";
  }
  if (_xml_sensitive_literal_count(text, xmlSensitiveValues)) {
    redactionCounter[0] += 1;
    return _xml_sensitive_literal_redact(text, xmlSensitiveValues);
  }
  return text;
}

function _assert_headers_have_no_xml_sensitive_literal(headers: Record<string, Record<string, any>>, xmlSensitiveValues: Set<string>): void {
  let hitCount = 0;
  for (const [head, entry] of Object.entries(headers)) {
    hitCount += _xml_sensitive_literal_count(head, xmlSensitiveValues);
    for (const result of entry.results ?? []) {
      if (typeof result === "object" && result !== null) {
        for (const key of ["text", "locator", "operator"]) {
          const value = result[key];
          if (typeof value === "string") {
            hitCount += _xml_sensitive_literal_count(value, xmlSensitiveValues);
          }
        }
      }
    }
    const variants = [entry.args ?? [], ...(entry.arg_variants ?? [])];
    for (const variant of variants) {
      for (const argument of variant) {
        for (const key of ["type", "name", "length", "limit", "help"]) {
          const value = argument[key];
          if (typeof value === "string") {
            hitCount += _xml_sensitive_literal_count(value, xmlSensitiveValues);
          }
        }
        const domain = argument.value_domain ?? {};
        for (const claim of domain.enum ?? []) {
          if (!_XML_DERIVED_VALUE_DOMAIN_SOURCES.has(String(claim.source))) {
            continue;
          }
          for (const member of claim.values ?? []) {
            hitCount += _xml_sensitive_literal_count(String(member), xmlSensitiveValues);
          }
        }
        for (const claim of domain.default ?? []) {
          if (!_XML_DERIVED_VALUE_DOMAIN_SOURCES.has(String(claim.source))) {
            continue;
          }
          hitCount += _xml_sensitive_literal_count(String(claim.value ?? ""), xmlSensitiveValues);
        }
      }
    }
  }
  if (hitCount) {
    throw new Error(`vendor XML sensitive-literal gate rejected projection (matched_literal_count=${hitCount})`);
  }
}

export function parse_vendor_xml(xmlPath: string, deviceBuild: string, credentialValues: Set<string>, xmlBytes?: Buffer, helpWitness?: Record<string, Record<number, string[]>>): [Record<string, Record<string, any>>, Record<string, any>] {
  if (!credentialValues.size) {
    throw new Error("credential closure is empty; refusing to parse vendor XML");
  }
  let raw = xmlBytes;
  if (raw === undefined) {
    raw = read_regular_nofollow(xmlPath, {
      errorType: Error,
      invalid_message: "vendor XML path is invalid",
      directory_message: "vendor XML directory is unavailable",
      open_message: "vendor XML is unavailable",
      bounds_message: "vendor XML exceeds size budget",
      changed_message: "vendor XML changed while reading",
      max_bytes: 16 * 1024 * 1024,
      min_bytes: 1,
    }) as Buffer;
  }
  preflight_command_tree_xml(raw, 16 * 1024 * 1024, Error as unknown as ErrorConstructor);
  const xmlText = raw.toString("utf8");
  const xmlSensitiveValues = xml_default_value_closure(raw);
  const heads: Record<string, Record<string, any>> = {};
  const suppressedHeads = new Set<string>();
  const argTypes: Record<string, number> = {};
  const redactions: [number] = [0];
  let itemCount = 0;
  let argCount = 0;
  let defaultCount = 0;
  let missingType = 0;
  let resultDeclarationCount = 0;

  function xml_default_value_closure_from_text(text: string): Set<string> {
    const defaults = new Set<string>();
    const argRe = /<arg\s+[^>]*>/g;
    let match: RegExpExecArray | null;
    while ((match = argRe.exec(text)) !== null) {
      const tag = match[0];
      const nameMatch = /name="([^"]*)"/.exec(tag);
      const typeMatch = /type="([^"]*)"/.exec(tag);
      const helpMatch = /help_string="([^"]*)"/.exec(tag);
      const defaultMatch = /default_value="([^"]*)"/.exec(tag);
      if (defaultMatch && is_credential_argument({ name: nameMatch?.[1], arg_type: typeMatch?.[1], help_string: helpMatch?.[1] }) && !is_placeholder_default_literal(defaultMatch[1].trim())) {
        defaults.add(defaultMatch[1].trim());
      }
    }
    return defaults;
  }

  function walk(xmlText: string, words: string[], xmlPathParts: string[]): void {
    const scopeRe = /<(?:scope|menu)\s+name="([^"]*)"[^>]*>/g;
    const itemRe = /<item\s+[^>]*name="([^"]*)"[^>]*>([\s\S]*?)<\/item>/g;
    let match: RegExpExecArray | null;
    while ((match = itemRe.exec(xmlText)) !== null) {
      itemCount += 1;
      const itemName = match[1].trim().toLowerCase().replace(/\s+/g, " ");
      const head = [...words, ...(itemName ? [itemName] : [])].join(" ").trim();
      const itemBody = match[2];
      const argsMatch = /<arguments>([\s\S]*?)<\/arguments>/.exec(itemBody);
      const argSchema: Array<Record<string, any>> = [];
      if (argsMatch) {
        const argRe = /<arg\s+[^>]*>/g;
        let argMatch: RegExpExecArray | null;
        let pos = 1;
        while ((argMatch = argRe.exec(argsMatch[1])) !== null) {
          argCount += 1;
          const tag = argMatch[0];
          const typeMatch = /type="([^"]*)"/.exec(tag);
          const typ = typeMatch?.[1] ?? "";
          argTypes[typ || "<missing>"] = (argTypes[typ || "<missing>"] ?? 0) + 1;
          if (!typ) missingType += 1;
          const defaultMatch = /default_value="([^"]*)"/.exec(tag);
          if (defaultMatch?.[1]?.trim()) defaultCount += 1;
          const schema: Record<string, any> = { position: pos, type: typ, optional: /optional="YES"/i.test(tag) };
          if (helpWitness) {
            const helpMatch = /help_string="([^"]*)"/.exec(tag);
            const witnessHelp = helpMatch?.[1] ?? "";
            if (witnessHelp) {
              helpWitness[head] ??= {};
              helpWitness[head][pos] ??= [];
              if (!helpWitness[head][pos].includes(witnessHelp)) {
                helpWitness[head][pos].push(witnessHelp);
              }
            }
          }
          const nameMatch = /name="([^"]*)"/.exec(tag);
          const helpMatch = /help_string="([^"]*)"/.exec(tag);
          if (is_credential_argument({ name: nameMatch?.[1], arg_type: typ, help_string: helpMatch?.[1] })) {
            schema.type = "REDACTED_SENSITIVE";
            schema.executable = false;
            redactions[0] += 1;
          } else {
            for (const [attr, key] of [["name", "name"], ["length", "length"], ["limit", "limit"], ["help_string", "help"]] as const) {
              const attrMatch = new RegExp(`${attr}="([^"]*)"`).exec(tag);
              const safe = _safe_xml_text(attrMatch?.[1] ?? "", credentialValues, xmlSensitiveValues, redactions);
              if (safe) {
                schema[key] = safe;
              }
            }
          }
          argSchema.push(schema);
          pos += 1;
        }
      }
      const srcPath = [...xmlPathParts, ...(itemName ? [itemName] : [])].join("/");
      const resultDeclarations: Array<Record<string, any>> = [];
      const resultsMatch = /<results>([\s\S]*?)<\/results>/.exec(itemBody);
      if (resultsMatch) {
        const resultRe = /<result(?:\s+operator="([^"]*)")?>([^<]*)<\/result>/g;
        let resultMatch: RegExpExecArray | null;
        let resultIndex = 1;
        while ((resultMatch = resultRe.exec(resultsMatch[1])) !== null) {
          const rawResult = resultMatch[2].trim();
          if (!rawResult) continue;
          const operator = resultMatch[1]?.trim() ?? "";
          const safeResult = _safe_xml_text(rawResult, credentialValues, xmlSensitiveValues, redactions);
          if (safeResult !== rawResult) {
            throw new Error("vendor XML result declaration intersects credential closure");
          }
          const declaration: Record<string, any> = { text: safeResult, locator: `vendor_xml:${deviceBuild}:${srcPath}/results/result:${resultIndex}` };
          const safeOperator = _safe_xml_text(operator, credentialValues, xmlSensitiveValues, redactions);
          if (safeOperator) {
            declaration.operator = safeOperator;
          }
          resultDeclarations.push(declaration);
          resultDeclarationCount += 1;
          resultIndex += 1;
        }
      }
      if (_xml_sensitive_literal_count(head, xmlSensitiveValues)) {
        suppressedHeads.add(head);
        continue;
      }
      _register(heads, head, `vendor_xml:${deviceBuild}:${srcPath}`, argSchema.length, credentialValues, suppressedHeads, argSchema, resultDeclarations);
    }
  }

  walk(xmlText, [], []);
  _assert_headers_have_no_xml_sensitive_literal(heads, xmlSensitiveValues);
  const schemaVariants = Object.values(heads).reduce((sum, v) => sum + (v.arg_variants?.length ?? 0), 0);
  const stats = {
    items: itemCount,
    arguments: argCount,
    unique_heads: Object.keys(heads).length,
    argument_types: Object.fromEntries(Object.entries(argTypes).sort(([a], [b]) => a.localeCompare(b))),
    missing_argument_type: missingType,
    default_values_omitted: defaultCount,
    credential_fields_redacted: redactions[0],
    suppressed_known_credential_heads: suppressedHeads.size,
    duplicate_head_schema_variants: schemaVariants,
    result_declarations: resultDeclarationCount,
    parameter_schema_coverage: argCount ? Math.round((argCount - missingType) / argCount * 1000000) / 1000000 : 1.0,
  };
  return [heads, stats];
}

export function diff_vendor_stdlibs(oldPayload: Record<string, any>, newPayload: Record<string, any>): Record<string, any> {
  const oldHeaders = oldPayload.headers ?? {};
  const newHeaders = newPayload.headers ?? {};
  const oldNames = new Set(Object.keys(oldHeaders));
  const newNames = new Set(Object.keys(newHeaders));
  const changed: Array<Record<string, any>> = [];
  for (const head of [...oldNames].filter((n) => newNames.has(n)).sort()) {
    const oldSchema = { pmax: oldHeaders[head].pmax, args: oldHeaders[head].args ?? [], arg_variants: oldHeaders[head].arg_variants ?? [] };
    const newSchema = { pmax: newHeaders[head].pmax, args: newHeaders[head].args ?? [], arg_variants: newHeaders[head].arg_variants ?? [] };
    if (JSON.stringify(oldSchema) !== JSON.stringify(newSchema)) {
      changed.push({ head, from: oldSchema, to: newSchema });
    }
  }
  return {
    schema: "ist.vendor_stdlib.diff",
    from: { version: String(oldPayload.version ?? ""), device_os_build: String(oldPayload.device_os_build ?? ""), source_sha256: String(oldPayload.source?.sha256 ?? "") },
    to: { version: String(newPayload.version ?? ""), device_os_build: String(newPayload.device_os_build ?? ""), source_sha256: String(newPayload.source?.sha256 ?? "") },
    added_headers: [...newNames].filter((n) => !oldNames.has(n)).sort(),
    removed_headers: [...oldNames].filter((n) => !newNames.has(n)).sort(),
    changed_argument_schemas: changed,
    stats: { added: newNames.size - [...newNames].filter((n) => oldNames.has(n)).length, removed: oldNames.size - [...oldNames].filter((n) => newNames.has(n)).length, changed_argument_schemas: changed.length },
  };
}

function _assert_payload_has_no_known_credential(payload: Record<string, any>, credentialValues: Set<string>): void {
  const serialized = JSON.stringify(payload);
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount) {
    throw new Error(`command inventory credential closure gate rejected payload (matched_literal_count=${hitCount})`);
  }
}

function _write_payload_atomic(filePath: string, payload: Record<string, any>): void {
  const raw = Buffer.from(JSON.stringify(payload, null, 1) + "\n", "utf8");
  atomic_write_bytes_nofollow(filePath, raw, {
    errorType: Error,
    invalid_message: "vendor projection path is invalid",
    unavailable_message: "vendor projection cannot be published atomically",
  });
}

function _sync_sibling_command_tree_xml(outputDir: string, deviceBuild: string, sourceXml: string, sourceRaw: Buffer): void {
  const sibling = path.join(outputDir, `cmdtree_${deviceBuild}.xml`);
  try {
    if (path.resolve(sibling) === path.resolve(sourceXml)) {
      return;
    }
  } catch {
    // ignore
  }
  if (fs.statSync(sibling).isFile() && !fs.lstatSync(sibling).isSymbolicLink()) {
    let existing: Buffer | null = null;
    try {
      existing = read_regular_nofollow(sibling, {
        errorType: Error,
        invalid_message: "sibling vendor XML path is invalid",
        directory_message: "sibling vendor XML directory is unavailable",
        open_message: "sibling vendor XML is unavailable",
        bounds_message: "sibling vendor XML exceeds size budget",
        changed_message: "sibling vendor XML changed while reading",
        max_bytes: 16 * 1024 * 1024,
        min_bytes: 1,
      }) as Buffer | null;
    } catch {
      existing = null;
    }
    if (existing !== null && existing.equals(sourceRaw)) {
      return;
    }
  }
  atomic_write_bytes_nofollow(sibling, sourceRaw, {
    errorType: Error,
    invalid_message: "sibling vendor XML path is invalid",
    unavailable_message: "sibling vendor XML cannot be published atomically",
  });
}

export function generate_vendor_stdlib_projection(options: { version: string; device_build: string; xml_path: string; output_dir?: string; manual_version?: string | null; manual_root?: string; footprint_dir?: string; credential_values?: Set<string> }): Record<string, any> {
  const ver = String(options.version ?? "").trim();
  const build = String(options.device_build ?? "").trim();
  const sourceXml = options.xml_path;
  if (!ver || !build) {
    throw new Error("version and device_build are required");
  }
  if (path.basename(sourceXml) !== `cmdtree_${build}.xml`) {
    throw new Error("vendor XML filename must match the requested device build");
  }
  const sourceRaw = read_regular_nofollow(sourceXml, {
    errorType: Error,
    invalid_message: "vendor XML path is invalid",
    directory_message: "vendor XML directory is unavailable",
    open_message: "vendor XML is unavailable",
    bounds_message: "vendor XML exceeds size budget",
    changed_message: "vendor XML changed while reading",
    max_bytes: 16 * 1024 * 1024,
    min_bytes: 1,
  }) as Buffer;
  let values = options.credential_values;
  if (values === undefined) {
    try {
      values = new Set(mirror_credential_literals());
    } catch (exc) {
      throw new Error("credential closure unavailable; refusing to generate inventory");
    }
  }
  if (!values.size) {
    throw new Error("credential closure is empty; refusing to generate inventory");
  }
  const helpWitness: Record<string, Record<number, string[]>> = {};
  const [headers, xmlStats] = parse_vendor_xml(sourceXml, build, values, sourceRaw, helpWitness);
  for (const entry of Object.values(headers)) {
    entry.origin = "vendor_xml";
  }
  const [resolvedManualVersion, manualClaims, manualValueDomains, catalogStatuses, catalogIdentities] = _load_manual_catalog_side(ver, options.manual_version ?? null, options.manual_root);
  const footprints = options.footprint_dir ?? path.join(ROOT, "knowledge", "footprints", "nodes");
  const [footprintTables, footprintStats] = footprint_parameter_tables(footprints);
  let xmlSensitiveValues: Set<string>;
  try {
    xmlSensitiveValues = xml_default_value_closure(sourceRaw);
  } catch {
    throw new Error("vendor XML cannot be parsed");
  }
  const valueDomainStats = merge_argument_value_domains(headers, manualValueDomains, footprintTables, values, xmlSensitiveValues, helpWitness);
  const catalogBase = options.manual_root ?? _default_manual_root();
  const catalogDir = path.join(catalogBase, resolvedManualVersion);
  let manualSourceDir: string;
  try {
    manualSourceDir = path.relative(ROOT, catalogDir);
  } catch {
    manualSourceDir = path.basename(catalogDir);
  }
  const source = { kind: "vendor_command_tree_xml", device_os_build: build, sha256: crypto.createHash("sha256").update(sourceRaw).digest("hex"), filename: path.basename(sourceXml) };
  const stats = {
    vendor_header_count: Object.keys(headers).length,
    vendor_argument_count: Number(xmlStats.arguments ?? 0),
    vendor_parameter_schema_coverage: Number(xmlStats.parameter_schema_coverage ?? 0.0),
    vendor_noise: 0,
    manual_declaration_count: 0,
    manual_bold_lines: 0,
    manual_noise: 0,
    manual_coverage_excl_noise: 0.0,
    manual_shared_with_vendor: Object.keys(manualClaims).filter((h) => h in headers).length,
    default_values_omitted: Number(xmlStats.default_values_omitted ?? 0),
    credential_fields_redacted: Number(xmlStats.credential_fields_redacted ?? 0),
    suppressed_known_credential_headers: Number(xmlStats.suppressed_known_credential_heads ?? 0),
    value_domain: {
      ...Object.fromEntries(Object.entries(valueDomainStats).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, Number(v)])),
      footprint_nodes_read: Number(footprintStats.files ?? 0),
      footprint_commands_read: Number(footprintStats.commands ?? 0),
      footprint_param_tables: Object.keys(footprintTables).length,
      manual_catalog: {
        schema: "ist.manual-command-catalog",
        version: resolvedManualVersion,
        families: catalogStatuses,
        identity: catalogIdentities,
        signature_claims: Object.keys(manualClaims).length,
        value_domain_rows: Object.values(manualValueDomains).reduce((sum, rows) => sum + rows.length, 0),
      },
    },
  };
  const payload = {
    schema: "ist.vendor_stdlib",
    version: ver,
    device_os_build: build,
    source,
    source_dir: manualSourceDir,
    source_glob: "*_cn.catalog.json",
    generator: "scripts/maintenance/build_vendor_stdlib.py",
    projection_policy: projection_policy_identity(),
    stats,
    headers: Object.fromEntries(Object.entries(headers).sort(([a], [b]) => a.localeCompare(b))),
    manual_declarations: {},
  };
  const xmlDefaultHits = projection_xml_default_literal_count(payload, sourceRaw);
  if (xmlDefaultHits) {
    throw new Error(`vendor XML sensitive-literal final gate rejected projection (matched_literal_count=${xmlDefaultHits})`);
  }
  _assert_payload_has_no_known_credential(payload, values);
  const outDir = options.output_dir ?? path.join(ROOT, "knowledge", "data", "compile_ref");
  const out = path.join(outDir, `vendor_stdlib_${ver}_${build}.json`);
  _write_payload_atomic(out, payload);
  _sync_sibling_command_tree_xml(outDir, build, sourceXml, sourceRaw);
  return { path: out, payload, manual_claims: manualClaims, stats };
}

export function manual_version_for_build(version: string, deviceBuild: string): string {
  try {
    const { _product_platform_from_command_tree_partition } = require("../../case_compiler/vendor_stdlib") as any;
    const { parse_build_identity, resolve_active_command_tree } = require("../../sync/command_tree_sync") as any;
    const [product, platform] = _product_platform_from_command_tree_partition(version, deviceBuild);
    if (!product || !platform) {
      return "";
    }
    const active = resolve_active_command_tree({ product, platform, version, device_build: deviceBuild });
    if (active === null) {
      return "";
    }
    return String(parse_build_identity(active.full_version).release ?? "");
  } catch {
    return "";
  }
}

function _parseArgs(argv: string[]): { version: string; xml: string; device_build: string; manual_version: string; compare_with: string } {
  const args = { version: "10.5", xml: "", device_build: "585", manual_version: "", compare_with: "" };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--version" && i + 1 < argv.length) {
      args.version = argv[++i];
    } else if (argv[i] === "--xml" && i + 1 < argv.length) {
      args.xml = argv[++i];
    } else if (argv[i] === "--device-build" && i + 1 < argv.length) {
      args.device_build = argv[++i];
    } else if (argv[i] === "--manual-version" && i + 1 < argv.length) {
      args.manual_version = argv[++i];
    } else if (argv[i] === "--compare-with" && i + 1 < argv.length) {
      args.compare_with = argv[++i];
    }
  }
  return args;
}

export function main(): number {
  const args = _parseArgs(process.argv.slice(2));
  const xmlPath = args.xml || path.join(ROOT, "knowledge", "data", "compile_ref", `cmdtree_${args.device_build}.xml`);
  if (!fs.statSync(xmlPath).isFile()) {
    console.error(`vendor XML not found: ${xmlPath}; pass --xml pointing at the sealed generation cmdtree_${args.device_build}.xml (runtime/command_tree/.../generations/<id>/), not /tmp`);
    return 1;
  }
  let generated: Record<string, any>;
  try {
    generated = generate_vendor_stdlib_projection({
      version: args.version,
      device_build: args.device_build,
      xml_path: xmlPath,
      manual_version: args.manual_version.trim() || manual_version_for_build(args.version, args.device_build) || null,
    });
  } catch (exc) {
    console.error(String(exc));
    return 1;
  }
  const out = generated.path;
  const payload = generated.payload;
  const stats = generated.stats;
  const credentialValues = new Set(mirror_credential_literals());
  const result: Record<string, any> = { out: path.relative(ROOT, out), ...stats };
  if (args.compare_with) {
    let previous: Record<string, any>;
    try {
      previous = JSON.parse(fs.readFileSync(args.compare_with, "utf8"));
    } catch (exc) {
      console.error(`cannot read --compare-with payload: ${exc}`);
      return 1;
    }
    const diff = diff_vendor_stdlibs(previous, payload);
    const previousBuild = String(previous.device_os_build ?? "unknown");
    const diffOut = path.join(ROOT, "knowledge", "data", "compile_ref", `vendor_stdlib_diff_${previousBuild}_${args.device_build}.json`);
    _assert_payload_has_no_known_credential(diff, credentialValues);
    _write_payload_atomic(diffOut, diff);
    result.diff_out = path.relative(ROOT, diffOut);
    result.diff_stats = diff.stats;
  }
  console.log(JSON.stringify(result));
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
