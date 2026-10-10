import crypto from "node:crypto";
import fs from "node:fs";
import nodePath from "node:path";
import os from "node:os";

import { P, PyValueError, reFindall, reSearch, reSplit, reSub } from "../../../_py";
import {
  FileIR,
  IInjectionSyntaxError,
  parse_found_times_cells,
  validate_i_injection_syntax,
} from "../../../case_compiler/case_ir";
import { CommandTreeUnavailable } from "../../compile_engine/engine_errors";
import { acquireLockSync } from "../../../../../platform/index";
import { restrictFilePrivate } from "../../../../../platform/index";

const logger = {
  debug: (..._args: any[]) => {},
  info: (..._args: any[]) => {},
  warning: (..._args: any[]) => {},
};

export const UNREACHABLE_IP_ADMISSION_SCHEMA = "ist.unreachable-ip-admission";
const UNREACHABLE_IP_ADMISSION_FIELDS = new Set(["schema", "author_unreachable_values", "author_ip_literals"]);
const _AUTOID_RE = /^\d{18}$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _MAX_CLAIMS_BYTES = 1024 * 1024;
const _COMMAND_CHANNEL_UNAVAILABLE_DETAIL = "the engine channel that can prove command-tree absence did not produce a durable verdict; that does not prove the commands are supported either";
const COMMAND_NOT_IN_TREE_CODE = "command_not_in_tree";
const COMMAND_TREE_UNAVAILABLE_MESSAGE = `error: command-existence gate — COMMAND_TREE_UNAVAILABLE: ${_COMMAND_CHANNEL_UNAVAILABLE_DETAIL}. This is an engine-side outage, not a case defect: do not reshape commands or expected values around it; stop this case and copy this error verbatim into your reply so the engine can repair the channel.`;
const COMMAND_NOT_IN_TREE_PREAMBLE = "error: command-existence gate — the commands below are absent from the device-build XML command tree, so the device does not support them; no manual/SPEC line reference or dev_help text can pass them. Reshape the case or report the gap:";
const COMMAND_PARAMETER_CONTRACT_CODE = "command_parameter_contract_violation";
const _APV_DISPATCH = new Set(["cmd_primitive", "direct_method_call"]);
export const SSL_CERT_LOAD_KIND = "SSL_CERT_LOAD";
const _SSL_CERT_LOAD_REQUIRED = ["vhost", "bound_object", "cert_group", "pairs"];
const _SSL_CERT_LOAD_PAIR_KEYS = ["key_file", "cert_file"];
const _SSL_CERT_LOAD_OPTIONAL = ["vhost_role", "rootca_file", "interca_file", "crlca_file", "sni_domain"];
const _SSL_CERT_LOAD_PAIR_OPTIONAL = ["sm2_key_type", "sm2_cert_type"];

export interface ReachabilityScope {
  isClosed(kind: string): boolean;
  allowedKinds(): Set<string>;
  asDict(): Record<string, any>;
}

function _scopeKinds(opts: { is_closed?: boolean; kinds?: Set<string> | null } = {}): ReachabilityScope {
  const isClosed = opts.is_closed ?? false;
  const kinds = opts.kinds ?? null;
  return {
    isClosed(kind: string): boolean {
      const normalized = String(kind ?? "").trim().toUpperCase();
      if (!isClosed) return true;
      if (kinds === null) return false;
      return kinds.has(normalized);
    },
    allowedKinds(): Set<string> {
      return new Set(kinds ?? []);
    },
    asDict(): Record<string, any> {
      if (!isClosed) {
        return { mode: "open" };
      }
      return { mode: "closed", kinds: [...(kinds ?? [])].sort() };
    },
  };
}

export function _raw_reachability_scope(): ReachabilityScope {
  return _scopeKinds({ is_closed: false });
}

function accepts_schema(schema: any, prefix: string): boolean {
  const s = String(schema ?? "").trim();
  return s === prefix || s.startsWith(prefix + ".");
}

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _cleanLines(text: any): string[] {
  return reSplit("\\r?\\n", String(text ?? "")).map((line) => String(line).trim()).filter((line) => line);
}

function _safe_output_component(value: string, field = "autoid"): string {
  const _sh = require("../compile_engine/_shared");
  return _sh.safe_output_component(value, { field });
}

function _safe_case_path(value: string, field = "autoid"): [string, P] {
  const _sh = require("../compile_engine/_shared");
  const sub = _safe_output_component(value, field);
  return [sub, new P(String(_sh.outputs_root())).joinpath(sub, "case.xlsx")];
}

function _read_claims_ledger(autoid: string, claimsName: string): Array<Record<string, any>> {
  if (!Array.from(claimsName).every((c) => /[A-Za-z0-9_.-]/.test(c)) || claimsName.includes("/") || claimsName.includes("\\") || !claimsName || claimsName.includes("..")) {
    return [];
  }
  const { read_regular_nofollow } = require("../../../case_compiler/_sealed_io");
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(autoid, claimsName);
  let payload: Buffer;
  try {
    payload = read_regular_nofollow(path._p, {
      errorType: Error,
      invalid_message: "claims ledger path is invalid",
      directory_message: "claims ledger parent is unavailable",
      open_message: "claims ledger is unavailable",
      bounds_message: "claims ledger exceeds its byte budget",
      changed_message: "claims ledger changed while being read",
      max_bytes: _MAX_CLAIMS_BYTES,
      min_bytes: 1,
    }) as Buffer;
  } catch (exc) {
    if ((exc as any)?.code === "ENOENT" || exc instanceof Error) return [];
    return [];
  }
  try {
    const data = JSON.parse(payload.toString("utf8"));
    if (!_isMapping(data)) return [];
    const claims = data.claims;
    return Array.isArray(claims) ? claims : [];
  } catch {
    return [];
  }
}

function _land_claims(autoid: string, claimsName: string, claim: Record<string, any>): boolean {
  if (!Array.from(claimsName).every((c) => /[A-Za-z0-9_.-]/.test(c)) || claimsName.includes("/") || claimsName.includes("\\") || !claimsName || claimsName.includes("..")) {
    return false;
  }
  if (typeof autoid !== "string" || !autoid.trim() || !claim) return false;
  const { atomic_write_bytes_nofollow, lexical_absolute } = require("../../../case_compiler/_sealed_io");
  const _sh = require("../compile_engine/_shared");
  let directory: P;
  try {
    directory = new P(String(_sh.outputs_root())).joinpath(autoid);
  } catch {
    return false;
  }
  const lockPath = directory.joinpath(".claims.lock");
  const lock = acquireLockSync(lockPath._p);
  try {
    const claims = _read_claims_ledger(autoid, claimsName);
    claims.push({ ...claim });
    const payload = Buffer.from(JSON.stringify({ schema: "ist.claims.ledger", autoid, claims }, null, 2) + "\n", "utf8");
    atomic_write_bytes_nofollow(directory.joinpath(claimsName)._p, payload, {
      errorType: Error,
      invalid_message: "claims ledger path is invalid",
      unavailable_message: "claims ledger could not be landed",
      create_parents: true,
      mode: 0o600,
    });
    return true;
  } catch {
    return false;
  } finally {
    lock.release();
  }
}

function _answerer_undetermined_claims(autoid: string): Array<Record<string, any>> {
  const claims = _read_claims_ledger(autoid, "needs_decision.json");
  return claims.filter((claim) => _isMapping(claim) && claim.claim_kind === require("./mechanical_case_submit_tool").ANSWERER_UNDETERMINED_CLAIM_KIND);
}

export function land_answerer_undetermined_claim(autoid: string, claim: Record<string, any>): boolean {
  return _land_claims(autoid, "needs_decision.json", { ...claim, claim_kind: require("./mechanical_case_submit_tool").ANSWERER_UNDETERMINED_CLAIM_KIND });
}

function _loadIntentSpecStatus(autoid: string): string | null {
  const _sh = require("../compile_engine/_shared");
  const intentPath = new P(String(_sh.outputs_root())).joinpath(autoid, "intent.json");
  if (!intentPath.is_file()) return null;
  try {
    const { ContractError, read_intent_json } = require("../../../../ist_emit/contract_entry");
    const [payload] = read_intent_json(intentPath, { trusted_root: String(_sh.outputs_root()) });
    const status = String(payload.governing_spec_status ?? "").trim();
    return status || null;
  } catch {
    return null;
  }
}

function _intentGoverningSpec(autoid: string): [string, string, string, string] {
  const _sh = require("../compile_engine/_shared");
  const intentPath = new P(String(_sh.outputs_root())).joinpath(autoid, "intent.json");
  if (!intentPath.is_file()) return ["", "", "", ""];
  try {
    const { ContractError, read_intent_json } = require("../../../../ist_emit/contract_entry");
    const [payload] = read_intent_json(intentPath, { trusted_root: String(_sh.outputs_root()) });
    return [
      String(payload.governing_spec ?? "").trim(),
      String(payload.governing_spec_sha256 ?? "").trim(),
      String(payload.governing_spec_generation_id ?? "").trim(),
      String(payload.governing_spec_manifest_sha256 ?? "").trim(),
    ];
  } catch {
    return ["", "", "", ""];
  }
}

function _default_reachability_scope(): Record<string, any> {
  return _raw_reachability_scope().asDict();
}

function _scope_from_dict(value: Record<string, any>): ReachabilityScope {
  const mode = String(value.mode ?? "open").trim().toLowerCase();
  if (mode !== "closed") {
    return _raw_reachability_scope();
  }
  const kinds = new Set<string>();
  for (const kind of value.kinds ?? []) {
    kinds.add(String(kind ?? "").trim().toUpperCase());
  }
  return _scopeKinds({ is_closed: true, kinds });
}

function _reachability_scope_from_blocks(blocks: any[], opts: { mechanical_case_sha256?: string } = {}): ReachabilityScope {
  const mechanicalCaseSha256 = opts.mechanical_case_sha256 ?? "";
  if (!Array.isArray(blocks) || !blocks.length) {
    return _raw_reachability_scope();
  }
  if (!mechanicalCaseSha256) {
    return _scopeKinds({ is_closed: true, kinds: null });
  }
  if (!_SHA256_RE.test(mechanicalCaseSha256)) {
    throw new PyValueError("mechanical_case_sha256 must be 64 lowercase hex characters");
  }
  const kinds = new Set<string>();
  for (const block of blocks) {
    if (!_isMapping(block)) continue;
    const kind = String(block.kind ?? "").trim().toUpperCase();
    if (kind) kinds.add(kind);
  }
  if (!kinds.size) {
    throw new PyValueError("blocks do not carry a sealable kind scope");
  }
  return _scopeKinds({ is_closed: true, kinds });
}

function _reachability_scope_from_credential(autoid: string, opts: { xlsx_sha256: string }): [ReachabilityScope | null, string] {
  const xlsxSha256 = opts.xlsx_sha256;
  if (!_SHA256_RE.test(String(xlsxSha256 ?? ""))) {
    return [null, "xlsx_sha256 must be 64 lowercase hex characters"];
  }
  const _sh = require("../compile_engine/_shared");
  const { lexical_absolute, read_regular_nofollow } = require("../../../case_compiler/_sealed_io");
  const credPath = new P(String(_sh.outputs_root())).joinpath(autoid, ".grade_credential.json");
  let payload: Buffer;
  try {
    payload = read_regular_nofollow(credPath._p, {
      errorType: Error,
      invalid_message: "lint credential path is invalid",
      directory_message: "lint credential parent is unavailable",
      open_message: "lint credential is unavailable",
      bounds_message: "lint credential exceeds its byte budget",
      changed_message: "lint credential changed while being read",
      max_bytes: _MAX_CLAIMS_BYTES,
      min_bytes: 1,
    }) as Buffer;
  } catch (exc) {
    return [null, `lint credential is unavailable: ${(exc as any)?.constructor?.name ?? "Error"}`];
  }
  let data: Record<string, any>;
  try {
    data = JSON.parse(payload.toString("utf8"));
  } catch {
    return [null, "lint credential is not valid JSON"];
  }
  if (!_isMapping(data)) {
    return [null, "lint credential is not a JSON object"];
  }
  if (String(data.autoid ?? "") !== String(autoid)) {
    return [null, "lint credential carries another case identity"];
  }
  if (String(data.xlsx_sha256 ?? "") !== xlsxSha256) {
    return [null, "lint credential does not match the current case.xlsx"];
  }
  const scopeValue = data.reachability_scope;
  if (!_isMapping(scopeValue)) {
    return [null, "lint credential has no blocks.kind reachability scope"];
  }
  return [_scope_from_dict(scopeValue), ""];
}

function _is_apv_command_method(f: string): boolean {
  return ["cmd", "cmd_config", "cmds_config"].includes(f);
}

function is_apv_command_step(step: Record<string, any>, opts: { methods?: Iterable<string> | null } = {}): boolean {
  const methods = opts.methods ?? null;
  const e = String(step.E ?? "").trim();
  const f = String(step.F ?? "").trim();
  if (!/^APV_\d+$/.test(e)) return false;
  if (methods === null) return _is_apv_command_method(f);
  return [...methods].includes(f);
}

function _apv_command_lines_for_step(steps: any[], i: number): string[] {
  const { strip_apv_command_kwargs } = require("../../../case_compiler/excel_contract");
  if (!is_apv_command_step(steps[i], { methods: null })) return [];
  const g = String(steps[i].G ?? "");
  const f = String(steps[i].F ?? "").trim();
  if (f === "cmd_config") {
    return [strip_apv_command_kwargs(g, f)];
  }
  return _cleanLines(g).map((line) => strip_apv_command_kwargs(line, f)).filter((line) => line);
}

function _ordered_apv_command_refs(steps: any[], init: string): Array<Record<string, any>> {
  const refs: Array<Record<string, any>> = [];
  const lines: string[] = [];
  for (const line of _cleanLines(init)) {
    lines.push(line);
  }
  if (lines.length) {
    refs.push({ command: lines.join("\n"), step_index: -1, init_lines: lines });
  }
  for (let i = 0; i < steps.length; i++) {
    const stepLines = _apv_command_lines_for_step(steps, i);
    if (!stepLines.length) continue;
    for (const line of stepLines) {
      refs.push({ command: line, step_index: i });
    }
  }
  return refs;
}

const _DEST_ANCHOR_RE = /(?:@|:\/\/)\[?([0-9A-Fa-f:.]+)\]?/g;

function _dest_of_cmd(cmd: string): string {
  const matches = reFindall(_DEST_ANCHOR_RE.source, String(cmd ?? ""));
  if (!matches.length) return "";
  return String(matches[0]);
}

function _bind_values(authoredValues: Iterable<string>): Set<string> {
  const { normalize_ip_literal } = require("../_shared/env_facts");
  const out = new Set<string>();
  for (const value of authoredValues) {
    const token = normalize_ip_literal(value);
    if (token) out.add(token);
  }
  return out;
}

function _intentional_unreachable_values(provenance: any): Set<string> {
  const { intentional_unreachable_author_values } = require("../../../case_compiler/provenance_ir");
  if (provenance === null || provenance === undefined) return new Set();
  try {
    return new Set(intentional_unreachable_author_values(provenance));
  } catch {
    return new Set();
  }
}

function _unreachable_ip_admission(autoid: string, steps: any[], opts: { init?: string; recorded_author_values?: Iterable<string> | null } = {}): Record<string, any> {
  const init = opts.init ?? "";
  const recordedAuthorValues = opts.recorded_author_values ?? null;
  const { require_env_facts } = require("../_shared/env_facts");
  const { strip_apv_command_kwargs } = require("../../../case_compiler/excel_contract");
  const facts = require_env_facts();
  let candidates = new Set<string>();
  for (const ref of _ordered_apv_command_refs(steps, init)) {
    for (const value of reFindall("\\b\\d{1,3}(?:\\.\\d{1,3}){3}\\b", String(ref.command ?? ""))) {
      if (facts.normalize_ip_literal(value) && !facts.declared(value)) {
        candidates.add(String(value));
      }
    }
  }
  if (!candidates.size) {
    return { schema: UNREACHABLE_IP_ADMISSION_SCHEMA, author_unreachable_values: [], author_ip_literals: [] };
  }
  let authored = new Set<string>();
  if (recordedAuthorValues !== null) {
    authored = _bind_values(recordedAuthorValues);
  } else {
    const _sh = require("../compile_engine/_shared");
    const { lexical_absolute, read_regular_nofollow } = require("../../../case_compiler/_sealed_io");
    const intentPath = new P(String(_sh.outputs_root())).joinpath(autoid, "intent.json");
    if (intentPath.is_file()) {
      try {
        const { ContractError, read_intent_json } = require("../../../../ist_emit/contract_entry");
        const [intent] = read_intent_json(intentPath, { trusted_root: String(_sh.outputs_root()) });
        const entries: any[] = [];
        if (_isMapping(intent) && Array.isArray(intent.steps)) {
          for (const step of intent.steps) entries.push(step);
        }
        if (_isMapping(intent) && Array.isArray(intent.provenance)) {
          for (const step of intent.provenance) entries.push(step);
        }
        for (const step of entries) {
          if (!_isMapping(step)) continue;
          const source = step.source;
          if (!_isMapping(source)) continue;
          const kind = String(source.kind ?? "").trim();
          if (kind !== "author_claim" && kind !== "spec_claim") continue;
          const ref = String(source.ref ?? "");
          const locators = reFindall("\\b\\d{1,3}(?:\\.\\d{1,3}){3}\\b", ref);
          for (const value of locators) {
            if (facts.normalize_ip_literal(value)) authored.add(String(value));
          }
        }
      } catch {
        return { schema: UNREACHABLE_IP_ADMISSION_SCHEMA, author_unreachable_values: [...candidates].sort(), author_ip_literals: [] };
      }
    } else {
      return { schema: UNREACHABLE_IP_ADMISSION_SCHEMA, author_unreachable_values: [...candidates].sort(), author_ip_literals: [] };
    }
  }
  const authorUnreachable = [...candidates].filter((value) => authored.has(value)).sort();
  const authorIpLiterals = [...authored].filter((value) => facts.normalize_ip_literal(value)).sort();
  return { schema: UNREACHABLE_IP_ADMISSION_SCHEMA, author_unreachable_values: authorUnreachable, author_ip_literals: authorIpLiterals };
}

function _recorded_author_unreachable_values(autoid: string, opts: { xlsx_sha256: string }): string[] {
  const xlsxSha256 = opts.xlsx_sha256;
  if (!_SHA256_RE.test(String(xlsxSha256 ?? ""))) return [];
  const _sh = require("../compile_engine/_shared");
  const { read_regular_nofollow } = require("../../../case_compiler/_sealed_io");
  const credPath = new P(String(_sh.outputs_root())).joinpath(autoid, ".grade_credential.json");
  try {
    const payload = read_regular_nofollow(credPath._p, {
      errorType: Error,
      invalid_message: "lint credential path is invalid",
      directory_message: "lint credential parent is unavailable",
      open_message: "lint credential is unavailable",
      bounds_message: "lint credential exceeds its byte budget",
      changed_message: "lint credential changed while being read",
      max_bytes: _MAX_CLAIMS_BYTES,
      min_bytes: 1,
    }) as Buffer;
    const data = JSON.parse(payload.toString("utf8"));
    if (!_isMapping(data)) return [];
    if (String(data.autoid ?? "") !== String(autoid)) return [];
    if (String(data.xlsx_sha256 ?? "") !== xlsxSha256) return [];
    const admission = data.unreachable_ip_admission;
    if (!_isMapping(admission)) return [];
    if (admission.schema !== UNREACHABLE_IP_ADMISSION_SCHEMA) return [];
    const values = admission.author_unreachable_values;
    return Array.isArray(values) ? values.map((v) => String(v)).filter((v) => v) : [];
  } catch {
    return [];
  }
}

function _recorded_author_ip_literals(autoid: string, opts: { xlsx_sha256: string }): string[] {
  const xlsxSha256 = opts.xlsx_sha256;
  if (!_SHA256_RE.test(String(xlsxSha256 ?? ""))) return [];
  const _sh = require("../compile_engine/_shared");
  const { read_regular_nofollow } = require("../../../case_compiler/_sealed_io");
  const credPath = new P(String(_sh.outputs_root())).joinpath(autoid, ".grade_credential.json");
  try {
    const payload = read_regular_nofollow(credPath._p, {
      errorType: Error,
      invalid_message: "lint credential path is invalid",
      directory_message: "lint credential parent is unavailable",
      open_message: "lint credential is unavailable",
      bounds_message: "lint credential exceeds its byte budget",
      changed_message: "lint credential changed while being read",
      max_bytes: _MAX_CLAIMS_BYTES,
      min_bytes: 1,
    }) as Buffer;
    const data = JSON.parse(payload.toString("utf8"));
    if (!_isMapping(data)) return [];
    if (String(data.autoid ?? "") !== String(autoid)) return [];
    if (String(data.xlsx_sha256 ?? "") !== xlsxSha256) return [];
    const admission = data.unreachable_ip_admission;
    if (!_isMapping(admission)) return [];
    if (admission.schema !== UNREACHABLE_IP_ADMISSION_SCHEMA) return [];
    const values = admission.author_ip_literals;
    return Array.isArray(values) ? values.map((v) => String(v)).filter((v) => v) : [];
  } catch {
    return [];
  }
}

function _gate_unreachable_ips(autoid: string, steps: any[], opts: { init?: string; recorded_author_values?: Iterable<string> | null } = {}): string {
  const admission = _unreachable_ip_admission(autoid, steps, { init: opts.init ?? "", recorded_author_values: opts.recorded_author_values ?? null });
  const values = [...(admission.author_unreachable_values ?? [])];
  if (!values.length) return "";
  const reported = values.slice(0, 20).join(", ");
  return (
    `the case queries ${values.length} IP(s) not declared in the bed topology (${reported}) — the address is written verbatim in the sealed Author case, so this is an execution-environment disclosure, not a case rejection: the case proceeds and the limitation is reported; expected is not rewritten.`
  );
}

function _gate_unreachable_listener(autoid: string, steps: any[], opts: { init?: string; reachability_scope?: any; author_ip_literals?: Iterable<string> | null } = {}): string {
  const { require_env_facts } = require("../_shared/env_facts");
  const { strip_apv_command_kwargs } = require("../../../case_compiler/excel_contract");
  const facts = require_env_facts();
  const scope = opts.reachability_scope ?? _raw_reachability_scope();
  const authorSet = _bind_values(opts.author_ip_literals ?? []);
  const lines: string[] = [];
  for (const ref of _ordered_apv_command_refs(steps, opts.init ?? "")) {
    const cmd = String(ref.command ?? "").trim();
    if (!cmd) continue;
    if (!/^(?:curl|dig|nslookup|ping|traceroute|tracepath|mtr)\b/i.test(cmd)) continue;
    const dest = _dest_of_cmd(cmd);
    if (!dest || !facts.normalize_ip_literal(dest)) continue;
    if (facts.declared(dest)) continue;
    if (authorSet.size && authorSet.has(facts.normalize_ip_literal(dest))) continue;
    const kind = scope.isClosed("OBSERVE_ASSERT") ? "" : "OBSERVE_ASSERT";
    lines.push(`step[${ref.step_index}]: ${cmd} targets ${dest}, which is in no declared segment of this bed and is not an Author-written address — the query can never reach it.`);
  }
  return lines.join("\n");
}

function _gate_driver_reachability(autoid: string, steps: any[], opts: { author_ip_literals?: Iterable<string> | null } = {}): string {
  const { require_env_facts } = require("../_shared/env_facts");
  const facts = require_env_facts();
  const authorSet = _bind_values(opts.author_ip_literals ?? []);
  const failures: string[] = [];
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (!_isMapping(s)) continue;
    const e = String(s.E ?? "").trim();
    if (!/^APV_\d+$/.test(e)) continue;
    const g = String(s.G ?? "");
    const dest = _dest_of_cmd(g);
    if (!dest || !facts.normalize_ip_literal(dest)) continue;
    if (facts.declared(dest)) continue;
    if (authorSet.size && authorSet.has(facts.normalize_ip_literal(dest))) continue;
    failures.push(`step[${i}] ${e} queries ${dest}, which is in no declared segment of this bed.`);
  }
  return failures.join("\n");
}

const _SHELL_WORDING_RE = /(?:^\s*\/|(?:^|\s)(?:bash|sh|zsh|python\d*|perl|ruby|systemctl|journalctl|netstat|ss|grep|awk|sed|cat|tail|head)\b|\|\s*(?:grep|awk|sed)\b|>\s*\/)/i;

function _looks_like_shell(command: string): boolean {
  return _SHELL_WORDING_RE.test(String(command ?? ""));
}

interface CommandTreeContext {
  build: string;
  stdlib: any;
  inventory: any;
}

const _commandTreeContextCache = new Map<string, CommandTreeContext>();

function _command_tree_context(opts: { device_build?: string } = {}): CommandTreeContext {
  const deviceBuild = String(opts.device_build ?? "").trim();
  const cached = _commandTreeContextCache.get(deviceBuild);
  if (cached) return cached;
  const { load_vendor_stdlib } = require("../../../case_compiler/vendor_stdlib");
  const inventory = load_vendor_stdlib("", deviceBuild);
  const stdlib = { inventory, recorded_command_heads: require("../worker_device_context").recorded_command_heads };
  const context: CommandTreeContext = { build: deviceBuild, stdlib, inventory };
  if (_commandTreeContextCache.size >= 8) {
    const firstKey = _commandTreeContextCache.keys().next().value;
    if (firstKey !== undefined) _commandTreeContextCache.delete(firstKey);
  }
  _commandTreeContextCache.set(deviceBuild, context);
  return context;
}

interface CommandExistenceVerdict {
  kind: "hit" | "missing" | "tree_unavailable";
  head: string;
  device_build: string;
  parameter_error?: string;
  parameters_valid?: boolean;
  detail?: string;
}

function command_existence_verdict(command: string, opts: { device_build?: string; _loaded_context?: CommandTreeContext } = {}): CommandExistenceVerdict {
  const deviceBuild = String(opts.device_build ?? "").trim();
  const context = opts._loaded_context ?? _command_tree_context({ device_build: deviceBuild });
  const inventory = context.inventory;
  if (inventory === null || inventory === undefined) {
    return { kind: "tree_unavailable", head: command, device_build: deviceBuild, detail: "command tree projection could not be loaded" };
  }
  const inventoryBuild = String(inventory.device_os_build ?? "").trim();
  if (inventoryBuild && deviceBuild && inventoryBuild !== deviceBuild) {
    return { kind: "tree_unavailable", head: command, device_build: deviceBuild, detail: "command tree identity does not match the bound build" };
  }
  const { norm_command_tokens, recorded_next_tokens_after_shared_prefix } = require("../../../case_compiler/vendor_stdlib");
  const tokens = norm_command_tokens(command);
  if (!tokens.length) {
    return { kind: "missing", head: command, device_build: deviceBuild };
  }
  const headers = inventory.headers ?? {};
  const heads = inventory.heads ?? {};
  let matchedHead = "";
  let matchedLength = 0;
  for (let k = Math.min(tokens.length, 8); k >= 1; k--) {
    const candidate = tokens.slice(0, k).join(" ");
    if (candidate in heads || candidate in headers) {
      matchedHead = candidate;
      matchedLength = k;
      break;
    }
  }
  if (!matchedHead) {
    return { kind: "missing", head: tokens.slice(0, Math.min(tokens.length, 2)).join(" ") || command, device_build: deviceBuild };
  }
  const headEntry = heads[matchedHead];
  if (headEntry && Array.isArray(headEntry.args) && headEntry.args.length) {
    const required = headEntry.args.filter((a: any) => !a.optional).length;
    const remaining = tokens.length - matchedLength;
    if (remaining < required) {
      return { kind: "hit", head: matchedHead, device_build: deviceBuild, parameters_valid: false, parameter_error: `command head ${matchedHead} requires at least ${required} argument(s) but only ${remaining} token(s) follow` };
    }
  }
  return { kind: "hit", head: matchedHead, device_build: deviceBuild, parameters_valid: true };
}

function _verified_precedent_commands(case_: any): Set<string> {
  const commands = new Set<string>();
  if (case_ === null || case_ === undefined) return commands;
  try {
    const steps = case_.steps ?? [];
    for (const step of steps) {
      if (!_isMapping(step)) continue;
      const source = step.source;
      if (!_isMapping(source)) continue;
      if (String(source.kind ?? "").trim() !== "precedent") continue;
      const ref = String(source.ref ?? "").trim();
      if (!ref) continue;
      commands.add(ref);
    }
  } catch {}
  return commands;
}

function _gate_command_existence(autoid: string, steps: any[], opts: { init?: string; evidence?: string; device_build?: string; precedent_passes?: Set<string>; inventory?: any; capability_receipt?: any } = {}): string {
  const deviceBuild = String(opts.device_build ?? "").trim();
  const precedentPasses = opts.precedent_passes ?? new Set();
  const inventory = opts.inventory ?? null;
  const capabilityReceipt = opts.capability_receipt ?? null;
  const commandRefs = _ordered_apv_command_refs(steps, opts.init ?? "");
  if (!commandRefs.length) return "";
  const loadedContext = _command_tree_context({ device_build: deviceBuild });
  const missing: string[] = [];
  const parameterErrors: string[] = [];
  for (const ref of commandRefs) {
    const command = String(ref.command ?? "");
    const verdict = command_existence_verdict(command, { device_build: deviceBuild, _loaded_context: loadedContext });
    if (verdict.kind === "tree_unavailable") {
      throw new CommandTreeUnavailable(String(verdict.detail ?? ""), { device_build: verdict.device_build || deviceBuild });
    }
    if (verdict.kind === "hit" && !verdict.parameters_valid) {
      parameterErrors.push(`step[${ref.step_index}]: ${command} — ${verdict.parameter_error}`);
      continue;
    }
    if (verdict.kind === "missing") {
      if (precedentPasses.has(command)) continue;
      missing.push(`step[${ref.step_index}]: ${command}`);
    }
  }
  if (parameterErrors.length) {
    return `${COMMAND_PARAMETER_CONTRACT_CODE}: the following commands violate the build-bound XML parameter contract:\n  - ${parameterErrors.slice(0, 20).join("\n  - ")}\nRe-read the exact XML-backed signature and correct these commands before sealing.`;
  }
  if (missing.length) {
    return `${COMMAND_NOT_IN_TREE_PREAMBLE}\n  - ${missing.slice(0, 20).join("\n  - ")}`;
  }
  return "";
}

function _gate_tau_coverage(autoid: string, steps: any[], opts: { init?: string; device_build?: string } = {}): string {
  const init = String(opts.init ?? "").trim();
  if (!init) return "";
  const { load_grammar } = require("../../../case_compiler/domain_grammar");
  let grammar: any;
  try {
    grammar = load_grammar();
  } catch {
    return "";
  }
  const tauRules = grammar.tau_coverage ?? {};
  const patterns = tauRules.patterns ?? [];
  if (!patterns.length) return "";
  const initLines = _cleanLines(init);
  const failures: string[] = [];
  for (const rule of patterns) {
    const pattern = String(rule.pattern ?? "");
    const message = String(rule.message ?? "");
    let matched = false;
    for (const line of initLines) {
      try {
        if (new RegExp(pattern, "i").test(line)) {
          matched = true;
          break;
        }
      } catch {
        continue;
      }
    }
    if (!matched) {
      failures.push(message || `init missing required tau coverage pattern ${pattern}`);
    }
  }
  return failures.join("\n");
}

function _gate_sleep_budget(autoid: string, steps: any[]): string {
  const { load_grammar } = require("../../../case_compiler/domain_grammar");
  let grammar: any;
  try {
    grammar = load_grammar();
  } catch {
    return "";
  }
  const budget = Number((grammar.sleep_budget ?? {}).max_seconds ?? 0);
  if (!budget || budget <= 0) return "";
  let total = 0;
  for (const s of steps) {
    if (!_isMapping(s)) continue;
    if (String(s.E ?? "").trim() !== "time") continue;
    if (String(s.F ?? "").trim() !== "sleep") continue;
    const raw = s.G;
    const value = Number(raw);
    if (Number.isFinite(value) && value > 0) {
      total += value;
    }
  }
  if (total > budget) {
    return `sleep budget exceeded: total sleep time ${total}s exceeds the per-case budget of ${budget}s (domain_grammar.sleep_budget). Remove or shorten sleep steps.`;
  }
  return "";
}

function _intent_save_variant(autoid: string): string {
  const _sh = require("../compile_engine/_shared");
  const intentPath = new P(String(_sh.outputs_root())).joinpath(autoid, "intent.json");
  if (!intentPath.is_file()) return "";
  try {
    const { ContractError, read_intent_json } = require("../../../../ist_emit/contract_entry");
    const [payload] = read_intent_json(intentPath, { trusted_root: String(_sh.outputs_root()) });
    return String(payload.expected_save_variant ?? "").trim().toLowerCase();
  } catch {
    return "";
  }
}

function persistence_path_kind(token: string): string | null {
  const { load_grammar } = require("../../../case_compiler/domain_grammar");
  let grammar: any;
  try {
    grammar = load_grammar();
  } catch {
    return null;
  }
  const channels = grammar.persistence_channels ?? {};
  for (const [kind, ch] of Object.entries<any>(channels)) {
    if (String(kind).startsWith("_") || !ch || typeof ch !== "object") continue;
    for (const pattern of ch.patterns || []) {
      try {
        if (new RegExp(String(pattern), "i").test(token)) return String(kind);
      } catch {}
    }
  }
  return null;
}

function parse_persistence_target(command: string): [string, string, string] | null {
  const cmd = String(command ?? "").trim();
  const lower = cmd.toLowerCase();
  const saveStems = ["write memory", "write file", "write all", "write net", "write"];
  const verifyStems = ["show startup", "show saved", "show config", "show running"];
  for (const stem of saveStems) {
    if (lower.startsWith(stem)) {
      const tail = cmd.slice(stem.length).trim();
      const token = tail.split(/\s+/)[0] ?? "";
      const pathKind = token ? (persistence_path_kind(token) ?? "") : "";
      return ["save", pathKind, tail];
    }
  }
  for (const stem of verifyStems) {
    if (lower.startsWith(stem)) {
      const tail = cmd.slice(stem.length).trim();
      return ["verify", tail ? (persistence_path_kind(tail.split(/\s+/)[0]) ?? "") : "", tail];
    }
  }
  return null;
}

function _persistence_config_cmds(command: string): string[] {
  const { load_grammar } = require("../../../case_compiler/domain_grammar");
  let grammar: any;
  try {
    grammar = load_grammar();
  } catch {
    return [];
  }
  return (grammar.persistence ?? {}).config_cmds ?? [];
}

function _persistence_operation_terms(kind: string): string[] {
  const { load_grammar } = require("../../../case_compiler/domain_grammar");
  let grammar: any;
  try {
    grammar = load_grammar();
  } catch {
    return [];
  }
  return (grammar.persistence ?? {}).operations?.[kind] ?? [];
}




function _per_cmd_save_variant(cmd: string): string {
  const { stemMatch } = require("../../../case_compiler/case_ir");
  const stem = stemMatch(cmd);
  if (!stem) return "";
  if (stem === "write memory") return "memory";
  if (stem === "write file") return "file";
  if (stem === "write all") return "all";
  if (stem === "write net") return "net";
  return "";
}


function _gate_save_restore_pairing(autoid: string, steps: any[], opts: { init?: string; expected_save_variant?: string } = {}): string {
  const init = String(opts.init ?? "");
  const expectedSaveVariant = String(opts.expected_save_variant ?? "").trim().toLowerCase();
  const { normalize_ip_literal, require_env_facts } = require("../_shared/env_facts");
  const facts = require_env_facts();
  const configCmds = _persistence_config_cmds(init);
  const observedSave = new Set<string>();
  const observedVerify = new Set<string>();
  const savePathKinds = new Set<string>();
  const verifyPathKinds = new Set<string>();
  const saveNetTargets = new Set<string>();
  const verifyNetTargets = new Set<string>();
  const failures: string[] = [];

  const consider = (command: string, origin: string): void => {
    const parsed = parse_persistence_target(command);
    if (parsed === null) return;
    const [kind, pathKind, target] = parsed;
    const operations = _persistence_operation_terms(kind);
    if (!operations.length) return;
    if (pathKind === "management_net" && target) {
      const t = String(target);
      const [a, b] = t.split(/\s+/);
      for (const ip of [a, b]) {
        if (ip && !facts.declared(ip) && !normalize_ip_literal(ip)) {
          failures.push(`${origin}: '${command}' net target ${ip} is not a declared bed IP nor a valid IP literal`);
        }
      }
    }
    if (kind === "save") {
      observedSave.add(kind);
      if (pathKind) savePathKinds.add(pathKind);
      if (pathKind === "management_net" && target) {
        saveNetTargets.add(String(target).split(/\s+/)[0] ?? "");
      }
    } else if (kind === "verify") {
      observedVerify.add(kind);
      if (pathKind) verifyPathKinds.add(pathKind);
      if (pathKind === "management_net" && target) {
        verifyNetTargets.add(String(target).split(/\s+/)[0] ?? "");
      }
    }
  };

  for (const line of configCmds) {
    consider(line, "init");
  }
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (!_isMapping(s)) continue;
    if (!is_apv_command_step(s, { methods: null })) continue;
    for (const line of _apv_command_lines_for_step(steps, i)) {
      consider(line, `step[${i}]`);
    }
  }

  if (observedSave.size && observedVerify.size) {
    return "";
  }
  if (!observedSave.size && !observedVerify.size) {
    return "";
  }
  if (observedSave.size && !observedVerify.size) {
    failures.push("the case writes configuration to flash but never verifies the persistence — add a verify step (show startup-config or equivalent) after the save.");
  }
  if (observedVerify.size && !observedSave.size) {
    failures.push("the case verifies persistence but never writes configuration to flash — add the save step (write memory/file/all/net) before the verify.");
  }
  if (expectedSaveVariant) {
    const variants = new Set<string>();
    for (const line of configCmds) {
      const v = _per_cmd_save_variant(line);
      if (v) variants.add(v);
    }
    for (let i = 0; i < steps.length; i++) {
      const s = steps[i];
      if (!_isMapping(s)) continue;
      if (!is_apv_command_step(s, { methods: null })) continue;
      for (const line of _apv_command_lines_for_step(steps, i)) {
        const v = _per_cmd_save_variant(line);
        if (v) variants.add(v);
      }
    }
    if (variants.size && !variants.has(expectedSaveVariant)) {
      failures.push(`the case uses save variant(s) ${[...variants].sort().join(", ")}, but the intent declares '${expectedSaveVariant}' — the write family was silently swapped (e.g. write all → write memory). Restore the declared save command.`);
    }
  }
  return failures.join("\n");
}

function _gate_destructive_commands(autoid: string, steps: any[], opts: { init?: string; stage?: string } = {}): string {
  const { _checkNoDestructiveCommands } = require("./structural_gate");
  const { StructuralResult } = require("./structural_gate");
  const result = new StructuralResult();
  _checkNoDestructiveCommands(steps, result);
  if (result.disabled.length) {
    _write_gate_disabled(autoid, result.disabled, { stage: opts.stage ?? "emit" });
  }
  if (result.violations.length) {
    _write_gate_rejections(autoid, result.violations, { stage: opts.stage ?? "emit" });
    return result.render(autoid);
  }
  return "";
}

function _signal_merge_precheck_refusal(aid: string, gate: string, code: string, opts: { detail?: Record<string, any> } = {}): void {
  _write_gate_rejections(aid, [{ code, detail: JSON.stringify(opts.detail ?? {}), step_index: -1 }], { stage: "merge_precheck" });
}

const MERGE_PRECHECK_REFUSAL_GATE_EXEMPT_GOVERNANCE = "exempt_governance_merge_precheck";

function _engine_inserted_binding_rejection(autoid: string, exc: Error, mutationReceipt: Record<string, any>, opts: { before_binding_steps?: any[]; binding_steps?: any[] } = {}): string {
  const before = opts.before_binding_steps ?? [];
  const after = opts.binding_steps ?? [];
  if (before.length !== after.length) {
    return `error: case ${autoid} the engine's mutation plan changed the number of provenance steps (${before.length} → ${after.length}), so the observation/assertion binding no longer lines up — this is an engine-side bug, not an authoring defect. Copy this error verbatim into your reply.`;
  }
  for (let i = 0; i < before.length; i++) {
    const b = before[i];
    const a = after[i];
    if (JSON.stringify(b) !== JSON.stringify(a)) {
      const inserted = (mutationReceipt.inserted ?? []).find((item: any) => Number(item.step_index) === i);
      if (inserted) {
        return `error: case ${autoid} the engine-inserted mutation step at step[${i}] (${JSON.stringify(inserted.command ?? "")}) invalidated the observation/assertion binding: ${exc instanceof Error ? exc.message : String(exc)}. This is an engine-side insertion, not an authoring defect. Copy this error verbatim into your reply.`;
      }
    }
  }
  return "";
}

function _binding_steps_from_provenance(provSteps: any[]): any[] {
  const out: any[] = [];
  for (const step of provSteps) {
    if (!_isMapping(step)) continue;
    const source = step.source;
    if (!_isMapping(source)) continue;
    out.push({ layer: step.layer, kind: source.kind, ref: source.ref });
  }
  return out;
}

function _gate_governing_spec_identity(autoid: string, validatedProv: any, opts: { mutation_receipt?: Record<string, any> } = {}): string {
  const [specName, specSha, specGen, specManifest] = _intentGoverningSpec(autoid);
  if (!specName) return "";
  const { check_governing_spec_identity } = require("../../../case_compiler/provenance_ir");
  try {
    const problems = check_governing_spec_identity(validatedProv, { governing_spec: specName, governing_spec_sha256: specSha, governing_spec_generation_id: specGen, governing_spec_manifest_sha256: specManifest });
    return problems.join("\n");
  } catch {
    return "";
  }
}

function _gate_manual_expect_conditional(autoid: string, validatedProv: any): string {
  const { check_manual_expect_conditional } = require("../../../case_compiler/provenance_ir");
  try {
    return check_manual_expect_conditional(validatedProv);
  } catch {
    return "";
  }
}

function _worker_bound_capability_inventory(): [any, any, string] {
  try {
    const { current_worker_device_session } = require("../worker_device_context");
    const session = current_worker_device_session();
    if (session === null || session === undefined) return [null, null, ""];
    const build = String(session.capability_build ?? "").trim();
    if (!build) return [null, null, "the worker session has no bound capability build"];
    const { load_vendor_stdlib } = require("../../../case_compiler/vendor_stdlib");
    const inventory = load_vendor_stdlib("", build);
    if (inventory === null) return [null, null, `the vendor command-tree projection for build ${build} could not be loaded`];
    const inventoryBuild = String(inventory.device_os_build ?? "").trim();
    if (inventoryBuild && inventoryBuild !== build) {
      return [null, null, `the bound build ${build} does not match the projection build ${inventoryBuild}`];
    }
    const receipt = {
      schema: "ist.compile.capability_consumed",
      device_build: build,
      generation_id: String(session.capability_generation_id ?? ""),
      manifest_sha256: String(session.capability_manifest_sha256 ?? ""),
      projection_sha256: String(session.capability_projection_sha256 ?? ""),
    };
    return [inventory, receipt, ""];
  } catch (exc) {
    return [null, null, `${(exc as any)?.constructor?.name ?? "Error"}: ${exc}`];
  }
}

function _validated_consistency_contract_identity(autoid: string, opts: { mechanical_case_sha256: string; blocks: any[] | null; consistency_batch_name: string }): [string | null, Record<string, any> | null, string] {
  const mechanicalCaseSha256 = opts.mechanical_case_sha256;
  const consistencyBatchName = opts.consistency_batch_name;
  if (!consistencyBatchName) return [null, null, ""];
  const _sh = require("../compile_engine/_shared");
  const { read_regular_nofollow, sha256_bytes } = require("../../../case_compiler/_sealed_io");
  const credPath = new P(String(_sh.outputs_root())).joinpath(consistencyBatchName, autoid, ".grade_credential.json");
  let payload: Buffer;
  try {
    payload = read_regular_nofollow(credPath._p, {
      errorType: Error,
      invalid_message: "lint credential path is invalid",
      directory_message: "lint credential parent is unavailable",
      open_message: "lint credential is unavailable",
      bounds_message: "lint credential exceeds its byte budget",
      changed_message: "lint credential changed while being read",
      max_bytes: _MAX_CLAIMS_BYTES,
      min_bytes: 1,
    }) as Buffer;
  } catch (exc) {
    return [null, null, `consistency batch lint credential is unavailable: ${(exc as any)?.constructor?.name ?? "Error"}`];
  }
  let data: Record<string, any>;
  try {
    data = JSON.parse(payload.toString("utf8"));
  } catch {
    return [null, null, "consistency batch lint credential is not valid JSON"];
  }
  if (!_isMapping(data)) {
    return [null, null, "consistency batch lint credential is not a JSON object"];
  }
  if (String(data.autoid ?? "") !== String(autoid)) {
    return [null, null, "consistency batch lint credential carries another case identity"];
  }
  const seal = data.seal;
  if (!_isMapping(seal)) {
    return [null, null, "consistency batch lint credential has no seal"];
  }
  if (String(seal.mechanical_case_sha256 ?? "") !== mechanicalCaseSha256) {
    return [null, null, "consistency batch lint credential seal does not match the submitted mechanical case"];
  }
  const consistencyContractSha = String(data.consistency_contract_sha256 ?? "");
  if (consistencyContractSha && !_SHA256_RE.test(consistencyContractSha)) {
    return [null, null, "consistency batch lint credential carries an invalid consistency contract identity"];
  }
  return [consistencyContractSha || null, data.consistency_requirement_proof ?? null, ""];
}

export const _SSL_CERT_ROOT = "cert";
const _SSL_HOST_ROLES = ["virtual", "real"];
const _SSL_IMPORT_FUNCTIONS: Record<string, string> = {
  "rootca|plain": "importRootCA",
  "rootca|sni": "importSniRootca",
  "interca|plain": "importInterCA",
  "interca|sni": "importSniInterca",
  "crlca|plain": "importCRLCA",
  "crlca|sni": "importSniCrlca",
  "key|plain": "importKey",
  "key|sni": "importSniKey",
  "key|sm2": "sm2ImportKey",
  "key|sm2_sni": "sm2ImportSniKey",
  "cert|plain": "importCert",
  "cert|sni": "importSniCert",
  "cert|sm2": "sm2ImportCert",
  "cert|sm2_sni": "sm2ImportSniCert",
};
const _SSL_ACTIVATE_FUNCTION = "activeCert";
const _SSL_TEARDOWN_REF = "skeleton:command_teardown_atlas.json";
const _SSL_FUNCTION_REF = "skeleton:excel_contract.json";
const _SSL_CERT_LOAD_FIELDS = new Set(["kind", "host", "vhost", "vhost_role", "bound_object", "cert_group", "rootca_file", "interca_file", "crlca_file", "pairs", "sni_domain", "activate_index", "activate_cert_type", "desc"]);
const _SSL_CERT_PAIR_FIELDS = new Set(["key_file", "cert_file", "index", "key_passwd", "sm2_key_type", "sm2_cert_type"]);
const _SSL_HOST_PREFIX = "ssl host";
const _SSL_MATERIAL_FIELDS = new Set(["cert_group", "pairs", "rootca_file", "interca_file", "crlca_file"]);

function _ssl_import_key(role: string, variant: string): string {
  return _SSL_IMPORT_FUNCTIONS[`${role}|${variant}`];
}

const _leadingWordsCache = new Map<string, string[]>();

function _leading_literal_words(text: string): string[] {
  const cached = _leadingWordsCache.get(text);
  if (cached) return cached;
  const words = text.toLowerCase().match(/[a-z0-9_-]+/g) ?? [];
  if (_leadingWordsCache.size >= 256) _leadingWordsCache.clear();
  _leadingWordsCache.set(text, words);
  return words;
}

const _activationCache = new Map<string, boolean>();

function _ssl_import_embeds_activation(functionName: string): boolean {
  const cached = _activationCache.get(functionName);
  if (cached !== undefined) return cached;
  const { mirror_src } = require("../../../case_compiler/apv_lang");
  const source: string = mirror_src("lib/apv/ssl_comm.py");
  if (!source) {
    throw new PyValueError("SSL framework source cannot be parsed");
  }
  const classRe = /class\s+ssl_comm[\s\S]*?(?=\nclass\s|$)/;
  const classMatch = classRe.exec(source);
  if (!classMatch) {
    throw new PyValueError("SSL framework class is unavailable");
  }
  const body = classMatch[0];
  const methods = new Map<string, string>();
  for (const m of body.matchAll(/\n    (?:async\s+)?def\s+(\w+)\(self[^)]*\):([\s\S]*?)(?=\n    (?:async\s+)?def\s+|$)/g)) {
    methods.set(m[1], m[2]);
  }
  const commandPrefixes = (methodName: string): Set<string[]> => {
    const method = methods.get(methodName);
    if (method === undefined) {
      throw new PyValueError(`SSL framework method ${_pyrepr(methodName)} is unavailable`);
    }
    const prefixes = new Set<string>();
    const callRe = /cmd_config\(\s*(["'])([^"']*?)\1/g;
    for (const cm of method.matchAll(callRe)) {
      const prefix = _leading_literal_words(cm[2]);
      if (prefix.length) prefixes.add(prefix.join(" "));
    }
    return new Set([...prefixes].map((p) => p.split(" ")));
  };
  let activationPrefixes = commandPrefixes(_SSL_ACTIVATE_FUNCTION);
  if (activationPrefixes.size === 0) {
    throw new PyValueError("activeCert has no mechanically readable framework action");
  }
  const longest = Math.max(...[...activationPrefixes].map((p) => p.length));
  activationPrefixes = new Set([...activationPrefixes].filter((p) => p.length === longest));
  const importPrefixes = commandPrefixes(functionName);
  const result = [...importPrefixes].some((candidate) =>
    [...activationPrefixes].some((activation) => candidate.length >= activation.length && activation.every((tok, i) => candidate[i] === tok)));
  _activationCache.set(functionName, result);
  return result;
}

function _pyrepr(value: any): string {
  if (typeof value === "string") return `'${value.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
  return String(value);
}

function _ssl_contract_parameters(host: string, functionName: string): [Set<string>, Set<string>, string] {
  const { contract_entry, load_excel_contract } = require("../../../case_compiler/excel_contract");
  let contract: any;
  try {
    contract = load_excel_contract();
  } catch (exc) {
    return [new Set(), new Set(), `Excel function contract is unavailable: ${exc}`];
  }
  const entry = contract_entry(host, functionName, contract);
  if (entry === null || entry === undefined) {
    return [new Set(), new Set(), `the framework function ${_pyrepr(functionName)} is absent from the Excel function contract for ${host} (contract is generated from the mirror; regenerate it if the framework really ships this helper)`];
  }
  const signature = entry.signature ?? {};
  const names = new Set<string>((signature.parameters ?? []).map((p: any) => String(p.name ?? "")).filter((n: string) => n));
  const required = new Set<string>((signature.required ?? []).map((n: any) => String(n)));
  if (!names.size) {
    return [new Set(), new Set(), `contract entry for ${_pyrepr(functionName)} carries no signature`];
  }
  return [names, required, ""];
}

function _ssl_call_g(host: string, functionName: string, values: Record<string, any>): [string, string] {
  const [names, required, error] = _ssl_contract_parameters(host, functionName);
  if (error) return ["", error];
  const unknown = Object.keys(values).filter((k) => !names.has(k)).sort();
  if (unknown.length) {
    return ["", `${functionName}: parameter(s) ${unknown.join(", ")} are not in the contract signature (it takes ${[...names].sort().join(", ")})`];
  }
  const missing = [...required].filter((k) => !(k in values)).sort();
  if (missing.length) {
    return ["", `${functionName}: required parameter(s) ${missing.join(", ")} have no value; supply them on the block`];
  }
  const parts: string[] = [];
  for (const name of Object.keys(values).sort()) {
    const value = values[name];
    if (typeof value === "number" && Number.isInteger(value)) {
      parts.push(`${name}=${value}`);
      continue;
    }
    const text = String(value);
    if (text.includes('"')) {
      return ["", `${functionName}: parameter ${name} value must not contain a quote`];
    }
    parts.push(`${name}="${text}"`);
  }
  return [parts.join(", "), ""];
}

function _ssl_cert_path(group: string, filename: string): string {
  const parts = [_SSL_CERT_ROOT, group.replace(/^\/+|\/+$/g, "").replace(/^ +| +$/g, ""), filename.replace(/^\/+|\/+$/g, "").replace(/^ +| +$/g, "")].filter((p) => p);
  return parts.join("/");
}

function _prepare_certified_ssl_material(block: Record<string, any>): Record<string, any> {
  const candidate = { ...block };
  if ([..._SSL_MATERIAL_FIELDS].some((field: string) => field in candidate)) {
    return candidate;
  }
  const { certified_ssl_release_fixture } = require("../../../case_compiler/excel_capability_samples");
  const fixture = certified_ssl_release_fixture();
  candidate.cert_group = fixture.cert_group;
  candidate.rootca_file = fixture.rootca_file;
  candidate.pairs = fixture.pairs.map((pair: any) => ({ ...pair }));
  return candidate;
}

function _certified_ssl_material_error(block: Record<string, any>): string {
  const { certified_ssl_release_fixture } = require("../../../case_compiler/excel_capability_samples");
  const fixture = certified_ssl_release_fixture();
  const expected = fixture.resolved_paths;
  const group = String(block.cert_group ?? "");
  const pairs = block.pairs ?? [];
  const resolvedKeys = pairs.map((pair: any) => _ssl_cert_path(group, String(pair.key_file ?? "")));
  const resolvedCerts = pairs.map((pair: any) => _ssl_cert_path(group, String(pair.cert_file ?? "")));
  const rootca = String(block.rootca_file ?? "").trim();
  const resolvedRootca = rootca ? _ssl_cert_path(group, rootca) : "";
  const unsupportedCa = ["interca_file", "crlca_file"].some((field) => String(block[field] ?? "").trim());
  const alteredPair = pairs.some((pair: any) => String(pair.key_passwd ?? "").trim() || String(pair.sm2_key_type ?? "").trim() || String(pair.sm2_cert_type ?? "").trim());
  if (
    JSON.stringify(resolvedKeys) === JSON.stringify(expected.keys) &&
    JSON.stringify(resolvedCerts) === JSON.stringify(expected.certs) &&
    (!resolvedRootca || resolvedRootca === String(expected.rootca)) &&
    !unsupportedCa &&
    !alteredPair &&
    (Number(block.activate_index ?? 1) === 1)
  ) {
    return "";
  }
  return `certificate material is not bound to the promoted same-source release fixture. Do not invent a repository path or certificate filename. Omit cert_group, pairs, rootca_file, interca_file and crlca_file together to use the engine-owned certified default projected in blocks_schema.json. Resolved key(s)=${JSON.stringify(resolvedKeys)}, cert(s)=${JSON.stringify(resolvedCerts)}, rootca=${JSON.stringify(resolvedRootca)}.`;
}

function _ssl_teardown_commands(): [string[], string] {
  const { _derivation_data } = require("../../../case_compiler/tau_coverage");
  let atlas: any;
  try {
    const [, a] = _derivation_data();
    atlas = a;
  } catch (exc) {
    return [[], `command teardown atlas is unavailable: ${exc}`];
  }
  for (const rule of atlas.clear_rules ?? []) {
    const prefixes = (rule.prefixes ?? []).map((p: any) => String(p));
    if (!prefixes.some((p: string) => p === _SSL_HOST_PREFIX)) continue;
    const cleanup = (rule.cleanup_commands ?? []).map((c: any) => String(c)).filter((c: string) => c.trim());
    if (cleanup.length) return [cleanup, ""];
  }
  return [[], `the teardown atlas carries no cleanup rule for ${_pyrepr(_SSL_HOST_PREFIX)}; regenerate it with: python -m scripts.gen_command_teardown_atlas`];
}

function _ssl_start_command(vhost: string): [string, string] {
  const { _derivation_data } = require("../../../case_compiler/tau_coverage");
  const { load_ssl_lifecycle_contract } = require("../../../case_compiler/ssl_lifecycle_contract");
  let lifecycle: any;
  try {
    const [, atlas] = _derivation_data();
    lifecycle = load_ssl_lifecycle_contract(String(atlas.device_build ?? ""));
  } catch (exc) {
    return ["", `SSL host start lifecycle is unavailable: ${exc}`];
  }
  const head = String(lifecycle.ssl_host_start_head ?? "").trim();
  if (!head) return ["", "SSL lifecycle contract carries no host start head"];
  return [`${head} "${vhost}"`, ""];
}

export function ssl_certificate_load_blocks(block: Record<string, any>): [Array<Record<string, any>> | null, string] {
  if (!_isMapping(block)) return [null, "SSL_CERT_LOAD block must be an object"];
  const unknown = Object.keys(block).filter((k) => !_SSL_CERT_LOAD_FIELDS.has(k)).sort();
  if (unknown.length) return [null, `unsupported field(s): ${unknown.join(", ")}`];
  const { _DUT_HOSTS } = require("../../../case_compiler/blocks");
  const host = String(block.host ?? _DUT_HOSTS[0]).trim();
  if (!_DUT_HOSTS.includes(host)) {
    return [null, `host must be one of ${_DUT_HOSTS} (the device under test); got ${_pyrepr(host)}`];
  }
  const vhost = String(block.vhost ?? "").trim();
  if (!vhost) return [null, "vhost is required (the SSL host name this case loads certificates onto)"];
  const role = String(block.vhost_role ?? _SSL_HOST_ROLES[0]).trim().toLowerCase();
  if (!_SSL_HOST_ROLES.includes(role)) {
    return [null, `vhost_role must be one of ${_SSL_HOST_ROLES}; got ${_pyrepr(role)}`];
  }
  const bound = String(block.bound_object ?? "").trim();
  if (!bound) return [null, "bound_object is required (the slb virtual/real object this SSL host binds to)"];
  const group = String(block.cert_group ?? "").trim();
  const sni = String(block.sni_domain ?? "").trim();
  const desc = String(block.desc ?? "").trim();
  const pairs = block.pairs;
  if (!Array.isArray(pairs) || !pairs.length) {
    return [null, "pairs must be a non-empty array of {key_file, cert_file} objects (one entry per key/certificate pair; sm2 sign+enc is two entries)"];
  }
  if (vhost.includes('"') || vhost.includes("\\") || bound.includes('"') || bound.includes("\\")) {
    return [null, "vhost and bound_object must not contain quotes or backslashes"];
  }
  const [, teardownError] = _ssl_teardown_commands();
  if (teardownError) return [null, teardownError];
  const out: Array<Record<string, any>> = [{ kind: "CONFIG", host, cmds: [`${_SSL_HOST_PREFIX} ${role} "${vhost}" ${bound}`], desc: desc || `create the ${role} SSL host ${vhost}`, ref: _SSL_TEARDOWN_REF }];
  const certificateImportFunctions: string[] = [];

  const addStep = (functionName: string, values: Record<string, any>, note: string): string => {
    const [g, error] = _ssl_call_g(host, functionName, values);
    if (error) return error;
    out.push({ kind: "STEP", E: host, F: functionName, G: g, desc: note, ref: _SSL_FUNCTION_REF });
    return "";
  };

  const caValues = (functionName: string, path: string): Record<string, any> => {
    const values: Record<string, any> = { vhost };
    const [names] = _ssl_contract_parameters(host, functionName);
    values[names.has("certFile") ? "certFile" : "certfile"] = path;
    if (sni && names.has("domain")) values.domain = sni;
    else if (sni && names.has("sni")) values.sni = sni;
    return values;
  };

  for (const [roleName, field] of [["rootca", "rootca_file"], ["interca", "interca_file"]] as const) {
    const filename = String(block[field] ?? "").trim();
    if (!filename) continue;
    const functionName = _ssl_import_key(roleName, sni ? "sni" : "plain");
    const error = addStep(functionName, caValues(functionName, _ssl_cert_path(group, filename)), `import the ${roleName} certificate onto ${vhost}`);
    if (error) return [null, error];
  }
  for (const [index, pair] of pairs.entries()) {
    if (!_isMapping(pair)) return [null, `pairs[${index}] must be an object`];
    const pairUnknown = Object.keys(pair).filter((k) => !_SSL_CERT_PAIR_FIELDS.has(k)).sort();
    if (pairUnknown.length) return [null, `pairs[${index}]: unsupported field(s): ${pairUnknown.join(", ")}`];
    const keyFile = String(pair.key_file ?? "").trim();
    const certFile = String(pair.cert_file ?? "").trim();
    if (!keyFile || !certFile) return [null, `pairs[${index}] requires both key_file and cert_file`];
    const slot = pair.index ?? 1;
    if (typeof slot !== "number" || !Number.isInteger(slot) || slot < 1) {
      return [null, `pairs[${index}].index must be a positive integer`];
    }
    const passwd = String(pair.key_passwd ?? "");
    const keyType = String(pair.sm2_key_type ?? "").trim();
    const certType = String(pair.sm2_cert_type ?? "").trim();
    if (Boolean(keyType) !== Boolean(certType)) {
      return [null, `pairs[${index}]: sm2_key_type and sm2_cert_type must be given together (the sm2 variant loads a typed key and its typed certificate as one pair)`];
    }
    const variant = keyType ? (sni ? "sm2_sni" : "sm2") : sni ? "sni" : "plain";
    for (const [roleName, filename, typed] of [["key", keyFile, keyType], ["cert", certFile, certType]] as const) {
      const functionName = _ssl_import_key(roleName, variant);
      const [names, , errorSig] = _ssl_contract_parameters(host, functionName);
      if (errorSig) return [null, errorSig];
      const values: Record<string, any> = { vhost };
      let fileParamSet = false;
      for (const candidate of ["keyfile", "keyFile", "certfile", "certFile"]) {
        if (names.has(candidate)) {
          values[candidate] = _ssl_cert_path(group, filename);
          fileParamSet = true;
          break;
        }
      }
      if (!fileParamSet) {
        return [null, `${functionName}: the contract signature has no key/certificate file parameter (it takes ${[...names].sort().join(", ")})`];
      }
      if (typed) {
        let typeSet = false;
        for (const candidate of ["keyType", "certType"]) {
          if (names.has(candidate)) {
            values[candidate] = typed;
            typeSet = true;
            break;
          }
        }
        if (!typeSet) return [null, `${functionName}: the contract signature has no sm2 type parameter`];
      }
      if (sni && names.has("domain")) values.domain = sni;
      for (const candidate of ["index", "id"]) {
        if (names.has(candidate)) {
          values[candidate] = slot;
          break;
        }
      }
      if (passwd && names.has("passwd")) values.passwd = passwd;
      const error = addStep(functionName, values, `import the ${roleName} of pair ${index + 1} onto ${vhost}`);
      if (error) return [null, error];
      if (roleName === "cert") certificateImportFunctions.push(functionName);
    }
  }
  const crlcaFile = String(block.crlca_file ?? "").trim();
  if (crlcaFile) {
    const functionName = _ssl_import_key("crlca", sni ? "sni" : "plain");
    const error = addStep(functionName, caValues(functionName, _ssl_cert_path(group, crlcaFile)), `import the CRL issuer certificate onto ${vhost}`);
    if (error) return [null, error];
  }
  let activationIsEmbedded: boolean;
  try {
    activationIsEmbedded = certificateImportFunctions.length > 0 && certificateImportFunctions.every((fn) => _ssl_import_embeds_activation(fn));
  } catch (exc) {
    return [null, `cannot derive certificate activation from framework source: ${exc instanceof Error ? exc.message : exc}`];
  }
  if (!activationIsEmbedded) {
    const activateIndex = block.activate_index ?? 1;
    if (typeof activateIndex !== "number" || !Number.isInteger(activateIndex) || activateIndex < 1) {
      return [null, "activate_index must be a positive integer"];
    }
    const activateValues: Record<string, any> = { vhost, index: activateIndex };
    if (sni) activateValues.sni = sni;
    const certTypeArg = String(block.activate_cert_type ?? "").trim();
    if (certTypeArg) activateValues.certType = certTypeArg;
    const error = addStep(_SSL_ACTIVATE_FUNCTION, activateValues, `activate the loaded certificate on ${vhost} because the selected certificate-import helper does not embed activation`);
    if (error) return [null, error];
  }
  const [startCommand, startError] = _ssl_start_command(vhost);
  if (startError) return [null, startError];
  out.push({ kind: "CONFIG", host, cmds: [startCommand], desc: `start the SSL host ${vhost} after certificate activation`, ref: _SSL_TEARDOWN_REF });
  out.push({ kind: "STEP", E: host, F: "cmd_config", G: `clear ssl host "${vhost}",prompt=abort:`, desc: `begin paired teardown for the SSL host ${vhost}`, ref: _SSL_TEARDOWN_REF });
  out.push({ kind: "STEP", E: host, F: "cmd_config", G: "YES", desc: `confirm paired teardown for the SSL host ${vhost}`, ref: _SSL_TEARDOWN_REF });
  return [out, ""];
}

export function split_ssl_certificate_load_blocks(block: Record<string, any>): [Array<Record<string, any>> | null, Array<Record<string, any>> | null, string] {
  const prepared = _prepare_certified_ssl_material(block);
  const [expanded, error] = ssl_certificate_load_blocks(prepared);
  if (error || expanded === null) return [null, null, error];
  const materialError = _certified_ssl_material_error(prepared);
  if (materialError) return [null, null, materialError];
  if (expanded.length < 3) return [null, null, "SSL_CERT_LOAD lowering omitted its paired teardown"];
  const cleanup = expanded.slice(-2);
  const [first, second] = cleanup;
  if (!(
    _isMapping(first) && _isMapping(second) &&
    String(first.kind ?? "").trim().toUpperCase() === "STEP" &&
    String(first.F ?? "").trim() === "cmd_config" &&
    String(first.G ?? "").includes("prompt=abort:") &&
    String(second.kind ?? "").trim().toUpperCase() === "STEP" &&
    String(second.F ?? "").trim() === "cmd_config" &&
    String(second.G ?? "").trim().toUpperCase() === "YES"
  )) {
    return [null, null, "SSL_CERT_LOAD lowering no longer ends in the certified interactive object-scoped teardown pair"];
  }
  return [expanded.slice(0, -2), cleanup, ""];
}

export function _expand_ssl_cert_load_sugar(blocks: any[]): [any[] | null, string] {
  if (!blocks.some((b) => _isMapping(b) && String(b.kind ?? "").trim().toUpperCase() === SSL_CERT_LOAD_KIND)) {
    return [blocks, ""];
  }
  const out: any[] = [];
  const deferredCleanup: any[][] = [];
  const assertionKinds = new Set(["OBSERVE_ASSERT", "CAPTURE_COMPARE", "OBSERVE_DIST", "OBSERVE_MEMBER", "EXPECT_FROM"]);
  const assertionIndices = blocks
    .map((candidate, index) => [candidate, index] as [any, number])
    .filter(([candidate]) => _isMapping(candidate) && (assertionKinds.has(String(candidate.kind ?? "").trim().toUpperCase()) || (String(candidate.kind ?? "").trim().toUpperCase() === "STEP" && String(candidate.E ?? "").trim() === "check_point")))
    .map(([, index]) => index);
  const businessAnchor = assertionIndices.length ? Math.max(...assertionIndices) : blocks.length - 1;
  const flushCleanup = (): void => {
    for (const cleanup of [...deferredCleanup].reverse()) {
      out.push(...cleanup);
    }
    deferredCleanup.length = 0;
  };
  for (const [index, block] of blocks.entries()) {
    if (!_isMapping(block) || String(block.kind ?? "").trim().toUpperCase() !== SSL_CERT_LOAD_KIND) {
      out.push(block);
    } else {
      const [setup, cleanup, error] = split_ssl_certificate_load_blocks(block);
      if (error) return [null, `blocks[${index}](${SSL_CERT_LOAD_KIND}): ${error}`];
      out.push(...(setup ?? []));
      deferredCleanup.push(cleanup ?? []);
    }
    if (index === businessAnchor) flushCleanup();
  }
  flushCleanup();
  return [out, ""];
}

const _CURRENT_EMIT_GATE_CODES: { value: string[] | null } = { value: null };

function _reject_unbound_emit_identity(code: string, message: string): string {
  const captured = _CURRENT_EMIT_GATE_CODES.value;
  if (captured !== null && !captured.includes(code)) {
    captured.push(code);
  }
  return `error: [${code}] ${message.replace(/^error:/, "").trim()}`;
}

function _record_emit_error_return(autoid: string, code: string, message: string): string {
  if (_CURRENT_EMIT_GATE_CODES.value && _CURRENT_EMIT_GATE_CODES.value.length) {
    return message;
  }
  return _reject_compile_gate(autoid, code, message);
}

function _reject_compile_gate(autoid: string, code: string, message: string, opts: { detail?: string; step_index?: number; stage?: string; extra?: Record<string, any> | null; failure_observations?: Array<Record<string, any>> | null } = {}): string {
  const { StructuralViolation } = require("./structural_gate");
  if (["mutation_contract_invalid", "provenance_parse_failed", "provenance_step_count_mismatch", "assertion_type_invalid", "assertion_binding_invalid", "provenance_source_unresolved"].includes(code) && !message.includes("COMPLIANT EMIT PATHS")) {
    message = `${message}\n\n${_emit_contract_paths()}`;
  }
  _write_gate_rejections(autoid, [new StructuralViolation(code, opts.detail || message, opts.step_index ?? -1)], { stage: opts.stage ?? "emit", extra: opts.extra ?? null, failure_observations: opts.failure_observations ?? null });
  return message;
}

function _emit_contract_paths(): string {
  return "COMPLIANT EMIT PATH — IDE typed path only. Provide aligned step provenance; the compiler derives assertion types, ordinals, ledger mode, observation windows, and the engine-issued device build. For an allowed Exempt pragma, mark only the affected check_point step with exempt=true and a closed-set reason_code; omit mutation_requirements. Existing historical artifacts are diagnostic inputs only and cannot select a legacy generation or delivery path.";
}

export const GATE_MAILBOX_VERSION = 1;
export const GATE_REJECTIONS_NAME = "gate_rejections.json";
export const GATE_DISABLED_NAME = "gate_disabled.json";
const _MAILBOX_BASE_KEYS = new Set(["ev", "aid", "gate", "detail", "step_index", "stage", "ts", "occurrence_id"]);
const _GATE_MAILBOX_LOCK_PATH = nodePath.join(os.tmpdir(), "ist_gate_mailbox.lock");
let _gateMailboxLock: { release(): void } | null = null;

function _gateMailboxLockAcquire(): void {
  _gateMailboxLock = acquireLockSync(_GATE_MAILBOX_LOCK_PATH);
}

function _gateMailboxLockRelease(): void {
  if (_gateMailboxLock) {
    _gateMailboxLock.release();
    _gateMailboxLock = null;
  }
}

export function _write_gate_mailbox(
  aid: string,
  event: string,
  entries: Array<Record<string, any>>,
  opts: { stage?: string; extra?: Record<string, any> | null } = {},
): void {
  if (!entries.length) return;
  const _sh = require("../compile_engine/_shared");
  const { append_jsonl_atomic } = require("../../../case_compiler/_sealed_io");
  const stage = opts.stage ?? "emit";
  const path = new P(String(_sh.outputs_root())).joinpath(aid, GATE_REJECTIONS_NAME);
  _gateMailboxLockAcquire();
  try {
    let existing: Array<Record<string, any>> = [];
    if (path.is_file()) {
      try {
        existing = JSON.parse(fs.readFileSync(path._p).toString("utf8"));
      } catch {
        existing = [];
      }
    }
    if (!Array.isArray(existing)) existing = [];
    const ts = Date.now() / 1000;
    const merged = [...existing];
    for (const entry of entries) {
      const record: Record<string, any> = {
        ev: event,
        aid,
        gate: String(entry.code ?? ""),
        detail: String(entry.detail ?? "").slice(0, 400),
        step_index: Number(entry.step_index ?? -1),
        stage,
        ts,
        occurrence_id: merged.length + 1,
      };
      if (opts.extra && typeof opts.extra === "object") {
        for (const [k, v] of Object.entries(opts.extra)) {
          if (!_MAILBOX_BASE_KEYS.has(k)) record[k] = v;
        }
      }
      merged.push(record);
    }
    fs.mkdirSync(path.parent._p, { recursive: true });
    const tmpPath = path._p + ".tmp." + String(process.pid);
    fs.writeFileSync(tmpPath, JSON.stringify(merged, null, 2) + "\n", "utf8");
    fs.renameSync(tmpPath, path._p);
  } finally {
    _gateMailboxLockRelease();
  }
}

export function _write_gate_rejections(
  aid: string,
  violations: Array<Record<string, any>>,
  opts: { stage?: string; extra?: Record<string, any> | null; failure_observations?: Array<Record<string, any>> | null } = {},
): void {
  if (!violations.length) return;
  const entries = violations.map((v) => ({ code: String(v.code ?? ""), detail: String(v.detail ?? ""), step_index: Number(v.step_index ?? -1) }));
  const extra: Record<string, any> | null = opts.extra ?? null;
  _write_gate_mailbox(aid, "gate_rejected", entries, { stage: opts.stage ?? "emit", extra });
  if (opts.failure_observations) {
    const path = new P(String(require("../compile_engine/_shared").outputs_root())).joinpath(aid, "failure_observations.json");
    try {
      fs.mkdirSync(path.parent._p, { recursive: true });
      fs.writeFileSync(path._p, JSON.stringify(opts.failure_observations, null, 2) + "\n", "utf8");
    } catch {}
  }
}

export function _write_gate_disabled(
  aid: string,
  violations: Array<Record<string, any>>,
  opts: { stage?: string } = {},
): void {
  if (!violations.length) return;
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(aid, GATE_DISABLED_NAME);
  _gateMailboxLockAcquire();
  try {
    let existing: Array<Record<string, any>> = [];
    if (path.is_file()) {
      try {
        existing = JSON.parse(fs.readFileSync(path._p).toString("utf8"));
      } catch {
        existing = [];
      }
    }
    if (!Array.isArray(existing)) existing = [];
    const ts = Date.now() / 1000;
    const merged = [...existing];
    for (const v of violations) {
      merged.push({ ev: "gate_disabled", aid, gate: String(v.code ?? ""), detail: String(v.detail ?? "").slice(0, 400), step_index: Number(v.step_index ?? -1), stage: opts.stage ?? "emit", ts, occurrence_id: merged.length + 1 });
    }
    fs.mkdirSync(path.parent._p, { recursive: true });
    fs.writeFileSync(path._p, JSON.stringify(merged, null, 2) + "\n", "utf8");
  } finally {
    _gateMailboxLockRelease();
  }
}

export function _pending_gate_rejections(autoid: string, opts: { expected_version?: number } = {}): Array<Record<string, any>> {
  const expected = opts.expected_version ?? 0;
  if (!expected) return [];
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(String(autoid).trim(), GATE_REJECTIONS_NAME);
  _gateMailboxLockAcquire();
  try {
    if (!path.is_file()) return [];
    try {
      const rows = JSON.parse(fs.readFileSync(path._p).toString("utf8"));
      return Array.isArray(rows) ? rows : [];
    } catch {
      return [];
    }
  } finally {
    _gateMailboxLockRelease();
  }
}

export function _pending_gate_disabled(autoid: string, opts: { expected_version?: number } = {}): Array<Record<string, any>> {
  const expected = opts.expected_version ?? 0;
  if (!expected) return [];
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(String(autoid).trim(), GATE_DISABLED_NAME);
  _gateMailboxLockAcquire();
  try {
    if (!path.is_file()) return [];
    try {
      const rows = JSON.parse(fs.readFileSync(path._p).toString("utf8"));
      return Array.isArray(rows) ? rows : [];
    } catch {
      return [];
    }
  } finally {
    _gateMailboxLockRelease();
  }
}

function _write_gate_mailbox_ack(aid: string, event: string, xlsxMtimeNs: number): void {
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(aid, ".gate_mailbox_ack.json");
  try {
    fs.mkdirSync(path.parent._p, { recursive: true });
    fs.writeFileSync(path._p, JSON.stringify({ ev: event, aid, xlsx_mtime_ns: xlsxMtimeNs, ts: Date.now() / 1000 }, null, 2) + "\n", "utf8");
  } catch {}
}

function _emit_fail_streak_bump(autoid: string): number {
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(autoid, ".emit_fail_streak.json");
  let streak = 0;
  try {
    if (path.is_file()) {
      streak = Number(JSON.parse(fs.readFileSync(path._p).toString("utf8")).streak ?? 0);
    }
  } catch {
    streak = 0;
  }
  streak += 1;
  try {
    fs.mkdirSync(path.parent._p, { recursive: true });
    fs.writeFileSync(path._p, JSON.stringify({ streak, ts: Date.now() / 1000 }) + "\n", "utf8");
  } catch {}
  return streak;
}

function _emit_fail_streak_clear(autoid: string): void {
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(autoid, ".emit_fail_streak.json");
  try {
    if (path.is_file()) fs.unlinkSync(path._p);
  } catch {}
}

const _EMIT_STATS_LOCK_PATH = nodePath.join(os.tmpdir(), "ist_emit_stats.lock");

function _emit_stat(autoid: string, out: string, channel: string): void {
  const _sh = require("../compile_engine/_shared");
  const path = new P(String(_sh.outputs_root())).joinpath(autoid, ".emit_stats.json");
  const lock = acquireLockSync(_EMIT_STATS_LOCK_PATH);
  try {
    let stats: Record<string, any> = {};
    if (path.is_file()) {
      try {
        stats = JSON.parse(fs.readFileSync(path._p).toString("utf8"));
      } catch {
        stats = {};
      }
    }
    const failed = String(out ?? "").trimStart().toLowerCase().startsWith("error:");
    stats[channel] = (stats[channel] ?? 0) + 1;
    if (failed) {
      stats[`${channel}_fail`] = (stats[`${channel}_fail`] ?? 0) + 1;
    }
    stats.ts = Date.now() / 1000;
    fs.mkdirSync(path.parent._p, { recursive: true });
    fs.writeFileSync(path._p, JSON.stringify(stats, null, 2) + "\n", "utf8");
  } finally {
    lock.release();
  }
}

export function compile_emit(opts: {
  autoid: string;
  steps_json?: string | any[];
  init_commands?: string;
  out_name?: string;
  strict_structural?: boolean;
  provenance_json?: string;
  expected_save_variant?: string;
  steps?: any[] | string | null;
  steps_path?: string;
  override_frozen_reason?: string;
  coverage_reduction_reason?: string;
  provenance?: Record<string, any> | any[] | string | null;
  provenance_path?: string;
  blocks?: any[] | string | null;
  command_existence_evidence?: string;
  ir_gap_reason?: string;
  raw_reason?: string;
  mutation_requirements?: any[] | string | null;
  mutation_requirements_path?: string;
  mechanical_case_sha256?: string;
  consistency_batch_name?: string;
}): string {
  let autoid = String(opts.autoid ?? "").trim();
  if (!autoid) {
    return _reject_unbound_emit_identity("autoid_required", "error: autoid is required");
  }
  try {
    autoid = _safe_output_component(autoid, "autoid");
    if (String(opts.out_name ?? "").trim()) {
      _safe_output_component(String(opts.out_name ?? ""), "out_name");
    }
  } catch (exc) {
    return _reject_unbound_emit_identity("output_identity_invalid", `error: unsafe output identity: ${exc instanceof Error ? exc.message : exc}`);
  }
  const [_workerCapabilityInventory, _workerCapabilityReceipt, _capabilityIdentityError] = _worker_bound_capability_inventory();
  if (_capabilityIdentityError) {
    return _record_emit_error_return(autoid, "capability_identity_unbound", `error: command-existence gate — CAPABILITY_UNKNOWN: ${_capabilityIdentityError}. The worker artifact is refused before lint because its command-tree generation is not mechanically bound.`);
  }
  if (/^\d+$/.test(autoid) && autoid.length < 15) {
    return _record_emit_error_return(autoid, "autoid_truncated", `error: autoid '${autoid}' looks like a truncated short id (all digits but fewer than 15). Pass the full requirements-system autoid (all 18 digits, copied whole from the mindmap) — a short id baked into the xlsx breaks requirement linkage and framework-report ID chains.`);
  }
  let blocks: any[] | string | null = opts.blocks ?? null;
  const _using_blocks = blocks !== null && blocks !== "" && !(Array.isArray(blocks) && blocks.length === 0);
  const _mechanical_case_sha = String(opts.mechanical_case_sha256 ?? "").trim();
  const _consistency_batch_name = String(opts.consistency_batch_name ?? "").trim();
  let _consistency_contract_sha: string | null = null;
  let _consistency_requirement_proof: Record<string, any> | null = null;
  if (_consistency_batch_name && !_mechanical_case_sha) {
    return _reject_compile_gate(autoid, "consistency_batch_name_requires_sealed_channel", "error: consistency_batch_name is valid only with the sealed mechanical case channel");
  }
  if (_mechanical_case_sha && !_using_blocks) {
    return _reject_compile_gate(autoid, "mechanical_case_sha256_requires_blocks_channel", "error: mechanical_case_sha256 is valid only with the blocks channel; raw steps have no blocks.kind scope to bind");
  }
  if (_mechanical_case_sha && !_SHA256_RE.test(_mechanical_case_sha)) {
    return _reject_compile_gate(autoid, "mechanical_case_sha256_malformed", "error: mechanical_case_sha256 must be 64 lowercase hex characters");
  }
  let _reachability_scope: ReachabilityScope = _raw_reachability_scope();
  const _raw_requested = !_using_blocks && (
    (opts.steps !== null && opts.steps !== undefined && !(Array.isArray(opts.steps) && opts.steps.length === 0)) ||
    Boolean(String(opts.steps_path ?? "").trim()) ||
    (Array.isArray(opts.steps_json) ? true : Boolean(String(opts.steps_json ?? "").trim()))
  );
  const _canonical_gap_reason = String(opts.ir_gap_reason ?? "").trim();
  const _alias_gap_reason = String(opts.raw_reason ?? "").trim();
  if (_canonical_gap_reason && _alias_gap_reason && _canonical_gap_reason !== _alias_gap_reason) {
    return _reject_compile_gate(autoid, "ir_gap_reason_conflict", "error: ir_gap_reason and deprecated raw_reason disagree — pass one canonical reason, or make both values identical during migration");
  }
  const _gap_reason = _canonical_gap_reason || _alias_gap_reason;
  if (_raw_requested && !_gap_reason) {
    return _reject_compile_gate(autoid, "ir_gap_reason_required_for_raw_steps", "error: raw steps escape hatch requires ir_gap_reason — state the concrete blocks-language shape that cannot be expressed. Use blocks kind=STEP for generic atlas-validated E/F/G/H/I steps; raw steps without a declared IR gap fail closed.");
  }
  let provenance: any = opts.provenance ?? null;
  let provenanceJson = String(opts.provenance_json ?? "");
  let steps: any = opts.steps ?? null;
  if (_using_blocks) {
    if (typeof blocks === "string") {
      try {
        blocks = JSON.parse(blocks);
      } catch {
        return _reject_compile_gate(autoid, "blocks_parse_failed", `error: case ${autoid} blocks arrived as an unparseable string — pass a native array of combinator objects (preferred), or a valid JSON-encoded array string`, { detail: "blocks string could not be parsed as a JSON array" });
      }
    }
    if (!Array.isArray(blocks)) {
      return _reject_compile_gate(autoid, "blocks_type_invalid", `error: case ${autoid} blocks must be a native array (a list of semantic combinators), got ${typeof blocks}`, { detail: `blocks value type is ${typeof blocks}, expected list` });
    }
    if (blocks.some((_b) => _isMapping(_b) && String(_b.kind ?? "").trim().toUpperCase() === SSL_CERT_LOAD_KIND)) {
      if (_mechanical_case_sha) {
        return _reject_compile_gate(autoid, "blocks_invalid", `error: case ${autoid} uses the ${SSL_CERT_LOAD_KIND} combinator together with a sealed mechanical case. The engine expands this combinator inside compile_emit, so the expanded blocks would no longer match the sealed material and the seal comparison would fail. Until the combinator is registered in the blocks expander itself, author the expanded steps in the mechanical case, or emit this case through the unsealed tool_blocks channel.`, { detail: `${SSL_CERT_LOAD_KIND} is expanded at emit time and cannot be reconciled with a sealed mechanical case` });
      }
      const [_sugar_blocks, _sugar_error] = _expand_ssl_cert_load_sugar(blocks);
      if (_sugar_error) {
        return _reject_compile_gate(autoid, "blocks_invalid", `error: case ${autoid} invalid blocks combinator — ${_sugar_error}`, { detail: String(_sugar_error) });
      }
      blocks = _sugar_blocks;
    }
    const { expand_blocks } = require("../../../case_compiler/blocks");
    let _prov_steps: any = null;
    let _prov_obj: Record<string, any> | null = null;
    if (provenance !== null && _isMapping(provenance)) {
      _prov_obj = { ...provenance };
      _prov_steps = _prov_obj.steps;
    } else if (provenanceJson && String(provenanceJson).trim()) {
      try {
        const _pj0 = JSON.parse(String(provenanceJson));
        if (_isMapping(_pj0)) {
          _prov_obj = _pj0;
          _prov_steps = _pj0.steps;
        }
      } catch {
        return _reject_compile_gate(autoid, "provenance_parse_failed", `error: case ${autoid} in blocks mode provenance_json parse failed — pass the native provenance object instead (steps count equal to blocks count, one entry per combinator).`, { detail: "blocks-mode provenance_json could not be parsed" });
      }
    }
    if (_prov_obj !== null && String(_prov_obj.autoid ?? "").trim() !== autoid) {
      return _reject_compile_gate(autoid, "provenance_autoid_mismatch", `error: provenance autoid=${JSON.stringify(_prov_obj.autoid)} does not match compile_emit autoid=${JSON.stringify(autoid)}`, { detail: "provenance and emit case identities differ" });
    }
    const [_bsteps, _bprov, _berr] = expand_blocks(blocks, _prov_steps);
    if (_berr) {
      return _reject_compile_gate(autoid, "blocks_invalid", `error: case ${autoid} invalid blocks combinator — ${_berr}`, { detail: String(_berr) });
    }
    steps = _bsteps;
    try {
      _reachability_scope = _reachability_scope_from_blocks(blocks ?? [], { mechanical_case_sha256: _mechanical_case_sha });
    } catch (exc) {
      return _reject_compile_gate(autoid, "blocks_reachability_scope_invalid", `error: case ${autoid} could not seal blocks.kind reachability scope — ${exc instanceof Error ? exc.message : exc}`, { detail: String(exc instanceof Error ? exc.message : exc) });
    }
    if (_mechanical_case_sha) {
      const [_ccSha, _ccProof, _ccError] = _validated_consistency_contract_identity(autoid, { mechanical_case_sha256: _mechanical_case_sha, blocks, consistency_batch_name: _consistency_batch_name });
      if (_ccError) {
        return _reject_compile_gate(autoid, "consistency_contract_invalid", `error: case ${autoid} linked consistency contract is unavailable or identity-stale — ${_ccError}`, { detail: _ccError });
      }
      _consistency_contract_sha = _ccSha;
      _consistency_requirement_proof = _ccProof;
    }
    if (_prov_obj !== null && _bprov !== null && _bprov !== undefined) {
      _prov_obj.steps = _bprov;
      provenance = _prov_obj;
      provenanceJson = "";
    } else if (_prov_obj === null && _bprov && (["0", "false", "no"].includes(String(process.env.IST_PROV_AUTOASSEMBLE ?? "1").trim().toLowerCase()) === false)) {
      provenance = { autoid, steps: _bprov };
      if (_bprov.some((item: any) => _isMapping(item) && item.assertion_type !== null && item.assertion_type !== undefined)) {
        provenance.assertion_schema = "ist.ide.assertion";
      }
      provenanceJson = "";
    }
  }
  let _payload: any[] | null = null;
  let _src = "";
  if (steps !== null && steps !== undefined && !(Array.isArray(steps) && steps.length === 0)) {
    if (Array.isArray(steps)) {
      _payload = [...steps];
    } else {
      _src = String(steps);
    }
  } else if (String(opts.steps_path ?? "").trim()) {
    const sp = String(opts.steps_path ?? "").trim();
    try {
      const { read_bytes } = require("./_sealed_output");
      _src = (read_bytes(sp, { max_bytes: 16 * 1024 * 1024 }) as Buffer).toString("utf8");
    } catch (e) {
      return _record_emit_error_return(autoid, "steps_source_unreadable", `error: steps_path read failed: ${e}`);
    }
  } else if (Array.isArray(opts.steps_json)) {
    _payload = opts.steps_json;
  } else {
    _src = typeof opts.steps_json === "string" ? opts.steps_json : String(opts.steps_json ?? "");
  }
  if (_payload === null) {
    if (!_src.trim()) {
      const _streak = _emit_fail_streak_bump(autoid);
      let _msg = `error: case ${autoid} step payload is empty — none of the four channels blocks/steps/steps_path/steps_json carried valid content (your array argument may have been dropped entirely by vendor serialization). Prefer blocks semantic combinators (native array); use the steps native array for shapes blocks cannot express.`;
      if (_streak >= 2) {
        _msg += `\n→ Consecutive empty payloads: do not retry as-is. First fs_write the steps array to workspace/outputs/${autoid}/steps.json, then pass steps_path=that path — the file channel bypasses argument serialization and cannot be swallowed.`;
      }
      if (_streak >= 3) {
        _msg += `\n⚠ ${_streak} consecutive empty payloads. If steps_path also fails to get through, stop retrying and copy this error verbatim into your reply for the orchestrator to re-dispatch.`;
      }
      return _record_emit_error_return(autoid, "steps_payload_empty", _msg);
    }
    try {
      _payload = JSON.parse(_src);
    } catch (e) {
      const head = JSON.stringify(_src.slice(0, 120));
      const tail = _src.length > 240 ? JSON.stringify(_src.slice(-120)) : "";
      const streak = _emit_fail_streak_bump(autoid);
      let msg = `error: steps_json parse failed: ${e}\nargument actually received (len=${_src.length}) head: ${head}` + (tail ? `\ntail: ${tail}` : "");
      if (streak >= 2) {
        msg += "\n→ Switch channel: pass steps as a native array (not a JSON string), or first fs_write the steps array to workspace/outputs/<autoid>/steps.json and pass steps_path (only outputs/ under workspace is writable) — neither has the trailing-garbage exposure of the string channel.";
      }
      if (streak >= 3) {
        msg += `\n⚠ This case has failed parsing ${streak} times in a row — stop retrying as-is; if switching channels still fails, stop and copy this error verbatim into your reply for the orchestrator to handle.`;
      }
      return _record_emit_error_return(autoid, "steps_payload_parse_failed", msg);
    }
  }
  if (!Array.isArray(_payload) || !_payload.length) {
    return _reject_compile_gate(autoid, "steps_payload_invalid", "error: steps must be a non-empty array (each element a dict with E/F/G)");
  }
  _emit_fail_streak_clear(autoid);
  steps = _payload;
  if (!_using_blocks) {
    try {
      const { classify_capability, all_capability_names } = require("../../../case_compiler/ir_coverage");
      const _touched = _raw_capabilities_touched(steps);
      const _known = all_capability_names();
      const _in_atlas = _touched.filter((c: string) => _known.includes ? _known.includes(c) : _known.has(c));
      const _out_of_atlas = _touched.filter((c: string) => !(_known.includes ? _known.includes(c) : _known.has(c)));
      let _expressible: boolean | null;
      if (_out_of_atlas.length) {
        _expressible = false;
      } else if (_in_atlas.length) {
        _expressible = _in_atlas.every((c: string) => classify_capability(c) === "covered");
      } else {
        _expressible = null;
      }
      const _ir_receipt = _write_ir_gap_touch(autoid, _touched, _expressible, { out_of_atlas: _out_of_atlas, reason: _gap_reason });
      if (_ir_receipt.status !== "durable") {
        return _record_emit_error_return(autoid, "ir_gap_receipt_not_persisted", `error: raw steps IR-gap accounting did not return a durable receipt; the raw emit was rejected before artifact creation (${String(_ir_receipt.error ?? "sink unavailable").slice(0, 160)})`);
      }
    } catch (exc) {
      logger.warning("ir_gap 记账准备失败，raw emit 已拒绝", exc);
      return _record_emit_error_return(autoid, "ir_gap_receipt_unavailable", `error: raw steps IR-gap accounting could not be prepared; the raw emit was rejected before artifact creation (${(exc as any)?.constructor?.name ?? "Error"})`);
    }
  }
  const _sh = require("../compile_engine/_shared");
  let overrideFrozenReason = String(opts.override_frozen_reason ?? "").trim();
  try {
    const _fzPath = new P(String(_sh.outputs_root())).joinpath(autoid, ".frozen.json");
    const _fzPresent = _fzPath.is_file();
    const _fzVerdict = _frozen_seal_verdict(autoid, _mechanical_case_sha, { facts_provider: () => _sh.load_facts({ out_name: String(opts.out_name ?? "") }) });
    if (_fzVerdict[0] !== "not_frozen") {
      const _ov = overrideFrozenReason;
      const _sigNote = _fzVerdict[2] ? `; signatures: ${_fzVerdict[2]}` : "";
      if (_fzVerdict[0] === "same") {
        try {
          const { emit_signal } = require("../../memory/footprint/signals");
          emit_signal("frozen_same_method_refused", autoid, { source: "compile_emit", basis: _fzVerdict[1].slice(0, 200), declared: Boolean(_ov) });
        } catch {}
        return _record_emit_error_return(autoid, "frozen_same_artifact", `error: case ${autoid} is frozen by cross-round on-device comparison (two consecutive rounds failed with the same signature), and this emit carries the same sealed mechanical case as the frozen attempt (${_fzVerdict[1]}${_sigNote}). The digest, not a declaration, is the criterion here: the sheet this emit would write is byte-identical to the one already proven ineffective, so re-running it can only reproduce the same failure. Re-author the mechanical case (different assertion/config/trigger shape); the new seal lifts this rule automatically, no declaration needed. If you judge it an environmental blockage rather than a case defect, check the testbed per ist-verify's stop-loss guidance instead of re-emitting.`);
      }
      if (_fzVerdict[0] === "unavailable" && !_ov) {
        try {
          const { emit_signal } = require("../../memory/footprint/signals");
          emit_signal("gate_disabled", autoid, { source: "compile_emit", gate: "frozen_seal_digest", reason: `seal identity unavailable: ${_fzVerdict[1]}`.slice(0, 200) });
        } catch {}
        return _record_emit_error_return(autoid, "frozen_change_undeclared", `error: case ${autoid} is frozen by cross-round on-device comparison (two consecutive rounds failed with the same signature - the same approach is proven ineffective${_sigNote}). The digest criterion could not run here: ${_fzVerdict[1]}, so this call falls back to the weaker declaration criterion. Pass override_frozen_reason = one sentence on what you changed this time (which kind of assertion/config/trigger). Emitting from a sealed mechanical case makes the digest available and removes this fallback.`);
      }
      const _declared = _ov || `engine seal-digest override: ${_fzVerdict[1]}`;
      let _fzCorrupt = false;
      if (_fzPresent) {
        let _fz: Record<string, any>;
        try {
          _fz = JSON.parse(fs.readFileSync(_fzPath._p).toString("utf8"));
        } catch {
          _fz = {};
          _fzCorrupt = true;
        }
        const _hist = _fz.overrides ?? [];
        _hist.push({ reason: _declared, ts: Date.now() / 1000, seal_verdict: _fzVerdict[0], basis: _fzVerdict[1].slice(0, 200) });
        _fz.overrides = _hist;
        const { _write_json_atomic } = require("./verifiability_tool");
        _write_json_atomic(_fzPath, _fz);
      }
      try {
        const { emit_signal } = require("../../memory/footprint/signals");
        emit_signal("override_frozen", autoid, { source: "compile_emit", reason: _declared.slice(0, 200), seal_verdict: _fzVerdict[0], basis: _fzVerdict[1].slice(0, 200), via_fallback: !_fzPresent, ledger_rebuilt_from_corrupt: _fzCorrupt });
      } catch {}
      overrideFrozenReason = _declared;
    }
  } catch (_fzOsErr) {
    logger.warning("frozen 规则账层文件系统异常(fail-closed 要求 override)", _fzOsErr);
    try {
      const { emit_signal } = require("../../memory/footprint/signals");
      emit_signal("gate_disabled", autoid, { source: "compile_emit", gate: "frozen", reason: `${(_fzOsErr as any)?.constructor?.name ?? "Error"}: ${_fzOsErr}`.slice(0, 200) });
    } catch {}
    return _record_emit_error_return(autoid, "frozen_ledger_unavailable", `error: case ${autoid} - frozen-gate ledger unreadable/unwritable (${(_fzOsErr as any)?.constructor?.name ?? "Error"}: ${_fzOsErr}); cannot verify frozen status, treating as frozen for safety. Fix the underlying filesystem issue, or pass override_frozen_reason to proceed if you are certain this case is not frozen (the override is recorded once the ledger is writable again).`);
  }
  try {
    const _udPath = new P(String(_sh.outputs_root())).joinpath(autoid, "user_decision.json");
    if (_udPath.is_file()) {
      const _ud = JSON.parse(fs.readFileSync(_udPath._p).toString("utf8"));
      const _form = String(_ud.expected_assertion_form ?? "").trim();
      const _fvals = steps.filter((s: any) => _isMapping(s)).map((s: any) => String(s.F ?? "").trim());
      const _hasH = steps.filter((s: any) => _isMapping(s)).some((s: any) => String(s.H ?? "").trim());
      const _need: Record<string, boolean> = { dist: _fvals.includes("dist"), member: _fvals.includes("member"), captured_relation: _hasH };
      if (_form in _need && !_need[_form]) {
        return _record_emit_error_return(autoid, "user_decision_form_mismatch", `error: case ${autoid} violates user decision — the user-approved assertion form is ${_form}, which is absent from the produced steps (F values present: ${[...new Set(_fvals)].sort().join(", ")}, has H capture: ${_hasH}). Rewrite the assertion in the form recorded in user_decision.json; substituting an easier form is not allowed.`);
      }
      const _kinds = _ud.claim_kinds_preserved ?? [];
      const _orderingKinds = new Set(["new_member_last"]);
      try {
        const _ndPath = _udPath.parent.joinpath("needs_decision.json");
        if (_ndPath.is_file()) {
          const _nd = JSON.parse(fs.readFileSync(_ndPath._p).toString("utf8"));
          for (const _c of _nd.claims ?? []) {
            if (_c.ordering_sensitive && _c.claim_kind) {
              _orderingKinds.add(String(_c.claim_kind));
            }
          }
        }
      } catch {}
      if (_kinds.some((k: string) => _orderingKinds.has(k))) {
        const _presents = steps.filter((s: any) => _isMapping(s) && String(s.F ?? "").trim() === "member" && _isMapping(s.member)).map((s: any) => s.member.present);
        if (!(_presents.includes(true) && _presents.includes(false))) {
          return _record_emit_error_return(autoid, "user_decision_ordering_missing", `error: case ${autoid} preserves an ordered-trajectory claim (user_decision's claim_kinds_preserved plus the ledger's ordering_sensitive mark) — the product must carry an ordering anchor: in time order, a not_found segment (target pool member set, member declared present=false) followed by a found segment (present=true). Distribution/participation statistics alone cannot prove ordering — that is a semantic downgrade, refused. If the ordering semantics has been proven unverifiable, report the underdetermination as-is to the orchestrator for the user to revise expectations, and update user_decision.json accordingly.`);
        }
      }
    }
  } catch (exc) {
    logger.warning("user_decision 规则校验异常(拒绝落卷)", exc);
    return _record_emit_error_return(autoid, "user_decision_unreadable", `error: user_decision credential is unreadable; refusing emit: ${(exc as any)?.constructor?.name ?? "Error"}: ${exc}`);
  }
  if (provenance !== null && provenance !== undefined && !(typeof provenance === "string" && !provenance.trim())) {
    if (_isMapping(provenance) || Array.isArray(provenance)) {
      provenanceJson = JSON.stringify(provenance);
    } else if (typeof provenance === "string") {
      provenanceJson = provenance;
    }
  } else if (String(opts.provenance_path ?? "").trim() && !(provenanceJson && provenanceJson.trim())) {
    const _pp = String(opts.provenance_path ?? "").trim();
    try {
      const { read_bytes } = require("./_sealed_output");
      provenanceJson = (read_bytes(_pp, { max_bytes: 16 * 1024 * 1024 }) as Buffer).toString("utf8");
    } catch (_e) {
      return _record_emit_error_return(autoid, "provenance_source_unreadable", `error: provenance_path read failed: ${_e}`);
    }
  }
  if (!(provenanceJson && provenanceJson.trim())) {
    return _record_emit_error_return(autoid, "provenance_required", `error: case ${autoid} missing provenance — pass provenance along with steps (native object with a steps array, each step {layer: G|E|V, source: {kind, ref}}; aligned one-to-one with the sheet steps). It is the sole basis for approval without re-retrieval, four-layer on-device attribution, and PASS write-back to the knowledge base. layer meaning: G=command skeleton (from footprint/manual), E=environment binding (from topology), V=assertion semantics (from Author/Spec/DefectSpec/Manual/ConfigBinding/CapabilityXml claims). A DefectSpec is only an engine-bound safe projection of a fully resolved bug-to-case declaration; it belongs to the Spec authority group and introduces no new category winner.\n\n` + _emit_contract_paths());
  }
  try {
    JSON.parse(provenanceJson);
  } catch {
    return _reject_compile_gate(autoid, "provenance_parse_failed", `error: case ${autoid} provenance parse failed — payload content is withheld. Pass one complete JSON value or use the native object argument.`, { detail: "provenance JSON is not a single complete value" });
  }
  const { expand_distribution_steps, expand_provenance_steps_with_plan } = require("../../../case_compiler/distribution_assertion");
  const _distSourceSteps = steps;
  const [_distSteps, _distPlan, _distErr] = expand_distribution_steps(steps);
  steps = _distSteps;
  if (_distErr) {
    return _record_emit_error_return(autoid, "distribution_declaration_invalid", `error: case ${autoid} distribution-interval assertion declaration is invalid: ${_distErr}`);
  }
  if (provenanceJson && provenanceJson.trim()) {
    try {
      const _pj = JSON.parse(provenanceJson);
      if (_isMapping(_pj)) {
        _pj.steps = expand_provenance_steps_with_plan(_pj.steps, _distPlan, { source_steps: _distSourceSteps, expanded_steps: steps });
        provenanceJson = JSON.stringify(_pj);
      }
    } catch (exc) {
      return _record_emit_error_return(autoid, "distribution_binding_invalid", `error: case ${autoid} ConfigBinding distribution receipt could not be recomputed: ${exc}`);
    }
  }
  const { attach_membership_derivation_receipts, expand_membership_steps } = require("../../../case_compiler/membership_assertion");
  const _memberSourceSteps = steps;
  const [_memberSteps, _memberErr] = expand_membership_steps(steps);
  steps = _memberSteps;
  if (_memberErr) {
    return _record_emit_error_return(autoid, "membership_declaration_invalid", `error: case ${autoid} hit-membership assertion declaration is invalid: ${_memberErr}`);
  }
  if (provenanceJson && provenanceJson.trim()) {
    try {
      const _pj = JSON.parse(provenanceJson);
      if (_isMapping(_pj)) {
        _pj.steps = attach_membership_derivation_receipts(_pj.steps, _memberSourceSteps, steps);
        provenanceJson = JSON.stringify(_pj);
      }
    } catch (exc) {
      return _record_emit_error_return(autoid, "membership_binding_invalid", `error: case ${autoid} ConfigBinding membership receipt could not be recomputed: ${exc}`);
    }
  }
  if (provenanceJson && provenanceJson.trim()) {
    const {
      backfill_efg: _preflight_backfill_efg,
      check_runtime_consistency: _preflight_runtime_consistency,
      check_source_locators: _preflight_check_source_locators,
      compile_expect_authority: _preflight_compile_expect_authority,
      parse_provenance: _preflight_parse_provenance,
    } = require("../../../case_compiler/provenance_ir");
    let _preflightRaw: any = null;
    try {
      _preflightRaw = JSON.parse(provenanceJson);
    } catch {
      _preflightRaw = null;
    }
    if (_isMapping(_preflightRaw)) {
      for (const _rawStep of _preflightRaw.steps ?? []) {
        const _rawSource = _isMapping(_rawStep) ? _rawStep.source : null;
        if (_isMapping(_rawSource) && String(_rawSource.kind ?? "") === "poison_confirmed") {
          const { validate_package_expect_reference } = require("../../../case_compiler/package_advisories");
          const _assetId = String(_rawSource.ref ?? "-");
          const _packageError = validate_package_expect_reference(_assetId, "poison_confirmed");
          return _reject_compile_gate(autoid, "package_reference_denied", _packageError, { detail: _packageError });
        }
      }
    }
    const _preflightCase = _preflight_parse_provenance(provenanceJson);
    if (_preflightCase === null || _preflightCase === undefined) {
      let _bad: string;
      try {
        JSON.parse(provenanceJson);
        _bad = "JSON parses but the structure does not conform (need {autoid, steps:[{layer,source:{kind,ref}},…]})";
      } catch (_je) {
        _bad = `the JSON itself is broken: ${_je}`;
      }
      return _reject_compile_gate(autoid, "provenance_parse_failed", `error: case ${autoid} provenance parse failed — ${_bad}; payload content is withheld. Pass provenance as a native object argument; do not serialize a JSON string into another string channel.`, { detail: _bad });
    }
    _preflightCase.autoid = autoid;
    if (!_preflight_backfill_efg(_preflightCase, steps)) {
      return _reject_compile_gate(autoid, "provenance_step_count_mismatch", `error: case ${autoid} provenance step count (${_preflightCase.steps.length}) does not match emit steps count (${steps.length}). Provide exactly one source entry per final step.`, { detail: `provenance steps=${_preflightCase.steps.length} emit steps=${steps.length}` });
    }
    const _preflightProblems = [
      ..._preflight_check_source_locators(_preflightCase, { outputs_root: _sh.outputs_root() }),
      ..._preflight_runtime_consistency(_preflightCase),
      ..._preflight_compile_expect_authority(_preflightCase),
    ];
    if (_preflightProblems.length) {
      const _packageProblem = _preflightProblems.find((p: string) => p.startsWith("E_PACKAGE_REFERENCE_DENIED") || p.startsWith("E_PACKAGE_INDEX_UNAVAILABLE")) ?? "";
      if (_packageProblem) {
        return _reject_compile_gate(autoid, "package_reference_denied", _packageProblem, { detail: _packageProblem });
      }
      return _reject_compile_gate(autoid, "provenance_source_unresolved", `error: case ${autoid} violates the provenance/no-fabrication contract:\n  - ` + _preflightProblems.join("\n  - ") + "\n\nEvery command/method/action and expected value needs a resolvable source receipt. For values unknowable offline, use <RUNTIME> with source.kind=device_runtime.", { detail: _preflightProblems.join("\n") });
    }
  }
  let _mutationValue: any = opts.mutation_requirements ?? null;
  if (String(opts.mutation_requirements_path ?? "").trim() && (_mutationValue === null || _mutationValue === "" || (Array.isArray(_mutationValue) && _mutationValue.length === 0))) {
    const _frp = String(opts.mutation_requirements_path ?? "").trim();
    try {
      const { read_json } = require("./_sealed_output");
      _mutationValue = read_json(_frp, { max_bytes: 16 * 1024 * 1024 });
    } catch (exc) {
      return _reject_compile_gate(autoid, "mutation_contract_invalid", `error: mutation_requirements_path could not be read: ${exc}`, { detail: `mutation requirements path unreadable: ${(exc as any)?.constructor?.name ?? "Error"}` });
    }
  }
  const { compile_mutation_plan } = require("../../../case_compiler/mutation_testing");
  let _provForMutation: any = null;
  if (provenanceJson && provenanceJson.trim()) {
    try {
      const _candidateProv = JSON.parse(provenanceJson);
      if (_isMapping(_candidateProv)) _provForMutation = _candidateProv;
    } catch {}
  }
  if (_isMapping(_provForMutation) && !_provForMutation.assertion_schema && !_using_blocks) {
    return _reject_compile_gate(autoid, "assertion_type_missing", `error: case ${autoid} raw provenance is untyped; project it to ist.ide.assertion before compile_emit`, { detail: "raw provenance omitted assertion_schema" });
  }
  if (_isMapping(_provForMutation) && !_provForMutation.assertion_schema) {
    try {
      const { CaseProvenance, backfill_efg, synthesize_assertion_types } = require("../../../case_compiler/provenance_ir");
      const _typedCase = CaseProvenance.from_dict(_provForMutation);
      _typedCase.autoid = autoid;
      const _typedErrors: string[] = [];
      if (!backfill_efg(_typedCase, steps)) {
        _typedErrors.push("provenance steps are not aligned with the final emit steps");
      } else {
        _typedErrors.push(...synthesize_assertion_types(_typedCase));
      }
      if (_typedErrors.length) {
        return _reject_compile_gate(autoid, "assertion_type_derivation_failed", `error: case ${autoid} cannot enter the typed IDE path:\n  - ` + _typedErrors.join("\n  - "), { detail: _typedErrors.join("\n") });
      } else {
        _provForMutation = _typedCase.to_dict();
      }
    } catch (exc) {
      return _reject_compile_gate(autoid, "assertion_type_derivation_failed", `error: case ${autoid} typed assertion derivation failed: ${exc}`, { detail: `typed assertion derivation failed: ${(exc as any)?.constructor?.name ?? "Error"}` });
    }
  }
  const _mutationRequired = Boolean(_isMapping(_provForMutation) && accepts_schema(_provForMutation.assertion_schema, "ist.ide.assertion"));
  let _deviceBuild = "";
  let _deviceBuildSource = "";
  try {
    const { current_worker_device_session } = require("../worker_device_context");
    const _mutationSession = current_worker_device_session();
    if (_mutationSession !== null && _mutationSession !== undefined) {
      _deviceBuild = String(_mutationSession.expected_build ?? "").trim();
      if (_deviceBuild) _deviceBuildSource = "worker_session";
    }
  } catch {}
  if (!_deviceBuild) {
    try {
      const { configured_device_os_build } = require("../../../case_compiler/vendor_stdlib");
      _deviceBuild = String(configured_device_os_build() ?? "").trim();
      if (_deviceBuild) _deviceBuildSource = "configured_fallback";
    } catch {}
  }
  const _bindingBeforeMutation = _binding_steps_from_provenance(_isMapping(_provForMutation) ? (_provForMutation.steps ?? []) : []);
  const [_mutSteps, _mutProv, _mutationReceipt, _mutationError] = compile_mutation_plan(steps, _provForMutation, _mutationValue, { required: _mutationRequired, derive_defaults: _mutationRequired, device_build: _deviceBuild, device_build_source: _deviceBuildSource });
  steps = _mutSteps;
  if (_mutationError) {
    return _reject_compile_gate(autoid, "mutation_contract_invalid", `error: case ${autoid} has an invalid IDE mutation contract — ${_mutationError}`, { detail: _mutationError });
  }
  if (_mutProv !== null && _mutProv !== undefined) {
    _provForMutation = _mutProv;
    provenanceJson = JSON.stringify(_provForMutation);
  }
  const { emit_xlsx } = require("../../../../ist_emit/xlsx_emit");
  const { make_FileIR, make_CaseIR, make_Step } = require("../../../../ist_emit/case_ir");
  const { get_config } = require("../../../case_compiler/config");
  let initG = String(opts.init_commands ?? "").trim() ? String(opts.init_commands).trim() : get_config().default_init_g();
  let _fixedLiteralN = 0;
  if (initG.includes("\\n")) {
    initG = initG.replace(/\\n/g, "\n");
    _fixedLiteralN += 1;
  }
  if (Array.isArray(steps)) {
    for (const _s of steps) {
      if (!_isMapping(_s)) continue;
      if (["APV_0", "test_env"].includes(String(_s.E ?? "").trim())) {
        const _g = _s.G;
        if (typeof _g === "string" && _g.includes("\\n")) {
          _s.G = _g.replace(/\\n/g, "\n");
          _fixedLiteralN += 1;
        }
      }
    }
  }
  if (initG.includes("，")) {
    initG = initG.replace(/，/g, ",");
  }
  if (Array.isArray(steps)) {
    for (const _s of steps) {
      if (!_isMapping(_s) || String(_s.E ?? "").trim() === "check_point") continue;
      const _g = _s.G;
      if (typeof _g === "string" && _g.includes("，")) {
        _s.G = _g.replace(/，/g, ",");
      }
    }
  }
  const stepRows = (steps as any[]).map((s: any) => make_Step({ D: String(s?.desc ?? s?.D ?? ""), E: String(s?.E ?? ""), F: String(s?.F ?? ""), G: s?.G ?? "", H: String(s?.H ?? ""), I: s?.I ?? "" }));
  const caseIr = make_CaseIR({ autoid, title: autoid, init_g: initG, steps: stepRows });
  const fileIr = make_FileIR({ cases: [caseIr] });
  const outDir = new P(String(_sh.outputs_root())).joinpath(String(opts.out_name ?? "").trim() || autoid);
  let outPath: string;
  try {
    outPath = emit_xlsx(fileIr, outDir.joinpath("case.xlsx")._p, { allow_legacy: true });
  } catch (exc) {
    return _record_emit_error_return(autoid, "xlsx_emit_failed", `error: xlsx emission failed: ${exc}`);
  }
  const xlsxSha256 = crypto.createHash("sha256").update(fs.readFileSync(outPath)).digest("hex");
  const xlsxMtimeNs = (() => {
    try {
      const st = fs.statSync(outPath);
      return Number(st.mtimeMs) * 1e6;
    } catch {
      return 0;
    }
  })();
  const _reachabilityScopeDict = _reachability_scope.asDict();
  const _recordedAuthorValues = _recorded_author_ip_literals(autoid, { xlsx_sha256: xlsxSha256 });
  const _credential: Record<string, any> = {
    schema: "ist.grade-credential",
    autoid,
    xlsx_sha256: xlsxSha256,
    xlsx_mtime_ns: xlsxMtimeNs,
    reachability_scope: _reachabilityScopeDict,
    unreachable_ip_admission: _unreachable_ip_admission(autoid, steps, { init: initG }),
    expected_save_variant: String(opts.expected_save_variant ?? "").trim() || _intent_save_variant(autoid),
    mechanical_case_sha256: _mechanical_case_sha || null,
    consistency_contract_sha256: _consistency_contract_sha,
    consistency_requirement_proof: _consistency_requirement_proof,
    capability_consumed: _workerCapabilityReceipt,
    override_frozen_reason: overrideFrozenReason || null,
    coverage_reduction_reason: String(opts.coverage_reduction_reason ?? "").trim() || null,
    gate_mailbox_version: GATE_MAILBOX_VERSION,
    ts: Date.now() / 1000,
  };
  const credPath = new P(String(_sh.outputs_root())).joinpath(autoid, ".grade_credential.json");
  try {
    fs.mkdirSync(credPath.parent._p, { recursive: true });
    fs.writeFileSync(credPath._p, JSON.stringify(_credential, null, 2) + "\n", "utf8");
  } catch (exc) {
    return _record_emit_error_return(autoid, "credential_write_failed", `error: lint credential could not be written: ${exc}`);
  }
  const { lint_draft } = require("./structural_gate");
  const lintResult = lint_draft(steps, { init: initG, final: true, device_build: _deviceBuild, author_ip_literals: _recordedAuthorValues, author_driver_hits: null });
  if (!lintResult.ok) {
    _write_gate_rejections(autoid, lintResult.violations, { stage: "emit" });
    return _record_emit_error_return(autoid, "structural_gate_violation", lintResult.render(autoid));
  }
  if (lintResult.disabled.length) {
    _write_gate_disabled(autoid, lintResult.disabled, { stage: "emit" });
  }
  const _fixNote = _fixedLiteralN ? `\n⚠ Auto-corrected ${_fixedLiteralN} literal backslash-n occurrence(s) in command text (E in (APV_0, test_env)) before emission.` : "";
  return `case.xlsx written: ${outPath}\nsha256: ${xlsxSha256}\nlint credential: ${credPath._p}\nreachability_scope: ${JSON.stringify(_reachabilityScopeDict)}${_fixNote}`;
}

function _frozen_seal_verdict(autoid: string, newSealSha256: string, opts: { facts?: any[] | null; facts_provider?: (() => any[]) | null } = {}): [string, string, string] {
  const { EngineSealError, load_seal } = require("../../../case_compiler/mechanical_case");
  let facts = opts.facts ?? null;
  if (facts === null && opts.facts_provider) {
    try {
      facts = opts.facts_provider();
    } catch {
      facts = null;
    }
  }
  if (!Array.isArray(facts) || !facts.length) {
    return ["unavailable", "no prior producer fact is on file for this case", ""];
  }
  let priorSha = "";
  let priorRound = "";
  let sigText = "";
  for (const fact of facts) {
    if (!_isMapping(fact)) continue;
    const fSeal = fact.seal ?? fact.mechanical_case_sha256 ?? "";
    const fRound = fact.round ?? "";
    const fSig = fact.signature ?? fact.failure_signature ?? "";
    if (fSeal) {
      priorSha = String(fSeal);
      priorRound = String(fRound);
      sigText = String(fSig ?? "");
    }
  }
  if (!priorSha) {
    return ["unavailable", "fact ledger shows frozen but no prior producer fact is on file (frozen file missing; cross-batch continuation)", sigText];
  }
  if (!newSealSha256) {
    return ["unavailable", "no seal digest available to compare against the frozen prior", sigText];
  }
  if (priorSha === newSealSha256) {
    return ["same", `seal digest ${newSealSha256.slice(0, 12)}… equals the frozen attempt's (round ${priorRound})`, sigText];
  }
  return ["not_frozen", "", ""];
}

export function engine_frozen_override_reason(autoid: string, newSealSha256: string, opts: { facts?: any[] | null; attribution_note?: string } = {}): string {
  const [verdict, basis, sigText] = _frozen_seal_verdict(autoid, newSealSha256, { facts: opts.facts ?? null });
  if (verdict === "same") {
    return "";
  }
  if (verdict === "not_frozen") {
    return "case is not frozen; no override reason is needed";
  }
  const note = String(opts.attribution_note ?? "").trim();
  const sigNote = sigText ? `; signatures: ${sigText}` : "";
  return `override: ${basis}${sigNote}${note ? `; ${note}` : ""}`;
}

function _write_ir_gap_touch(aid: string, capabilities: string[], expressible: boolean | null, opts: { out_of_atlas?: string[]; reason?: string } = {}): Record<string, any> {
  try {
    const { report_ir_gap_touch } = require("../../../case_compiler/ir_gap_touch");
    return report_ir_gap_touch({ autoid: aid, capabilities: [...capabilities], expressible, out_of_atlas: [...(opts.out_of_atlas ?? [])], reason: String(opts.reason ?? "") });
  } catch (exc) {
    return { status: "failed", schema: "ist.compile.ir_gap_receipt", error: (exc as any)?.constructor?.name ?? "Error" };
  }
}

function _raw_capabilities_touched(steps: any[]): string[] {
  const names = new Set<string>();
  for (const s of steps ?? []) {
    if (!_isMapping(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    if (!e || !f) continue;
    if (e === "check_point" || e === "time") continue;
    names.add(f);
  }
  return [...names].sort();
}

const _CURRENT_ENGINE_DEFECT_CHANNEL: { value: Record<string, any> | null } = { value: null };

export function engine_defect_channel<T>(fn: () => T): [T, Record<string, any> | null] {
  const previous = _CURRENT_ENGINE_DEFECT_CHANNEL.value;
  const channel: Record<string, any> = { defects: [] };
  _CURRENT_ENGINE_DEFECT_CHANNEL.value = channel;
  try {
    return [fn(), channel.defects.length ? channel : null];
  } finally {
    _CURRENT_ENGINE_DEFECT_CHANNEL.value = previous;
  }
}

function _signal_engine_defect(kind: string, detail: Record<string, any>): void {
  const channel = _CURRENT_ENGINE_DEFECT_CHANNEL.value;
  if (channel !== null) {
    channel.defects.push({ kind, ...detail });
  }
}

export function _canonical_json_sha256(value: any): string {
  return crypto.createHash("sha256").update(_canonicalJsonString(value), "utf8").digest("hex");
}

function _canonicalJsonString(value: any): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new PyValueError("canonical JSON refuses non-finite numbers");
    return String(value);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map((item) => _canonicalJsonString(item)).join(",") + "]";
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((key) => `${JSON.stringify(key)}:${_canonicalJsonString(value[key])}`).join(",") + "}";
  }
  return JSON.stringify(String(value));
}

export function mechanical_findings_for_emit(autoid: string, blocks: any, init_commands = ""): Array<Record<string, any>> {
  if (!Array.isArray(blocks) || !blocks.length) return [];
  try {
    const { mechanical_findings } = require("../../../case_compiler/device_characteristics");
    let bed: any = null;
    try {
      bed = require("../compile_engine/briefs")._bed_facts();
    } catch {
      bed = null;
    }
    const initLines = String(init_commands ?? "").split("\n").map((line) => line.trim()).filter((line) => line);
    return mechanical_findings({ blocks, init_commands: initLines }, { bed_facts: bed });
  } catch (exc) {
    logger.warning(`交卷机械发现计算失败(autoid=${autoid})`, exc);
    return [];
  }
}

export function _render_mechanical_findings(findings: Array<Record<string, any>>): string {
  if (!findings || !findings.length) return "";
  const slim = findings.map((item) => {
    const out: Record<string, any> = {};
    for (const [key, value] of Object.entries(item)) {
      if (key !== "quote") out[key] = value;
    }
    return out;
  });
  const lines: string[] = [
    "",
    `mechanical findings: ${findings.length} (disclosure only — this submission is accepted and no rule rejected it):`,
    "mechanical_findings: " + JSON.stringify(slim),
  ];
  for (const item of findings) {
    const code = String(item.code ?? "");
    const locator = String(item.locator ?? "");
    const quote = String(item.text ?? item.quote ?? "").split(/\s+/).filter(Boolean).join(" ");
    const parts: string[] = [`  - ${code}`];
    if (item.host) parts.push(`host=${item.host}`);
    if (item.target) parts.push(`target=${item.target}`);
    if (item.paired_hosts !== null && item.paired_hosts !== undefined) parts.push(`paired_hosts=${JSON.stringify(item.paired_hosts ?? [])}`);
    if (item.configured_blocks) parts.push(`configured_blocks=${JSON.stringify(item.configured_blocks)}`);
    if (item.observed_blocks) parts.push(`observed_blocks=${JSON.stringify(item.observed_blocks)}`);
    lines.push(parts.join(" "));
    if (quote && locator) {
      lines.push(`    documentation (${locator}): ${quote}`);
    }
  }
  return lines.join("\n");
}

export function _append_gate_event_log(records: Array<Record<string, any>>): Array<Record<string, any>> {
  if (!records || !records.length) return [];
  try {
    const { runtime_path } = require("../../../common/runtime_paths");
    const p = new P(String(runtime_path("logs", "gate_events.jsonl")));
    fs.mkdirSync(p.parent._p, { recursive: true });
    const references: Array<Record<string, any>> = [];
    const fh = fs.openSync(p._p, "a");
    try {
      for (const rec of records) {
        const raw = Buffer.from(_canonicalJsonString(rec) + "\n", "utf8");
        const offset = fs.fstatSync(fh).size;
        fs.writeSync(fh, raw);
        const info = fs.fstatSync(fh);
        references.push({
          offset,
          length: raw.length,
          device: (info as any).dev ?? 0,
          inode: (info as any).ino ?? 0,
          sha256: crypto.createHash("sha256").update(raw).digest("hex"),
        });
      }
      fs.fsyncSync(fh);
    } finally {
      fs.closeSync(fh);
    }
    return references;
  } catch (exc) {
    logger.debug("gate_events 记账失败(不改变规则本身裁决)", exc);
    return [];
  }
}

function _gate_redact(text: string): string {
  try {
    return String(require("../../../case_compiler/device_mcp_client")._redact(text));
  } catch {
    return "[gate detail omitted: redactor unavailable]";
  }
}

function _redactExtra(value: any): any {
  if (typeof value === "string") return _gate_redact(value);
  if (Array.isArray(value)) return value.map((item) => _redactExtra(item));
  if (_isMapping(value)) {
    const out: Record<string, any> = {};
    for (const [key, item] of Object.entries(value)) out[String(key)] = _redactExtra(item);
    return out;
  }
  return value;
}

export function _gate_records(autoid: string, items: any[], opts: { ev: string; stage: string; extra?: Record<string, any> | null }): Array<Record<string, any>> {
  const { ev, stage } = opts;
  const extra = opts.extra ?? null;
  const now = Date.now() / 1000;
  const redactedExtra: Record<string, any> = {};
  for (const [key, value] of Object.entries(extra ?? {})) redactedExtra[String(key)] = _redactExtra(value);
  const records: Array<Record<string, any>> = [];
  let index = 0;
  for (const item of items ?? []) {
    index += 1;
    const gate = String(item?.code ?? "");
    const stepIndex = Number(item?.step_index ?? -1);
    const seed = `${autoid}|${ev}|${stage}|${gate}|${stepIndex}|${process.hrtime.bigint().toString()}|${index}|${process.pid}`;
    const record: Record<string, any> = {
      ev,
      aid: String(autoid ?? "").trim(),
      gate,
      step_index: stepIndex,
      stage: String(stage ?? ""),
      ts: now,
      occurrence_id: crypto.createHash("sha256").update(seed, "utf8").digest("hex"),
      ...redactedExtra,
    };
    const text = _gate_redact(String(item?.detail ?? "")).slice(0, 400);
    if (ev === "gate_rejected") record.detail = text;
    else record.reason = text;
    records.push(record);
  }
  return records;
}

export function _gate_mailbox_occurrence_id(autoid: string, opts: { ev: string; item: Record<string, any>; index: number }): string {
  const existing = String(opts.item?.occurrence_id ?? "").trim();
  if (existing) return existing;
  const canonical: Record<string, any> = {};
  for (const [key, value] of Object.entries(opts.item ?? {})) {
    if (key !== "occurrence_id") canonical[key] = value;
  }
  const payload = { schema: "ist.compile.gate_mailbox.legacy_identity", aid: String(autoid ?? "").trim(), ev: opts.ev, index: Math.trunc(opts.index), item: canonical };
  return crypto.createHash("sha256").update(_canonicalJsonString(payload), "utf8").digest("hex");
}

export function _gate_mailbox_records(autoid: string, data: Record<string, any>): [Array<Record<string, any>>, Array<Record<string, any>>, Array<Record<string, any>>] {
  const hits: Array<Record<string, any>> = [];
  const disabled: Array<Record<string, any>> = [];
  const advisories: Array<Record<string, any>> = [];
  const collect = (key: string, ev: string, out: Array<Record<string, any>>): void => {
    let index = 0;
    for (const raw of (data?.[key] ?? []) as any[]) {
      index += 1;
      if (!_isMapping(raw)) continue;
      const item = { ...raw };
      item.occurrence_id = _gate_mailbox_occurrence_id(autoid, { ev, item, index });
      out.push(item);
    }
  };
  collect("hits", "gate_rejected", hits);
  collect("disabled", "gate_disabled", disabled);
  collect("advisories", "gate_advisory", advisories);
  return [hits, disabled, advisories];
}

export function _write_gate_advisories(autoid: string, advisories: any[], opts: { stage?: string } = {}): Array<Record<string, any>> {
  const records = _gate_records(autoid, advisories ?? [], { ev: "gate_advisory", stage: opts.stage ?? "emit" });
  _gateMailboxLockAcquire();
  try {
    const _sh = require("../compile_engine/_shared");
    const p = new P(String(_sh.outputs_root())).joinpath(String(autoid).trim(), "gate_rejections.json");
    fs.mkdirSync(p.parent._p, { recursive: true });
    let existing: Record<string, any> = {};
    if (p.is_file()) {
      try {
        existing = JSON.parse(fs.readFileSync(p._p).toString("utf8"));
      } catch {
        existing = {};
      }
    }
    if (!_isMapping(existing)) existing = {};
    const items = Array.isArray(existing.advisories) ? existing.advisories : [];
    items.push(...records);
    existing.schema = "ist.compile.gate_mailbox";
    existing.advisories = items;
    _durable_json_replace(p, existing);
  } catch (exc) {
    logger.debug("gate_advisory 落盘失败(不阻断 emit 主流程)", exc);
  } finally {
    _gateMailboxLockRelease();
  }
  return records;
}

export function _peek_gate_mailbox(autoid: string): [Array<Record<string, any>>, Array<Record<string, any>>, Array<Record<string, any>>] {
  const _sh = require("../compile_engine/_shared");
  const p = new P(String(_sh.outputs_root())).joinpath(String(autoid).trim(), "gate_rejections.json");
  _gateMailboxLockAcquire();
  try {
    if (!p.is_file() || p.is_symlink()) return [[], [], []];
    let data: any;
    try {
      data = JSON.parse(fs.readFileSync(p._p).toString("utf8"));
    } catch {
      logger.warning(`gate mailbox 不可读(autoid=${autoid})，保留原文件待审计`);
      return [[], [], []];
    }
    if (!_isMapping(data)) {
      logger.warning(`gate mailbox 根对象无效(autoid=${autoid})，保留原文件待审计`);
      return [[], [], []];
    }
    return _gate_mailbox_records(autoid, data);
  } finally {
    _gateMailboxLockRelease();
  }
}

export function _ack_gate_mailbox(autoid: string, occurrence_ids: Iterable<string>): number {
  const expected = new Set<string>([...occurrence_ids].map((value) => String(value ?? "").trim()).filter((value) => value));
  if (!expected.size) return 0;
  const _sh = require("../compile_engine/_shared");
  const p = new P(String(_sh.outputs_root())).joinpath(String(autoid).trim(), "gate_rejections.json");
  _gateMailboxLockAcquire();
  try {
    if (!p.is_file() || p.is_symlink()) return 0;
    let data: any;
    try {
      data = JSON.parse(fs.readFileSync(p._p).toString("utf8"));
    } catch {
      logger.warning(`gate mailbox ack 前不可读(autoid=${autoid})，保留原文件待审计`);
      return 0;
    }
    if (!_isMapping(data)) return 0;
    const [hits, disabled, advisories] = _gate_mailbox_records(autoid, data);
    const keep = (items: Array<Record<string, any>>) => items.filter((item) => !expected.has(String(item.occurrence_id ?? "")));
    const keptHits = keep(hits);
    const keptDisabled = keep(disabled);
    const keptAdvisories = keep(advisories);
    const acknowledged = hits.length + disabled.length + advisories.length - keptHits.length - keptDisabled.length - keptAdvisories.length;
    if (!acknowledged) return 0;
    if (keptHits.length || keptDisabled.length || keptAdvisories.length) {
      data.schema = "ist.compile.gate_mailbox";
      data.hits = keptHits;
      data.disabled = keptDisabled;
      data.advisories = keptAdvisories;
      _durable_json_replace(p, data);
      return acknowledged;
    }
    try {
      fs.unlinkSync(p._p);
    } catch (exc) {
      logger.warning(`gate mailbox 已确认但 ack 删除失败(autoid=${autoid})`, exc);
      return 0;
    }
    return acknowledged;
  } finally {
    _gateMailboxLockRelease();
  }
}

export function _drain_gate_mailbox(autoid: string): [Array<Record<string, any>>, Array<Record<string, any>>, Array<Record<string, any>>] {
  const [hits, disabled, advisories] = _peek_gate_mailbox(autoid);
  _ack_gate_mailbox(autoid, [...hits, ...disabled, ...advisories].map((item) => String(item.occurrence_id ?? "")));
  return [hits, disabled, advisories];
}

export function _durable_json_replace(path: P, obj: Record<string, any>): string {
  const _sh = require("../compile_engine/_shared");
  const root = String(_sh.outputs_root());
  const absolutePath = nodePath.resolve(path._p);
  const absoluteRoot = nodePath.resolve(root);
  const relative = nodePath.relative(absoluteRoot, absolutePath);
  if (!relative || relative.startsWith("..") || nodePath.isAbsolute(relative)) {
    throw new Error("durable JSON sink escaped workspace outputs");
  }
  const parts = relative.split(nodePath.sep).filter((part) => part);
  if (parts.length < 2 || parts.includes("..")) {
    throw new Error("durable JSON sink has an invalid output-relative path");
  }
  const payload = Buffer.from(JSON.stringify(obj, null, 2) + "\n", "utf8");
  const { atomic_write_bytes_nofollow } = require("../../../case_compiler/_sealed_io");
  return String(atomic_write_bytes_nofollow(path._p, payload, {
    error_type: Error,
    invalid_message: "durable JSON sink has an invalid path",
    unavailable_message: "durable JSON sink transaction failed",
    create_parents: true,
    mode: 0o600,
  }));
}

export function _probe_ir_gap_sink(scopeName: string): Record<string, any> {
  try {
    const _sh = require("../compile_engine/_shared");
    const safeScope = _safe_output_component(scopeName, "out_name");
    const probeId = crypto.randomBytes(32).toString("hex") + crypto.createHash("sha256").update(process.hrtime.bigint().toString(), "utf8").digest("hex");
    const p = new P(String(_sh.outputs_root())).joinpath(safeScope, `.ir_gap_probe.${probeId}.json`);
    const payload = { schema: "ist.compile.ir_gap_sink_probe", probe_id: probeId };
    const digest = _durable_json_replace(p, payload);
    const loaded = JSON.parse(fs.readFileSync(p._p).toString("utf8"));
    if (JSON.stringify(loaded) !== JSON.stringify(payload)) {
      throw new Error("ir_gap sink probe payload mismatch");
    }
    fs.unlinkSync(p._p);
    return { status: "healthy", schema: "ist.compile.ir_gap_sink_health", probe_id: probeId, receipt_sha256: digest };
  } catch (exc) {
    logger.warning("ir_gap sink 健康探针失败", exc);
    return { status: "unhealthy", schema: "ist.compile.ir_gap_sink_health", error: (exc as any)?.constructor?.name ?? "Error" };
  }
}

export function _write_frozen_override_ack(autoid: string, reason: string, xlsxPath: P): void {
  try {
    const { _write_json_atomic } = require("./verifiability_tool");
    const _sh = require("../compile_engine/_shared");
    const ackPath = new P(String(_sh.outputs_root())).joinpath(String(autoid).trim(), ".frozen_override_ack.json");
    const mtime = fs.statSync(xlsxPath._p).mtimeMs / 1000;
    _write_json_atomic(ackPath, { reason: String(reason ?? "").trim().slice(0, 200), ts: Date.now() / 1000, xlsx_mtime: mtime });
  } catch (exc) {
    logger.debug("frozen override ack 落盘失败(不阻断 emit)", exc);
  }
}

export function _gate_observability(autoid: string, opts: { gate: string; state: string; [key: string]: any }): void {
  try {
    const { runtime_path } = require("../../../common/runtime_paths");
    const { gate, state, ...extra } = opts;
    const p = new P(String(runtime_path("logs", "gate_observability.jsonl")));
    fs.mkdirSync(p.parent._p, { recursive: true });
    fs.appendFileSync(p._p, JSON.stringify({ ts: Date.now() / 1000, autoid: String(autoid), gate, state, ...extra }) + "\n", "utf8");
  } catch (exc) {
    logger.debug("gate observability 追加失败", exc);
  }
}

export const MERGE_LEDGER_PENDING_REASONS: readonly string[] = ["存在未裁或裁决身份不匹配的盘上冲突，拒绝合并", "未决冲突台账不可读，拒绝合并", "裁决台账不可读，拒绝合并", "批级来源冲突裁决要求停止编写或放弃整批，不得合并", "用户裁决为停止编写或放弃本次生成，不得合并"];
export const MERGE_XML_ABSENCE_REASON = "设备 XML 命令树未收录用例命令，设备不支持这个功能";

export function merge_reason_is_ledger_pending(reason: string | null | undefined): boolean {
  const text = String(reason ?? "");
  return MERGE_LEDGER_PENDING_REASONS.some((token) => text.startsWith(token));
}

export function merge_reason_is_xml_absence(reason: string | null | undefined): boolean {
  return String(reason ?? "").startsWith(MERGE_XML_ABSENCE_REASON);
}

function _stepsToCaseir(autoid: string, steps: any[], opts: { title?: string } = {}): [any | null, string] {
  const { CaseIR, Row, Step } = require("../../../case_compiler/case_ir");
  const { capture_register_final_operator } = require("../../../case_compiler/blocks");
  const istSteps: any[] = [];
  let hasCp = false;
  const seenVars = new Set<string>();
  for (const [i, s] of (steps ?? []).entries()) {
    if (!_isMapping(s)) return [null, `step[${i}] is not a dict`];
    const e = String(s.E ?? "").trim();
    let f = String(s.F ?? "").trim();
    if (!e || !f) return [null, `step[${i}] is missing E or F`];
    if (e === "test_env") f = f.toLowerCase();
    let gVal = String(s.G ?? "");
    let hVal = s.H ?? null;
    if (e === "check_point" && !hVal && seenVars.has(gVal)) {
      hVal = gVal;
      gVal = "";
    }
    if (e === "check_point") {
      hasCp = true;
      f = capture_register_final_operator(f, hVal);
      s.F = f;
      s.G = gVal;
      if (hVal) s.H = hVal;
    } else if (hVal) {
      seenVars.add(String(hVal));
    }
    const iVal = s.I !== null && s.I !== undefined ? String(s.I) : null;
    const row = new Row({ test_object: e, method: f, data: gVal, save_as: hVal, input_var: iVal });
    istSteps.push(new Step({ stmt_type: 2 + i, description: String(s.desc ?? ""), rows: [row] }));
  }
  if (!hasCp) {
    return [null, `case ${autoid} has no check_point step at all — it is bound to fail on-device (pass requires success>0). Add a found assertion.`];
  }
  const caseIr = new CaseIR({ autoid, priority: "P1", title: opts.title || `agent_${autoid}`, steps: istSteps });
  return [caseIr, ""];
}

function _buildSentinel(): any {
  const { CaseIR, Row, Step } = require("../../../case_compiler/case_ir");
  return new CaseIR({
    autoid: "000000000000000000",
    priority: "P9",
    title: "sentinel-do-not-execute",
    steps: [new Step({ stmt_type: 2, description: "sentinel", rows: [new Row({ test_object: "time", method: "sleep", data: "1" })] })],
  });
}

function _parseAutoidsArg(autoids: string | string[] | null | undefined): [string[] | null, string | null] {
  if (autoids === null || autoids === undefined) return [null, null];
  if (Array.isArray(autoids)) {
    if (!autoids.length) return [null, null];
    const aidList = autoids.map((a) => String(a).trim()).filter((a) => a);
    if (!aidList.length) return [[], "error: autoids list has no valid id (all elements empty)"];
    return [aidList, null];
  }
  const s = String(autoids).trim();
  if (!s) return [null, null];
  let parsed: any;
  if (s.startsWith("[")) {
    try {
      parsed = JSON.parse(s);
    } catch (e) {
      return [[], `error: autoids JSON parse failed: ${e}`];
    }
  } else {
    parsed = s.split(",").map((x) => x.trim()).filter((x) => x);
  }
  if (!Array.isArray(parsed)) return [[], "error: autoids must be a JSON array or a comma-separated id list"];
  const aidList = parsed.map((a) => String(a).trim()).filter((a) => a);
  if (!aidList.length) return [[], "error: autoids resolved to empty (pass a non-empty JSON array, a comma-separated string, or a native list)"];
  return [aidList, null];
}

export function merge_case_producer_rules(autoid: string, steps: any, opts: { init?: string; title?: string; reachability_scope?: any; expected_save_variant?: string; recorded_author_values?: Iterable<string> | null; recorded_author_ip_literals?: Iterable<string> | null } = {}): [any | null, string] {
  const { expand_distribution_steps } = require("../../../case_compiler/distribution_assertion");
  const { expand_membership_steps } = require("../../../case_compiler/membership_assertion");
  if (!Array.isArray(steps) || !steps.length) return [null, `(autoid=${autoid}) steps must be a non-empty list`];
  let filtered = steps.filter((s) => !(_isMapping(s) && ["APV_0", "test_env"].includes(String(s.E ?? "").trim()) && !String(s.G ?? "").trim()));
  if (!filtered.length) return [null, `(autoid=${autoid}) steps became empty after dropping empty command steps`];
  const [distSteps, _distPlan, distErr] = expand_distribution_steps(filtered);
  if (distErr) return [null, `(autoid=${autoid}) distribution-interval assertion declaration is invalid: ${distErr}`];
  filtered = distSteps;
  const [memberSteps, memberErr] = expand_membership_steps(filtered);
  if (memberErr) return [null, `(autoid=${autoid}) hit-membership assertion declaration is invalid: ${memberErr}`];
  filtered = memberSteps;
  const caseInit = String(opts.init ?? "").trim();
  let gate = _gate_unreachable_ips(autoid, filtered, { init: caseInit, recorded_author_values: opts.recorded_author_values ?? null });
  if (gate) return [null, gate];
  gate = _gate_unreachable_listener(autoid, filtered, { init: caseInit, reachability_scope: opts.reachability_scope ?? null, author_ip_literals: opts.recorded_author_ip_literals ?? null });
  if (gate) return [null, gate];
  gate = _gate_driver_reachability(autoid, filtered, { author_ip_literals: opts.recorded_author_ip_literals ?? null });
  if (gate) return [null, gate];
  gate = _gate_destructive_commands(autoid, filtered, { init: caseInit, stage: "merge_precheck" });
  if (gate) return [null, gate];
  gate = _gate_save_restore_pairing(autoid, filtered, { init: caseInit, expected_save_variant: _intent_save_variant(autoid) || String(opts.expected_save_variant ?? "") });
  if (gate) return [null, gate];
  let fullSteps = [...filtered];
  if (caseInit) {
    fullSteps = [{ E: "APV_0", F: "cmds_config", G: caseInit, desc: "case 自包含前置配置" }, ...fullSteps];
  }
  const [caseIr, info] = _stepsToCaseir(autoid, fullSteps, { title: String(opts.title ?? "") });
  if (caseIr === null) return [null, `(autoid=${autoid}): ${info}`];
  return [caseIr, ""];
}

export function precheck_merge_case(aid: string, out_name = ""): string | null {
  let xp: P;
  try {
    [aid, xp] = _safe_case_path(aid, "autoid");
    if (String(out_name ?? "").trim()) {
      _safe_output_component(out_name, "out_name");
    }
  } catch (exc) {
    return `unsafe output identity: ${exc instanceof Error ? exc.message : exc}`;
  }
  const _sh = require("../compile_engine/_shared");
  if (!xp.is_file()) return "case.xlsx 不在盘(编写未产出或已被挪走)";
  const ndPath = xp.parent.joinpath("needs_decision.json");
  const udPath = xp.parent.joinpath("user_decision.json");
  if (ndPath.is_file()) {
    let claims: any[];
    try {
      const nd = JSON.parse(fs.readFileSync(ndPath._p).toString("utf8"));
      claims = (nd.claims ?? []).filter((c: any) => _isMapping(c));
    } catch (exc) {
      return `未决冲突台账不可读，拒绝合并:${(exc as any)?.constructor?.name ?? "Error"}`;
    }
    if (claims.length) {
      const { xml_absence_veto_claims } = require("../compile_engine/terminal_credentials");
      if (xml_absence_veto_claims(claims)) return MERGE_XML_ABSENCE_REASON;
      const { decision_covers_claims } = require("./verifiability_tool");
      if (!(udPath.is_file() && decision_covers_claims(udPath, ndPath))) {
        return "存在未裁或裁决身份不匹配的盘上冲突，拒绝合并";
      }
      let ud: any;
      try {
        ud = JSON.parse(fs.readFileSync(udPath._p).toString("utf8"));
      } catch {
        return "裁决台账不可读，拒绝合并";
      }
      const decision = String(ud.decision ?? "");
      const action = String(ud.action ?? "");
      if (accepts_schema(ud.schema, "ist.delta.batch-conflict-decision")) {
        const { BATCH_USE_XML } = require("../compile_engine/conflict_chain");
        if (decision !== BATCH_USE_XML) return "批级来源冲突裁决要求停止编写或放弃整批，不得合并";
        if (Number(fs.statSync(xp._p).mtimeMs) * 1e6 <= Number(fs.statSync(udPath._p).mtimeMs) * 1e6) {
          return "批级裁决要求按 XML 重编，当前卷早于裁决";
        }
      } else if (["keep_case_and_block", "abandon_generation"].includes(action) || ["xml_keep_case_blocked", "abandon_generation"].includes(decision)) {
        return "用户裁决为停止编写或放弃本次生成，不得合并";
      } else if (action.startsWith("recompile_with_") && Number(fs.statSync(xp._p).mtimeMs) * 1e6 <= Number(fs.statSync(udPath._p).mtimeMs) * 1e6) {
        return "用户裁决要求重编，当前卷早于裁决";
      }
    }
  }
  const [casePayload, credentialSha256, credentialStatus] = _sh.lint_credential_snapshot(aid);
  if (credentialStatus === "credential_missing") return "缺 lint 凭证(未经 compile_emit 通过规则产出)";
  if (["credential_unreadable", "credential_contract_invalid"].includes(String(credentialStatus))) return "lint 凭证不可读或身份契约不匹配";
  if (credentialStatus !== "ok") return "lint 凭证过期或卷面身份不可安全核验(当前 case.xlsx 字节 SHA 与 emit 凭证不一致——须重新 compile_emit 通过规则)";
  const [scope, scopeError] = _reachability_scope_from_credential(aid, { xlsx_sha256: String(credentialSha256) });
  if (scope === null) return "lint 凭证的 blocks.kind/一致性绑定无效，须从密封机械用例重新 emit: " + scopeError;
  const { lint_xlsx_case } = require("./structural_gate");
  const lr = lint_xlsx_case(casePayload);
  if (lr.disabled && lr.disabled.length) _write_gate_disabled(aid, lr.disabled, { stage: "merge_precheck" });
  if (lr.advisories && lr.advisories.length) _write_gate_advisories(aid, lr.advisories, { stage: "merge_precheck" });
  if (!lr.ok) {
    _write_gate_rejections(aid, lr.violations, { stage: "merge_precheck" });
    return "成品卷 lint 违例:" + lr.violations.map((it: any) => `[${it.code}]`).join("; ").slice(0, 200);
  }
  let rowsForRules: any[];
  try {
    rowsForRules = require("./package_registry_tool")._load_case_rows(casePayload);
  } catch (exc) {
    throw new Error(`merged rule readback failed: ${exc}`);
  }
  const [caseIr, ruleReason] = merge_case_producer_rules(aid, rowsForRules, {
    init: "",
    reachability_scope: scope,
    recorded_author_values: _recorded_author_unreachable_values(aid, { xlsx_sha256: String(credentialSha256) }),
    recorded_author_ip_literals: _recorded_author_ip_literals(aid, { xlsx_sha256: String(credentialSha256) }),
  });
  if (caseIr === null) return `合卷卷面规则未通过:${ruleReason}`;
  const provenancePath = xp.parent.joinpath("case.provenance.json");
  let typedProvenance: Record<string, any> = {};
  try {
    typedProvenance = JSON.parse(fs.readFileSync(provenancePath._p).toString("utf8"));
  } catch {
    typedProvenance = {};
  }
  if (accepts_schema(typedProvenance.assertion_schema, "ist.ide.assertion")) {
    const mutationTesting = require("../../../case_compiler/mutation_testing");
    const mutation = mutationTesting.load_mutation_credential(aid, _sh.project_root().joinpath("runtime", "mutation_credentials"));
    const caseSha = crypto.createHash("sha256").update(casePayload).digest("hex");
    if (!mutationTesting.mutation_receipt_run_ready(mutation, caseSha)) {
      let receiptForDiag: Record<string, any> = {};
      if (_isMapping(mutation) && mutation.exempt_governance) {
        receiptForDiag = mutation;
      } else {
        try {
          const loaded = JSON.parse(fs.readFileSync(xp.parent.joinpath("case.mutation.json")._p).toString("utf8"));
          receiptForDiag = _isMapping(loaded) ? loaded : {};
        } catch {
          receiptForDiag = {};
        }
      }
      const governanceReason = mutationTesting.exempt_governance_failure_message(receiptForDiag);
      if (governanceReason) {
        const govItems = (receiptForDiag.requirements ?? []).filter((item: any) => _isMapping(item));
        const [govTotal, govExempt, , , govDiscretionary, govRatio] = mutationTesting._governance_counts(govItems);
        _signal_merge_precheck_refusal(aid, "merge_precheck_refusal_exempt_governance", mutationTesting._exempt_governance_check(receiptForDiag, { allow_compiler_issued_full_exempt: true }), {
          detail: {
            total_assertions: govTotal,
            exempt_assertions: govExempt,
            discretionary_exempt_assertions: govDiscretionary,
            author_declared_exempt_assertions: govItems.filter((item: any) => item.status === "exempt" && !mutationTesting._is_compiler_issued_exempt(item)).length,
            exempt_ratio: Math.round(Number(govRatio) * 1e6) / 1e6,
            max_exempt_ratio: mutationTesting.EXEMPT_MAX_RATIO,
          },
        });
        return governanceReason;
      }
      return "IDE 类型案缺少引擎侧变异凭据，或凭据未翻转/未绑定当前 case.xlsx";
    }
  }
  const factsMod = require("../compile_engine/facts");
  const fsFacts = _sh.load_facts({ out_name: out_name });
  if (factsMod.frozen(fsFacts, String(aid).trim())) {
    const ackPath = xp.parent.joinpath(".frozen_override_ack.json");
    let ackOk = false;
    if (ackPath.is_file()) {
      try {
        const ack = JSON.parse(fs.readFileSync(ackPath._p).toString("utf8"));
        ackOk = Math.abs(Number(ack.xlsx_mtime ?? -1) - fs.statSync(xp._p).mtimeMs / 1000) < 1e-6;
      } catch {
        ackOk = false;
      }
    }
    if (!ackOk) {
      return "同签名连续两轮 fail(引擎账本判定已冻结)但未见针对本次卷面的换法声明(override_frozen_reason)——须经 compile_emit 显式声明后重编";
    }
  }
  return null;
}

export function _replay_runtime_fills_before_emit(caseIrs: any[], sidecar: P): [string, Record<string, Array<[string, string, string]>>] {
  void caseIrs;
  const { _json_list } = require("../../../case_compiler/runtime_fill");
  const records = _json_list(sidecar._p, { label: "legacy runtime_fills sidecar" });
  if (records && records.length) {
    throw new PyValueError("observe_then_assert_forbidden: legacy runtime_fills actuals cannot be replayed into expected; resolve via Author|Spec|DefectSpec|Manual|ConfigBinding|CapabilityXml");
  }
  return ["", {}];
}

export function compile_emit_merged(opts: { cases_json?: string; shared_init?: string; out_name?: string; autoids?: string | string[] } = {}): string {
  const casesJson = String(opts.cases_json ?? "");
  const sharedInit = String(opts.shared_init ?? "");
  let outName = String(opts.out_name ?? "");
  const autoidsArg = opts.autoids ?? "";
  const _sh = require("../compile_engine/_shared");
  try {
    if (outName.trim()) _safe_output_component(outName, "out_name");
  } catch (exc) {
    return `error: unsafe output identity: ${exc instanceof Error ? exc.message : exc}`;
  }
  const [aidList, autoidsErr] = _parseAutoidsArg(autoidsArg);
  if (autoidsErr) return autoidsErr;
  const caseCredentialSha256: Record<string, string> = {};
  let cases: Array<Record<string, any>>;
  if (aidList !== null) {
    const { _load_case_rows } = require("./package_registry_tool");
    cases = [];
    const caseSnapshots: Record<string, Buffer> = {};
    const caseReachabilityScopes: Record<string, ReachabilityScope> = {};
    const noGrade: string[] = [];
    const staleGrade: string[] = [];
    const scopeBad: string[] = [];
    for (const rawAid of aidList) {
      let aid: string;
      let xp: P;
      try {
        [aid, xp] = _safe_case_path(String(rawAid), "autoid");
      } catch (exc) {
        return `error: unsafe output identity: ${exc instanceof Error ? exc.message : exc}`;
      }
      if (!xp.is_file()) {
        return `error: case.xlsx for autoid ${aid} does not exist (${xp}); the case may not have compiled successfully — compile it first / re-dispatch the worker`;
      }
      const [casePayload, credentialSha256, credentialStatus] = _sh.lint_credential_snapshot(aid);
      if (credentialStatus === "credential_missing") {
        noGrade.push(aid);
        continue;
      }
      if (credentialStatus !== "ok") {
        staleGrade.push(aid);
        continue;
      }
      const [scope, scopeError] = _reachability_scope_from_credential(aid, { xlsx_sha256: String(credentialSha256) });
      if (scope === null) {
        scopeBad.push(`${aid}: ${scopeError}`);
        continue;
      }
      caseSnapshots[aid] = Buffer.isBuffer(casePayload) ? casePayload : Buffer.from(casePayload as any);
      caseReachabilityScopes[aid] = scope;
      caseCredentialSha256[aid] = String(credentialSha256);
    }
    if (noGrade.length || staleGrade.length || scopeBad.length) {
      const parts: string[] = [];
      if (noGrade.length) parts.push(`missing lint credential (did not go through gated compile_emit): ${noGrade.join(", ")}`);
      if (staleGrade.length) parts.push(`re-compiled but not re-emitted (the credential does not match the current case.xlsx): ${staleGrade.join(", ")}`);
      if (scopeBad.length) parts.push("missing/stale blocks.kind reachability scope (re-emit from the sealed mechanical case; merge will not guess kind from xlsx text): " + scopeBad.join("; "));
      return "error: merge rejected by the lint-credential rule — the following cases have not passed all of emit's mechanical rules on their current case.xlsx:\n" + parts.join("\n") + "\nRun compile_emit again for each listed case (passing all mechanical rules auto-lands the lint credential), then merge.";
    }
    const { lint_xlsx_case } = require("./structural_gate");
    const lintBad: string[] = [];
    for (const [aid, snapshotPayload] of Object.entries(caseSnapshots)) {
      let rows: any[];
      try {
        rows = _load_case_rows(snapshotPayload);
      } catch (e) {
        return `error: failed to read back case.xlsx for ${aid}: ${e}`;
      }
      const lr = lint_xlsx_case(snapshotPayload);
      if (!rows || !rows.length) return `error: ${aid} read back empty steps (case.xlsx data area empty?)`;
      cases.push({ autoid: aid, steps: rows, _reachability_scope: caseReachabilityScopes[aid] });
      if (lr.disabled && lr.disabled.length) _write_gate_disabled(aid, lr.disabled, { stage: "merge_final" });
      if (!lr.ok) {
        _write_gate_rejections(aid, lr.violations, { stage: "merge_final" });
        lintBad.push(`${aid}: ` + lr.violations.map((it: any) => `[${it.code}]`).join("; "));
      }
    }
    if (lintBad.length) {
      return "error: merge rejected by finished-sheet lint — the following cases carry mechanically decidable must-crash/always-fail shapes (one must-crash case crashes the whole pytest file and none of the rest run):\n  " + lintBad.join("\n  ") + "\nFix them, run compile_emit again, then merge (violation details are in the corresponding emit returns).";
    }
  } else {
    try {
      cases = JSON.parse(casesJson);
      if (!Array.isArray(cases) || !cases.length) {
        return "error: pass autoids (preferred; the tool reads the sheets back itself) or a non-empty cases_json";
      }
    } catch (e) {
      return `error: cases_json parse failed: ${e}`;
    }
  }
  let FileIR: any;
  let Row: any;
  let emitXlsxMerged: any;
  try {
    ({ FileIR, Row } = require("../../../case_compiler/case_ir"));
    ({ emit_xlsx: emitXlsxMerged } = require("../../../case_compiler/xlsx_emit"));
    require("../../../case_compiler/config");
    require("../../../case_compiler/distribution_assertion");
    require("../../../case_compiler/membership_assertion");
  } catch (e) {
    return `error: failed to load compiler modules: ${e}`;
  }
  const caseIrs: any[] = [];
  const seenAutoids = new Set<string>();
  for (const [idx, c] of cases.entries()) {
    if (!_isMapping(c)) return `error: cases[${idx}] is not a dict`;
    let autoid: string;
    try {
      autoid = _safe_output_component(String(c.autoid ?? ""), `cases[${idx}].autoid`);
    } catch (exc) {
      return `error: unsafe output identity: ${exc instanceof Error ? exc.message : exc}`;
    }
    if (seenAutoids.has(autoid)) {
      return `error: autoid ${autoid} is duplicated (autoid is the primary key and must be unique; titles may repeat)`;
    }
    seenAutoids.add(autoid);
    const [caseIr, reason] = merge_case_producer_rules(autoid, c.steps, {
      init: String(c.init ?? "").trim(),
      title: String(c.title ?? ""),
      reachability_scope: c._reachability_scope,
      expected_save_variant: String(c.expected_save_variant ?? ""),
      recorded_author_values: _recorded_author_unreachable_values(autoid, { xlsx_sha256: caseCredentialSha256[autoid] ?? "" }),
      recorded_author_ip_literals: _recorded_author_ip_literals(autoid, { xlsx_sha256: caseCredentialSha256[autoid] ?? "" }),
    });
    if (caseIr === null) return `error: cases[${idx}] ${reason}`;
    caseIrs.push(caseIr);
  }
  const shared = sharedInit.trim();
  const initRows = shared ? [new Row({ test_object: "APV_0", method: "cmds_config", data: shared })] : [];
  let sub: string;
  let out: P;
  try {
    [sub, out] = _safe_case_path(outName || caseIrs[0].autoid, "out_name");
  } catch (exc) {
    return `error: unsafe output identity: ${exc instanceof Error ? exc.message : exc}`;
  }
  let replayNote = "";
  try {
    [replayNote] = _replay_runtime_fills_before_emit(caseIrs, out.parent.joinpath("runtime_fills.json"));
  } catch (exc) {
    return `error: runtime_fills replay failed: ${exc}`;
  }
  const fir = new FileIR({ feature: sub, author: "IST-Core-agent", init_rows: initRows, cases: [...caseIrs, _buildSentinel()], module: "ist_smoke" });
  let stats: any;
  try {
    stats = emitXlsxMerged(fir, out._p, { trusted_outputs_root: _sh.outputs_root() });
  } catch (e) {
    return `error: emit failed: ${e}`;
  }
  const outAutoids = caseIrs.map((c: any) => c.autoid);
  return `=== compile_emit_merged ===\n已合并 ${caseIrs.length} 个真 case + 1 哨兵 → ${out}\nautoids: ${JSON.stringify(outAutoids)}\nround-trip stats: ${stats}${replayNote}\n(case_count expected=${caseIrs.length}+1 sentinel=${caseIrs.length + 1})\nIndependent whole-volume verification must test this exact artifact SHA before delivery.`;
}
