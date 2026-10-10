// 生成：tools/extract_engine.py ← InfoTest main/case_compiler/blocks.py（sha256 fd9c31d8c99845f7）。不在这里手改。
import crypto from "node:crypto";
import { _cex_set_caller } from "../_root";
import { IInjectionSyntaxError, parse_found_times_cells, validate_i_injection_syntax } from "./case_ir";
import { distribution_count_binding_error } from "./distribution_assertion";

_cex_set_caller("cex_core.engine.case_compiler.blocks");

export const _ASSERT_OPS = ["found", "not_found", "abs_found"] as const;
export const _EXIT_STATUS_EXPECTS = ["success", "failure"] as const;
const _ANSWERER_KINDS = ["device", "fixture", "bed_service", "undetermined"] as const;
const _ANSWERER_FIELD_KEYS = new Set(["kind", "ref", "note"]);
const _EXIT_STATUS_MASKING_REFUSAL =
  "OBSERVE_EXIT.cmd must leave the observed command's status unmasked; pipes, ';', '||', background execution, newlines, and command substitution are rejected (use a direct command, or '&&' only when every command must succeed)";
const _REGISTER_NAME_RE = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
const _AUTO_REGISTER_RE = /^v\d+$/;
export const _REF_KINDS = [
  "footprint", "manual", "precedent", "env_facts", "intent", "config_derived", "skeleton",
  "test_env_dispatch", "device_runtime", "distribution_derived", "membership_derived", "captured_relation",
] as const;
const _REF_LOCATOR_REQUIRED = new Set(["footprint", "manual", "precedent", "env_facts", "intent", "skeleton"]);

export function _parse_ref(ref: any): Record<string, string> {
  const s = String(ref ?? "").trim();
  if (!s) {
    return { kind: "emit_auto", ref: "" };
  }
  const idx = s.indexOf(":");
  const head = idx === -1 ? s : s.slice(0, idx);
  const tail = idx === -1 ? "" : s.slice(idx + 1);
  if ((_REF_KINDS as readonly string[]).includes(head)) {
    return { kind: head, ref: tail.trim() };
  }
  return { kind: "emit_auto", ref: s };
}

export function _dispatch_source(e: string, f: string, g: string, ref: any = null): Record<string, string> {
  let sourceText = String(ref ?? "").trim();
  let parsed = _parse_ref(ref);
  if (parsed.kind === "test_env_dispatch" && parsed.ref === "") {
    parsed = { kind: "emit_auto", ref: "" };
    sourceText = "";
  }
  if (parsed.kind !== "emit_auto") {
    return parsed;
  }
  if (sourceText) {
    return parsed;
  }
  if (String(e || "").trim() !== "test_env") {
    return parsed;
  }
  const dispatchMethod = String(f || "").trim().toLowerCase();
  try {
    const { ExcelContractError, contract_entry, load_excel_contract } = require("./excel_contract");
    const contract = load_excel_contract();
    const entry = contract_entry("test_env", dispatchMethod, contract);
    if (entry === null || entry.status !== "enabled") {
      return parsed;
    }
  } catch (exc: any) {
    if (exc && exc.name === "ExcelContractError") {
      return parsed;
    }
    throw exc;
  }
  return { kind: "test_env_dispatch", ref: `lib/env.py#Env.${dispatchMethod}` };
}

function _err(i: number, kind: string, msg: string): string {
  return `blocks[${i}](${kind}): ${msg}`;
}

const _DUT_HOSTS = ["APV_0", "APV_1"];
const _CONFIG_STEP_FUNCTIONS = new Set(["cmd_config", "cmds_config"]);

export function _observe_step(host: string, cmd: string, desc: string, saveAs = ""): Record<string, any> {
  const h = (host || "").trim();
  let st: Record<string, any>;
  if (_DUT_HOSTS.includes(h)) {
    st = { E: h, F: "cmd_config", G: cmd, desc };
  } else {
    st = { E: "test_env", F: h.toLowerCase(), G: cmd, desc };
  }
  if (saveAs) {
    st.H = saveAs;
  }
  return st;
}

function _answerer_shape_error(i: number, kind: string, b: Record<string, any>): string | null {
  const answerer = b.answerer;
  if (answerer === null || answerer === undefined) {
    return null;
  }
  if (typeof answerer !== "object" || Array.isArray(answerer)) {
    return _err(i, kind, "answerer must be an object {kind, ref|note} naming who answers this observation");
  }
  const extra = Object.keys(answerer).filter((k) => !_ANSWERER_FIELD_KEYS.has(k)).sort();
  if (extra.length) {
    return _err(i, kind, `answerer has unsupported field(s): ${extra.join(", ")} (closed set: kind, ref, note)`);
  }
  const aKind = String(answerer.kind || "").trim();
  if (!(_ANSWERER_KINDS as readonly string[]).includes(aKind)) {
    return _err(i, kind, `answerer.kind must be one of ${_ANSWERER_KINDS.join(", ")}; got ${JSON.stringify(aKind)}`);
  }
  if (aKind === "device" || aKind === "fixture") {
    const ref = answerer.ref;
    if (typeof ref !== "number" || !Number.isInteger(ref) || ref < 0) {
      return _err(i, kind, `answerer.ref for kind=${aKind} must be a blocks[] index (non-negative integer) of the block that establishes the answerer`);
    }
  } else if (aKind === "bed_service") {
    const ref = answerer.ref;
    if (typeof ref !== "string" || !ref.trim()) {
      return _err(i, kind, "answerer.ref for kind=bed_service must be a device name from the bed topology (non-empty text)");
    }
  } else {
    const note = answerer.note;
    if (typeof note !== "string" || !note.trim()) {
      return _err(i, kind, "answerer.note for kind=undetermined must be one line naming what no source states about who answers");
    }
  }
  return null;
}

const _STEP_FIELDS = new Set([
  "kind", "E", "F", "G", "H", "I", "desc", "ref", "assertion_type", "exempt", "reason_code",
  "observation_id", "result_channel", "observation_ref", "binding_input", "timeout_s",
  "expectation_id", "semantic_key",
]);
export const _ASSERTION_ID_FIELDS = ["expectation_id", "semantic_key"] as const;
export const COMMAND_TIMEOUT_MIN_S = 1;
export const COMMAND_TIMEOUT_MAX_S = 600;

export function _command_timeout_error(i: number, kind: string, b: Record<string, any>): string | null {
  if (!("timeout_s" in b)) {
    return null;
  }
  const value = b.timeout_s;
  if (typeof value !== "number" || !Number.isInteger(value)) {
    return _err(i, kind, "timeout_s must be an integer; booleans are not accepted");
  }
  if (value < COMMAND_TIMEOUT_MIN_S || value > COMMAND_TIMEOUT_MAX_S) {
    return _err(i, kind, `timeout_s must be between ${COMMAND_TIMEOUT_MIN_S} and ${COMMAND_TIMEOUT_MAX_S} seconds`);
  }
  return null;
}

export function _timeout_command_error(i: number, kind: string, command: string): string | null {
  const { ExcelContractError, parse_g_arguments } = require("./excel_contract");
  let args: any[];
  let kwargs: Record<string, any>;
  try {
    [args, kwargs] = parse_g_arguments(command, "cmd_config");
  } catch (exc: any) {
    if (exc instanceof ExcelContractError) {
      return _err(i, kind, "timeout_s requires a valid single-command G argument list");
    }
    throw exc;
  }
  if (args.length !== 1) {
    return _err(i, kind, "timeout_s requires exactly one product command per entry");
  }
  if ("timeout" in kwargs) {
    return _err(i, kind, "timeout_s conflicts with an existing timeout= argument; supply only one");
  }
  return null;
}

export const SSL_CERT_LOAD_KIND = "SSL_CERT_LOAD";
const _NO_ASSERTION_ID_KINDS = new Set(["CONFIG", "OBSERVE_ONLY", "CAPTURE", "SLEEP", "OBSERVE_ASSERT", "SSL_CERT_LOAD"]);
const _ASSERTION_ID_BLOCK_KINDS = new Set(["CAPTURE_COMPARE", "OBSERVE_DIST", "OBSERVE_MEMBER", "EXPECT_FROM", "OBSERVE_EXIT"]);

export function _exit_status_command(command: string): string {
  return `( ${command} ); ist_case_exit_code=$?; echo; printf 'IST_EXIT_STATUS=%s' "$ist_case_exit_code"; echo`;
}

export function _probe_tool_name(command: string): string {
  let tokens: string[];
  try {
    tokens = shlexSplit(command);
  } catch {
    return "";
  }
  let index = 0;
  while (index < tokens.length) {
    const token = tokens[index];
    if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(token) || token === "sudo" || token === "env") {
      index += 1;
      continue;
    }
    if (token === "timeout") {
      index += 1;
      if (index < tokens.length && /^\d+(?:\.\d+)?[smhd]?$/.test(tokens[index])) {
        index += 1;
      }
      continue;
    }
    return token.split("/").pop()!.toLowerCase();
  }
  return "";
}

function shlexSplit(command: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let inSingle = false;
  let inDouble = false;
  let escaped = false;
  for (const ch of command) {
    if (escaped) {
      current += ch;
      escaped = false;
      continue;
    }
    if (ch === "\\" && !inSingle) {
      escaped = true;
      continue;
    }
    if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
      continue;
    }
    if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
      continue;
    }
    if (/\s/.test(ch) && !inSingle && !inDouble) {
      if (current) {
        tokens.push(current);
        current = "";
      }
      continue;
    }
    current += ch;
  }
  if (escaped) {
    throw new Error("No escaped character");
  }
  if (inSingle || inDouble) {
    throw new Error("No closing quotation");
  }
  if (current) {
    tokens.push(current);
  }
  return tokens;
}

function shlexPunctuationTokens(command: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let inSingle = false;
  let inDouble = false;
  let escaped = false;
  const punct = new Set(["(", ")", ";", "<", ">", "|", "&"]);
  const flush = () => {
    if (current) {
      tokens.push(current);
      current = "";
    }
  };
  for (const ch of command) {
    if (escaped) {
      current += ch;
      escaped = false;
      continue;
    }
    if (ch === "\\" && !inSingle) {
      escaped = true;
      continue;
    }
    if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
      continue;
    }
    if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
      continue;
    }
    if (inSingle || inDouble) {
      current += ch;
      continue;
    }
    if (/\s/.test(ch)) {
      flush();
      continue;
    }
    if (punct.has(ch)) {
      flush();
      tokens.push(ch);
      continue;
    }
    current += ch;
  }
  if (escaped) {
    throw new Error("No escaped character");
  }
  if (inSingle || inDouble) {
    throw new Error("No closing quotation");
  }
  flush();
  // coalesce runs of punctuation chars into single tokens like shlex does
  const merged: string[] = [];
  for (const tok of tokens) {
    if (
      merged.length &&
      [...tok].every((c) => punct.has(c)) &&
      [...merged[merged.length - 1]].every((c) => punct.has(c))
    ) {
      merged[merged.length - 1] += tok;
    } else {
      merged.push(tok);
    }
  }
  return merged;
}

export function _exit_status_masking_error(command: string): string {
  if (command.includes("\n") || command.includes("\r")) {
    return _EXIT_STATUS_MASKING_REFUSAL;
  }
  if (command.includes("`") || command.includes("$(")) {
    return _EXIT_STATUS_MASKING_REFUSAL;
  }
  let tokens: string[];
  try {
    tokens = shlexPunctuationTokens(command);
  } catch {
    return _EXIT_STATUS_MASKING_REFUSAL;
  }
  const punctuation = new Set(["(", ")", ";", "<", ">", "|", "&"]);
  for (const token of tokens) {
    if (!token || ![...token].every((c) => punctuation.has(c))) {
      continue;
    }
    if (token.includes("|") || token.includes(";")) {
      return _EXIT_STATUS_MASKING_REFUSAL;
    }
    if (token.includes("&") && token !== "&&" && !token.includes("<") && !token.includes(">")) {
      return _EXIT_STATUS_MASKING_REFUSAL;
    }
  }
  return "";
}

export function _assertion_identity(container: Record<string, any>): [Record<string, string>, string] {
  const out: Record<string, string> = {};
  for (const name of _ASSERTION_ID_FIELDS) {
    if (!(name in container)) {
      continue;
    }
    const value = container[name];
    if (typeof value !== "string" || !value.trim()) {
      return [{}, `${name}, when present, must be the non-empty identifier minted by the typed expectation contract (copy it verbatim)`];
    }
    out[name] = value.trim();
  }
  return [out, ""];
}

export function _reject_block_level_assertion_ids(i: number, kind: string, b: Record<string, any>): string | null {
  const present = _ASSERTION_ID_FIELDS.filter((name) => name in b);
  if (!present.length) {
    return null;
  }
  const hint = kind === "OBSERVE_ASSERT"
    ? " — declare them on each asserts[] entry instead"
    : " — this combinator produces no check_point to bind them to";
  return _err(i, kind, `unsupported field(s): ${present.join(", ")}${hint}`);
}

function _collect_nested_assertion_ids(value: any, path: string, out: string[]): void {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, sub] of Object.entries(value)) {
      const child = path ? `${path}.${key}` : String(key);
      if ((_ASSERTION_ID_FIELDS as readonly string[]).includes(key)) {
        out.push(child);
        continue;
      }
      _collect_nested_assertion_ids(sub, child, out);
    }
  } else if (Array.isArray(value)) {
    value.forEach((sub, index) => {
      _collect_nested_assertion_ids(sub, `${path}[${index}]`, out);
    });
  }
}

export function _nested_assertion_id_error(i: number, kind: string, b: Record<string, any>): string | null {
  const found: string[] = [];
  for (const [key, value] of Object.entries(b)) {
    if ((_ASSERTION_ID_FIELDS as readonly string[]).includes(key)) {
      continue;
    }
    if (kind === "OBSERVE_ASSERT" && key === "asserts" && Array.isArray(value)) {
      value.forEach((item, j) => {
        if (typeof item !== "object" || item === null) {
          return;
        }
        for (const [subKey, subValue] of Object.entries(item)) {
          if ((_ASSERTION_ID_FIELDS as readonly string[]).includes(subKey)) {
            continue;
          }
          _collect_nested_assertion_ids(subValue, `asserts[${j}].${subKey}`, found);
        }
      });
      continue;
    }
    _collect_nested_assertion_ids(value, String(key), found);
  }
  if (!found.length) {
    return null;
  }
  return _err(i, kind, `unsupported field(s): ${found.join(", ")} — assertion identity is only read at the assertion-bearing position (the combinator itself, or each OBSERVE_ASSERT asserts[] entry); nested containers are never consulted, so an id written there is silently dropped`);
}

export function _reject_explicit_provenance_assertion_ids(i: number, kind: string, pv: any): string | null {
  if (typeof pv !== "object" || pv === null || Array.isArray(pv)) {
    return null;
  }
  const present = _ASSERTION_ID_FIELDS.filter((name) => name in pv);
  if (!present.length) {
    return null;
  }
  return `provenance_steps[${i}] (for blocks[${i}](${kind})): unsupported field(s): ${present.join(", ")} — the explicit provenance channel carries one entry per combinator, so one id there would be copied onto every row this combinator expands to (including non-assertion rows, and every one of N assertions). Declare the pair on the assertion itself: each OBSERVE_ASSERT asserts[] entry, the combinator that synthesizes exactly one assertion, or an E=check_point STEP.`;
}

function _assertion_slot_label(kind: string, blockIndex: number, offset: number): string {
  if (kind === "OBSERVE_ASSERT") {
    return `blocks[${blockIndex}].asserts[${offset - 1}]`;
  }
  return `blocks[${blockIndex}]`;
}

export function _assertion_identity_coverage_error(provOut: Record<string, any>[], slots: [string, number][]): string | null {
  if (!slots.length) {
    return null;
  }
  let touched = 0;
  const missing: [string, string[]][] = [];
  for (const [label, index] of slots) {
    const entry = index < provOut.length ? provOut[index] : {};
    const absent = _ASSERTION_ID_FIELDS.filter((name) => !entry[name]);
    if (absent.length < _ASSERTION_ID_FIELDS.length) {
      touched += 1;
    }
    if (absent.length) {
      missing.push([label, absent]);
    }
  }
  if (!touched || !missing.length) {
    return null;
  }
  const carried = slots.length - missing.length;
  const detail = missing.map(([label, names]) => `${label} lacks ${names.join(", ")}`).join("; ");
  return `assertion identity coverage is partial: ${carried} of ${slots.length} check_point assertions carry both ${_ASSERTION_ID_FIELDS[0]} and ${_ASSERTION_ID_FIELDS[1]}, but ${detail}. The emit identity gate requires every final assertion to carry a contract identity, so within one case either all assertions carry the pair minted by the typed expectation contract, or none may.`;
}

export function _derived_binding_source(opts: {
  sourceKind: string;
  recipeId: string;
  ruleId: string;
  sourceInput: Record<string, any>;
  outputStep: Record<string, any>;
  outputOrdinal?: number;
}): [Record<string, any> | null, string] {
  const { build_config_binding_derivation_receipt } = require("./provenance_ir");
  const [receipt, error] = build_config_binding_derivation_receipt({
    sourceKind: opts.sourceKind,
    recipeId: opts.recipeId,
    ruleId: opts.ruleId,
    sourceInput: opts.sourceInput,
    outputStep: opts.outputStep,
    outputOrdinal: opts.outputOrdinal ?? 0,
  });
  if (receipt === null) {
    return [null, error];
  }
  return [{ kind: opts.sourceKind, ref: receipt.recipe_id, receipt }, ""];
}

function _expand_generic_step(
  i: number,
  b: Record<string, any>,
  definedRegisters: Set<string>,
  captureRegisters: Set<string> | null = null
): [Record<string, any> | null, Record<string, any> | null, string | null] {
  const extra = Object.keys(b).filter((k) => !_STEP_FIELDS.has(k)).sort();
  if (extra.length) {
    const clientHint = extra.some((field) => ["host", "cmd", "asserts"].includes(field))
      ? " STEP has no host/cmd/asserts fields: a client command with an assertion belongs in OBSERVE_ASSERT {host, cmd, asserts}, which derives test_env dispatch provenance mechanically."
      : "";
    return [null, null, _err(i, "STEP", `unsupported field(s): ${extra.join(", ")}.${clientHint}`)];
  }
  const eRaw = b.E;
  const fRaw = b.F;
  const gRaw = b.G;
  if (typeof eRaw !== "string" || !eRaw.trim()) {
    return [null, null, _err(i, "STEP", "E must be a non-empty framework object name")];
  }
  if (typeof fRaw !== "string" || !fRaw.trim()) {
    return [null, null, _err(i, "STEP", "F must be a non-empty framework method name")];
  }
  if (typeof gRaw !== "string") {
    return [null, null, _err(i, "STEP", "G must be a string (empty text is allowed where the method arity is zero)")];
  }
  const e = eRaw.trim();
  const f = fRaw.trim();
  let g = gRaw;
  const timeoutError = _command_timeout_error(i, "STEP", b);
  if (timeoutError) {
    return [null, null, timeoutError];
  }
  if ("timeout_s" in b) {
    if (!e.startsWith("APV") || f !== "cmd_config") {
      return [null, null, _err(i, "STEP", "timeout_s on STEP requires E=APV* and F=cmd_config")];
    }
    const timeoutCmdError = _timeout_command_error(i, "STEP", g);
    if (timeoutCmdError) {
      return [null, null, timeoutCmdError];
    }
    g = `${g},timeout=${b.timeout_s}`;
  }
  const ref = String(b.ref || "").trim();
  const { ExcelContractError, contract_entry, load_excel_contract, validate_g_for_entry } = require("./excel_contract");
  let contract: any;
  try {
    contract = load_excel_contract();
  } catch (exc: any) {
    if (exc instanceof ExcelContractError) {
      return [null, null, _err(i, "STEP", `Excel function contract is unavailable: ${exc}`)];
    }
    throw exc;
  }
  const fCmp = e === "test_env" ? f.toLowerCase() : f;
  const entry = contract_entry(e, fCmp, contract);
  if (entry === null) {
    const clientHint = e === "test_env" || f === "test_env"
      ? " For an environment/client observation, use OBSERVE_ASSERT with the exact environment host in `host`, the command in `cmd`, and signed checks in `asserts`; do not encode the execution object itself as F."
      : "";
    return [null, null, _err(i, "STEP", `E=${JSON.stringify(e)}, F=${JSON.stringify(f)} is not a valid method: the pair is absent from the Excel function contract.${clientHint}`)];
  }
  if (entry.status !== "enabled") {
    return [null, null, _err(i, "STEP", `E=${JSON.stringify(e)}, F=${JSON.stringify(f)} is ${entry.status}: ${entry.reason}`)];
  }
  try {
    validate_g_for_entry(entry, g, contract);
  } catch (exc: any) {
    if (exc instanceof ExcelContractError) {
      return [null, null, _err(i, "STEP", `invalid G syntax for E=${JSON.stringify(e)}, F=${JSON.stringify(f)}: ${exc}`)];
    }
    throw exc;
  }
  let parsedRef = _dispatch_source(e, fCmp, g, ref);
  if (parsedRef.kind === "emit_auto") {
    return [null, null, _err(i, "STEP", `ref is required and must be a recognized provenance pointer (one of ${_REF_KINDS.join(", ")}, written as kind:location); only a validated test_env dispatch derives its source mechanically. If this step is a client observation with an assertion, replace the raw STEP pair with one OBSERVE_ASSERT block instead of inventing a provenance locator`)];
  }
  if (_REF_LOCATOR_REQUIRED.has(parsedRef.kind) && !String(parsedRef.ref || "").trim()) {
    return [null, null, _err(i, "STEP", `ref kind ${JSON.stringify(parsedRef.kind)} requires a non-empty source locator`)];
  }
  if (e === "time") {
    let seconds: number;
    try {
      seconds = parseInt(g, 10);
      if (Number.isNaN(seconds)) throw new Error("nan");
    } catch {
      return [null, null, _err(i, "STEP", "time.sleep G must be an integer number of seconds")];
    }
    if (seconds <= 0 || seconds > 300) {
      return [null, null, _err(i, "STEP", `time.sleep G must be within 1..300; got ${seconds}`)];
    }
  }
  const h = String(b.H || "").trim();
  const iCol = String(b.I || "").trim();
  const identifierFields: [string, string][] = [["H", h]];
  if (!(e === "check_point" && f === "found_times")) {
    identifierFields.push(["I", iCol ? iCol.split(".")[0] : ""]);
  }
  for (const [fieldName, value] of identifierFields) {
    if (value && !_REGISTER_NAME_RE.test(value)) {
      return [null, null, _err(i, "STEP", `${fieldName} register reference ${JSON.stringify(value)} is not a safe identifier`)];
    }
  }
  if (e === "check_point") {
    let checkRefs: string[];
    if (f === "found_times") {
      try {
        parse_found_times_cells(g, h, iCol);
      } catch (exc: any) {
        return [null, null, _err(i, "STEP", String(exc.message || exc))];
      }
      checkRefs = [];
    } else {
      checkRefs = [h, iCol];
    }
    for (const refName of checkRefs) {
      if (refName && !definedRegisters.has(refName.split(".")[0])) {
        return [null, null, _err(i, "STEP", `${JSON.stringify(refName)} must be captured by an earlier STEP before check_point use`)];
      }
    }
  } else {
    if (iCol) {
      const base = iCol.split(".")[0];
      const objectNames = new Set((contract.objects || []).map((item: any) => String(item.e)));
      if (!definedRegisters.has(base) && !objectNames.has(base)) {
        return [null, null, _err(i, "STEP", `I=${JSON.stringify(iCol)} must reference an earlier STEP capture or framework object`)];
      }
    }
    try {
      validate_i_injection_syntax(g, iCol, fCmp);
    } catch (exc: any) {
      if (exc instanceof ExcelContractError || exc instanceof IInjectionSyntaxError) {
        return [null, null, _err(i, "STEP", String(exc.message || exc))];
      }
      throw exc;
    }
    if (h) {
      if (captureRegisters && captureRegisters.has(h)) {
        return [null, null, _err(i, "STEP", `H=${JSON.stringify(h)} names a register already captured by an earlier CAPTURE combinator — a raw STEP writing there overwrites that baseline while later EXPECT_FROM still reads it. Pick a different H, or drop the CAPTURE if this step is the capture you meant.`)];
      }
      definedRegisters.add(h);
    }
  }
  const step: Record<string, any> = { E: e, F: fCmp, G: g, desc: String(b.desc || "") };
  const exempt = b.exempt;
  const reasonCode = String(b.reason_code || "").trim();
  if (e !== "check_point" && (exempt !== null && exempt !== undefined || reasonCode)) {
    return [null, null, _err(i, "STEP", "exempt/reason_code are valid only on check_point steps")];
  }
  if (e !== "check_point") {
    const idError = _reject_block_level_assertion_ids(i, "STEP", b);
    if (idError) {
      return [null, null, idError];
    }
  }
  const [assertionIds, idError] = _assertion_identity(b);
  if (idError) {
    return [null, null, _err(i, "STEP", idError)];
  }
  if (e === "check_point") {
    if (exempt !== null && exempt !== undefined && exempt !== false && exempt !== true) {
      return [null, null, _err(i, "STEP", "exempt must be a boolean when present")];
    }
    if (exempt !== true && reasonCode) {
      return [null, null, _err(i, "STEP", "reason_code is valid only when exempt=true")];
    }
    if (exempt === true) {
      step.exempt = true;
      step.reason_code = reasonCode;
    }
  }
  if (h) {
    step.H = h;
  }
  if (iCol) {
    step.I = iCol;
  }
  const layer = e === "check_point" ? "V" : e === "time" ? "E" : "G";
  if (parsedRef.kind === "config_derived") {
    const bindingInput = b.binding_input;
    if (typeof bindingInput !== "object" || bindingInput === null || Array.isArray(bindingInput)) {
      return [null, null, _err(i, "STEP", "config_derived requires binding_input with an independently recomputable rule_id and source_input")];
    }
    const keys = Object.keys(bindingInput).sort();
    if (keys.length !== 2 || keys[0] !== "rule_id" || keys[1] !== "source_input") {
      return [null, null, _err(i, "STEP", "binding_input requires exactly rule_id/source_input")];
    }
    const sourceInput = bindingInput.source_input;
    if (typeof sourceInput !== "object" || sourceInput === null || Array.isArray(sourceInput)) {
      return [null, null, _err(i, "STEP", "binding_input.source_input must be an object")];
    }
    const [newRef, bindingError] = _derived_binding_source({
      sourceKind: "config_derived",
      recipeId: String(parsedRef.ref || ""),
      ruleId: String(bindingInput.rule_id || ""),
      sourceInput,
      outputStep: step,
    });
    if (newRef === null) {
      return [null, null, _err(i, "STEP", bindingError)];
    }
    parsedRef = newRef;
  }
  const stepProvenance: Record<string, any> = { layer, source: parsedRef };
  if (e === "check_point" && typeof b.assertion_type === "object" && b.assertion_type !== null) {
    stepProvenance.assertion_type = JSON.parse(JSON.stringify(b.assertion_type));
  }
  if (e === "check_point") {
    Object.assign(stepProvenance, assertionIds);
  }
  return [step, stepProvenance, null];
}

function _validate_expanded_contract_steps(steps: Record<string, any>[]): string | null {
  const { ExcelContractError, contract_entry, enabled_fs_by_e, load_excel_contract, validate_g_for_entry } = require("./excel_contract");
  let contract: any;
  try {
    contract = load_excel_contract();
  } catch (exc: any) {
    if (exc instanceof ExcelContractError) {
      return `Excel function contract is unavailable: ${exc}`;
    }
    throw exc;
  }
  const enabledByE = enabled_fs_by_e(contract);
  for (let index = 0; index < steps.length; index++) {
    const step = steps[index];
    const e = String(step.E || "").trim();
    const f = String(step.F || "").trim();
    if (f === "dist" || f === "member") {
      continue;
    }
    const fCmp = e === "test_env" ? f.toLowerCase() : f;
    const entry = contract_entry(e, fCmp, contract);
    if (entry === null) {
      const enabled = Object.keys(enabledByE[e] || {}).sort();
      const choices = enabled.map((v) => JSON.stringify(v)).join(", ") || "(none)";
      return `expanded step[${index}] E=${JSON.stringify(e)}, F=${JSON.stringify(f)} is absent from the Excel function contract; enabled F values for E=${JSON.stringify(e)}: ${choices}`;
    }
    if (entry.status !== "enabled") {
      return `expanded step[${index}] E=${JSON.stringify(e)}, F=${JSON.stringify(f)} is ${entry.status}: ${entry.reason}`;
    }
    if (e === "check_point" && fCmp === "found_times") {
      try {
        validate_g_for_entry(entry, String(step.G || ""), contract);
        parse_found_times_cells(step.G, step.H, step.I);
      } catch (exc: any) {
        return `expanded step[${index}] has invalid found_times A-I syntax: ${exc.message || exc}`;
      }
    } else {
      try {
        validate_g_for_entry(entry, String(step.G || ""), contract);
      } catch (exc: any) {
        if (exc instanceof ExcelContractError) {
          return `expanded step[${index}] has invalid G syntax: ${exc}`;
        }
        throw exc;
      }
    }
  }
  return null;
}

export function _bind_expanded_block(opts: {
  blockIndex: number;
  kind: string;
  block: Record<string, any>;
  steps: Record<string, any>[];
  provenance: Record<string, any>[];
  occurrences: Map<string, number>;
  availableObservationRefs: Set<string>;
}): string | null {
  const { blockIndex, kind, block, steps, provenance, occurrences, availableObservationRefs } = opts;
  if (steps.length !== provenance.length) {
    return _err(blockIndex, kind, "expanded provenance is not step-aligned");
  }
  const observations: string[] = [];
  for (let offset = 0; offset < steps.length; offset++) {
    const step = steps[offset];
    const prov = provenance[offset];
    const e = String(step.E || "").trim();
    const f = String(step.F || "").trim();
    if (e === "" || e === "check_point" || e === "time" || !f) {
      continue;
    }
    const declaredStepObservation = Boolean(kind === "STEP" && String(block.observation_id || "").trim());
    if (
      !declaredStepObservation &&
      !["OBSERVE_ASSERT", "OBSERVE_EXIT", "CAPTURE_COMPARE", "OBSERVE_ONLY", "OBSERVE_DIST", "OBSERVE_MEMBER", "CAPTURE", "EXPECT_FROM"].includes(kind)
    ) {
      continue;
    }
    const material = JSON.stringify({ E: e, F: f, G: String(step.G || ""), H: String(step.H || ""), I: String(step.I || "") });
    const digest = crypto.createHash("sha256").update(material, "utf8").digest("hex").slice(0, 24);
    const occurrence = occurrences.get(digest) || 0;
    occurrences.set(digest, occurrence + 1);
    const declaredId = kind === "STEP" ? String(block.observation_id || "").trim() : "";
    const observationId = declaredId || `obs_${digest}_${occurrence}`;
    const resultChannel = (kind === "STEP" ? String(block.result_channel || "").trim() : "") || `result_${observationId}`;
    delete prov.observation_ref;
    prov.observation_id = observationId;
    prov.result_channel = resultChannel;
    availableObservationRefs.add(observationId);
    availableObservationRefs.add(resultChannel);
    observations.push(observationId);
  }
  const assertions: [Record<string, any>, Record<string, any>][] = [];
  for (let offset = 0; offset < steps.length; offset++) {
    if (String(steps[offset].E || "").trim() === "check_point") {
      assertions.push([steps[offset], provenance[offset]]);
    }
  }
  if (!assertions.length) {
    return null;
  }
  const explicitRef = String(block.observation_ref || "").trim();
  if (kind === "STEP" && !explicitRef) {
    return _err(blockIndex, kind, "check_point STEP requires observation_ref naming an earlier explicit observation_id/result_channel; row adjacency is not a binding");
  }
  if (explicitRef && !availableObservationRefs.has(explicitRef)) {
    return _err(blockIndex, kind, `observation_ref ${JSON.stringify(explicitRef)} does not name an earlier explicit observation_id/result_channel in this blocks array`);
  }
  if (kind !== "STEP" && !observations.length) {
    return _err(blockIndex, kind, "assertion-producing combinator has no structural observation producer");
  }
  const reference = explicitRef || observations[observations.length - 1];
  for (const [, prov] of assertions) {
    delete prov.observation_id;
    delete prov.result_channel;
    prov.observation_ref = reference;
  }
  return null;
}

export function expand_blocks(
  blocks: any,
  provenanceSteps: any[] | null = null
): [Record<string, any>[] | null, Record<string, any>[] | null, string | null] {
  if (!Array.isArray(blocks) || !blocks.length) {
    return [null, null, "blocks must be a non-empty array"];
  }
  if (provenanceSteps !== null && provenanceSteps.length !== blocks.length) {
    return [null, null, `provenance steps count (${provenanceSteps.length}) must equal blocks count (${blocks.length}) — annotate at **combinator granularity**, not expanded rows: with ${blocks.length} combinators, provenance.steps holds ${blocks.length} entries (each {layer, source} maps to one combinator; row expansion is the tool's job).`];
  }
  const steps: Record<string, any>[] = [];
  const provOut: Record<string, any>[] = [];
  let regN = 0;
  const definedRegisters = new Set<string>();
  const captureRegisters = new Set<string>();
  const observationOccurrences = new Map<string, number>();
  const availableObservationRefs = new Set<string>();
  const deferredSslSteps: [Record<string, any>[], Record<string, any>[]][] = [];
  const assertionSlots: [string, number][] = [];

  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    if (typeof b !== "object" || b === null || Array.isArray(b)) {
      return [null, null, _err(i, "?", "each combinator must be an object")];
    }
    const kind = String(b.kind || "").trim().toUpperCase();
    const desc = String(b.desc || "");
    if ("timeout_s" in b && kind !== "CONFIG" && kind !== "STEP") {
      return [null, null, _err(i, kind, "timeout_s is supported only by CONFIG or APV cmd_config STEP")];
    }
    const nestedIdError = _nested_assertion_id_error(i, kind || "?", b);
    if (nestedIdError) {
      return [null, null, nestedIdError];
    }
    let assertionIds: Record<string, string> = {};
    if (_NO_ASSERTION_ID_KINDS.has(kind)) {
      const blockIdError = _reject_block_level_assertion_ids(i, kind, b);
      if (blockIdError) {
        return [null, null, blockIdError];
      }
    } else if (_ASSERTION_ID_BLOCK_KINDS.has(kind)) {
      let blockIdError: string;
      [assertionIds, blockIdError] = _assertion_identity(b);
      if (blockIdError) {
        return [null, null, _err(i, kind, blockIdError)];
      }
    }
    const pv = provenanceSteps !== null ? provenanceSteps[i] : null;
    const explicitIdError = _reject_explicit_provenance_assertion_ids(i, kind || "?", pv);
    if (explicitIdError) {
      return [null, null, explicitIdError];
    }
    let produced = 0;
    const blockStepStart = steps.length;
    const blockProvStart = provOut.length;
    const blockAuto: Record<string, any>[] = [];

    if (kind === "SSL_CERT_LOAD") {
      if (provenanceSteps !== null) {
        return [null, null, _err(i, kind, "SSL_CERT_LOAD mints engine-owned per-step provenance while it lowers to CONFIG/STEP blocks; omit the explicit provenance_steps entry and use the block's projected fields")];
      }
      const { split_ssl_certificate_load_blocks } = require("../ist_core/tools/device/emit_xlsx_tool");
      const [setupBlocks, cleanupBlocks, lowerError] = split_ssl_certificate_load_blocks(b);
      if (lowerError || setupBlocks === null || cleanupBlocks === null) {
        return [null, null, _err(i, kind, lowerError)];
      }
      const [loweredSteps, loweredProv, nestedError] = expand_blocks(setupBlocks);
      if (nestedError || loweredSteps === null || loweredProv === null) {
        return [null, null, _err(i, kind, nestedError || "standard-library lowering returned no steps")];
      }
      steps.push(...loweredSteps);
      produced = loweredSteps.length;
      blockAuto.push(...loweredProv);
      for (const step of loweredSteps) {
        const register = String(step.H || "").trim();
        if (register) {
          definedRegisters.add(register);
        }
      }
      const [cleanupSteps, cleanupProv, cleanupError] = expand_blocks(cleanupBlocks);
      if (cleanupError || cleanupSteps === null || cleanupProv === null) {
        return [null, null, _err(i, kind, cleanupError || "standard-library teardown returned no steps")];
      }
      deferredSslSteps.push([cleanupSteps, cleanupProv]);
    } else if (kind === "STEP") {
      const [step, stepProv, stepErr] = _expand_generic_step(i, b, definedRegisters, captureRegisters);
      if (stepErr) {
        return [null, null, stepErr];
      }
      steps.push(step!);
      produced = 1;
      blockAuto.push(stepProv!);
    } else if (kind === "CONFIG") {
      const timeoutError = _command_timeout_error(i, kind, b);
      if (timeoutError) {
        return [null, null, timeoutError];
      }
      let cmds = b.cmds;
      if (!Array.isArray(cmds) || !cmds.length || !cmds.every((c: any) => typeof c === "string")) {
        return [null, null, _err(i, kind, "cmds must be a non-empty list of command strings (one command per element)")];
      }
      const short = cmds.filter((c: string) => c.trim().length <= 2);
      if (cmds.length > 2 && short.length > Math.floor(cmds.length / 2)) {
        return [null, null, _err(i, kind, `cmds looks character-split (${short.length}/${cmds.length} elements ≤2 chars) — each array element must be **one whole command**, not single characters. Pass the whole command as one string element.`)];
      }
      cmds = cmds.map((c: string) => c.trim()).filter((c: string) => c);
      if (!cmds.length) {
        return [null, null, _err(i, kind, "cmds are all empty — provide real commands (one per element)")];
      }
      const dut = String(b.host || "APV_0").trim();
      if (!_DUT_HOSTS.includes(dut)) {
        return [null, null, _err(i, kind, `CONFIG.host must be one of ${_DUT_HOSTS.join(", ")} (the device under test); got ${JSON.stringify(dut)}`)];
      }
      if ("timeout_s" in b) {
        for (const cmd of cmds) {
          const timeoutCmdError = _timeout_command_error(i, kind, cmd);
          if (timeoutCmdError) {
            return [null, null, timeoutCmdError];
          }
          steps.push({ E: dut, F: "cmd_config", G: `${cmd},timeout=${b.timeout_s}`, desc });
          blockAuto.push({ layer: "G", source: _parse_ref(b.ref) });
        }
        produced = cmds.length;
      } else if (cmds.length === 1) {
        steps.push({ E: dut, F: "cmd_config", G: cmds[0], desc });
      } else {
        steps.push({ E: dut, F: "cmds_config", G: cmds.join("\n"), desc });
      }
      if (!("timeout_s" in b)) {
        produced = 1;
        blockAuto.push({ layer: "G", source: _parse_ref(b.ref) });
      }
    } else if (kind === "OBSERVE_EXIT") {
      const cmd = String(b.cmd || "").trim();
      const host = String(b.host || "").trim();
      const expect = String(b.expect || "").trim().toLowerCase();
      if (!cmd || !host) {
        return [null, null, _err(i, kind, "host and cmd are required")];
      }
      if (_DUT_HOSTS.includes(host)) {
        const { observe_exit_channel_error } = require("./apv_lang");
        return [null, null, _err(i, kind, observe_exit_channel_error(host))];
      }
      const answererError = _answerer_shape_error(i, kind, b);
      if (answererError) {
        return [null, null, answererError];
      }
      const maskingError = _exit_status_masking_error(cmd);
      if (maskingError) {
        return [null, null, _err(i, kind, maskingError)];
      }
      if (!(_EXIT_STATUS_EXPECTS as readonly string[]).includes(expect)) {
        return [null, null, _err(i, kind, `expect must be one of ${_EXIT_STATUS_EXPECTS.join(", ")}; got ${JSON.stringify(expect)}`)];
      }
      const { exit_status_assertion } = require("./provenance_ir");
      const probe = expect === "failure" ? _probe_tool_name(cmd) : "";
      let probeCodes: number[] = [];
      if (expect === "failure") {
        if (cmd.includes("&&")) {
          return [null, null, _err(i, kind, "expect=failure requires a single probe command; an && conjunction cannot name one transport-failure class")];
        }
        const { probe_tool_transport_failure_codes } = require("./domain_grammar");
        const table = probe_tool_transport_failure_codes();
        if (!(probe in table)) {
          return [null, null, _err(i, kind, `expect=failure asserts a transport-level failure of the probe tool, so the probe must be a tool whose transport-failure exit codes are documented in the grammar probe_tools table (registered: ${Object.keys(table).sort().join(", ")}); got ${JSON.stringify(probe || "<none>")}. A bare non-zero exit code is not accepted: it also matches client-side errors and misses answered refusals.`)];
        }
        probeCodes = table[probe];
      }
      const [assertionStep, statusError] = exit_status_assertion(expect, probe, probeCodes);
      if (assertionStep === null) {
        return [null, null, _err(i, kind, statusError)];
      }
      assertionStep.desc = desc;
      steps.push(_observe_step(host, _exit_status_command(cmd), desc));
      steps.push(assertionStep);
      produced = 2;
      const statusRecipe = "status.exit:" + crypto.createHash("sha256")
        .update(JSON.stringify({ host: host.toLowerCase(), cmd, expect }), "utf8")
        .digest("hex").slice(0, 24);
      const [statusSource, statusSourceError] = _derived_binding_source({
        sourceKind: "status_derived",
        recipeId: statusRecipe,
        ruleId: "status.exit-code",
        sourceInput: expect === "failure" ? { expect, probe, codes: probeCodes } : { expect },
        outputStep: assertionStep,
      });
      if (statusSource === null) {
        return [null, null, _err(i, kind, statusSourceError)];
      }
      const statusProvenance: Record<string, any> = { layer: "V", source: statusSource, ...assertionIds };
      if (typeof b.assertion_type === "object" && b.assertion_type !== null) {
        statusProvenance.assertion_type = JSON.parse(JSON.stringify(b.assertion_type));
      }
      blockAuto.push({ layer: "G", source: _dispatch_source(steps[steps.length - 2].E, steps[steps.length - 2].F, steps[steps.length - 2].G, b.cmd_ref) });
      blockAuto.push(statusProvenance);
    } else if (kind === "OBSERVE_ASSERT") {
      const cmd = String(b.cmd || "").trim();
      const host = String(b.host || "").trim();
      const asserts = b.asserts;
      if (!cmd || !host) {
        return [null, null, _err(i, kind, "host and cmd are required")];
      }
      if (!Array.isArray(asserts) || !asserts.length) {
        return [null, null, _err(i, kind, "asserts must be a non-empty assertion list; use OBSERVE_ONLY for observation without assertions")];
      }
      const answererError = _answerer_shape_error(i, kind, b);
      if (answererError) {
        return [null, null, answererError];
      }
      steps.push(_observe_step(host, cmd, desc));
      produced = 1;
      blockAuto.push({ layer: "G", source: _dispatch_source(steps[steps.length - 1].E, steps[steps.length - 1].F, steps[steps.length - 1].G, b.cmd_ref || b.ref) });
      for (let j = 0; j < asserts.length; j++) {
        const a = asserts[j];
        if (typeof a !== "object" || a === null || Array.isArray(a)) {
          return [null, null, _err(i, kind, `asserts[${j}] must be an object`)];
        }
        const op = String(a.op || "").trim();
        const pattern = a.pattern;
        if (!(_ASSERT_OPS as readonly string[]).includes(op)) {
          return [null, null, _err(i, kind, `asserts[${j}].op must be one of ${_ASSERT_OPS.join(", ")}; got ${JSON.stringify(op)}`)];
        }
        if (typeof pattern !== "string" || !pattern.trim()) {
          return [null, null, _err(i, kind, `asserts[${j}].pattern must be non-empty text/regex`)];
        }
        const assertionStep: Record<string, any> = { E: "check_point", F: op, G: pattern, desc: String(a.desc || "") };
        const exempt = a.exempt;
        const reasonCode = String(a.reason_code || "").trim();
        if (exempt !== null && exempt !== undefined && exempt !== false && exempt !== true) {
          return [null, null, _err(i, kind, `asserts[${j}].exempt must be a boolean when present`)];
        }
        if (exempt !== true && reasonCode) {
          return [null, null, _err(i, kind, `asserts[${j}].reason_code is valid only when exempt=true`)];
        }
        if (exempt === true) {
          assertionStep.exempt = true;
          assertionStep.reason_code = reasonCode;
        }
        const specGap = a.spec_gap;
        if (specGap !== null && specGap !== undefined && !(typeof specGap === "string" && specGap.trim())) {
          return [null, null, _err(i, kind, `asserts[${j}].spec_gap, when present, must be one line naming what the governing spec does not state`)];
        }
        steps.push(assertionStep);
        produced += 1;
        let assertionSource = _parse_ref(a.ref);
        if (assertionSource.kind === "config_derived") {
          const bindingInput = a.binding_input;
          if (typeof bindingInput !== "object" || bindingInput === null || Array.isArray(bindingInput)) {
            return [null, null, _err(i, kind, `asserts[${j}] config_derived requires binding_input with an independently recomputable rule_id and source_input`)];
          }
          const keys = Object.keys(bindingInput).sort();
          if (keys.length !== 2 || keys[0] !== "rule_id" || keys[1] !== "source_input") {
            return [null, null, _err(i, kind, `asserts[${j}].binding_input requires exactly rule_id/source_input`)];
          }
          const sourceInput = bindingInput.source_input;
          if (typeof sourceInput !== "object" || sourceInput === null || Array.isArray(sourceInput)) {
            return [null, null, _err(i, kind, `asserts[${j}].binding_input.source_input must be an object`)];
          }
          const [newSource, bindingError] = _derived_binding_source({
            sourceKind: "config_derived",
            recipeId: String(assertionSource.ref || ""),
            ruleId: String(bindingInput.rule_id || ""),
            sourceInput,
            outputStep: assertionStep,
          });
          if (newSource === null) {
            return [null, null, _err(i, kind, `asserts[${j}].binding_input is invalid: ${bindingError}`)];
          }
          assertionSource = newSource;
        } else if ("binding_input" in a) {
          return [null, null, _err(i, kind, `asserts[${j}].binding_input is valid only when ref uses config_derived`)];
        }
        const [assertIds, assertIdError] = _assertion_identity(a);
        if (assertIdError) {
          return [null, null, _err(i, kind, `asserts[${j}].${assertIdError}`)];
        }
        const assertionProvenance: Record<string, any> = { layer: "V", source: assertionSource };
        if (typeof a.assertion_type === "object" && a.assertion_type !== null) {
          assertionProvenance.assertion_type = JSON.parse(JSON.stringify(a.assertion_type));
        }
        Object.assign(assertionProvenance, assertIds);
        if (typeof specGap === "string" && specGap.trim()) {
          assertionProvenance.spec_gap = specGap.trim();
        }
        blockAuto.push(assertionProvenance);
      }
    } else if (kind === "CAPTURE_COMPARE") {
      const host = String(b.host || "").trim();
      const cap = String(b.capture_cmd || "").trim();
      const cmd = String(b.cmd || "").trim() || cap;
      const relation = String(b.relation || "").trim().toLowerCase();
      if (!host || !cap) {
        return [null, null, _err(i, kind, "host and capture_cmd are required")];
      }
      if (relation !== "same" && relation !== "differs") {
        return [null, null, _err(i, kind, `relation must be same (two observations equal) or differs (two observations differ); got ${JSON.stringify(relation)}`)];
      }
      let reg: string;
      for (;;) {
        regN += 1;
        reg = `v${regN}`;
        if (!definedRegisters.has(reg)) {
          break;
        }
      }
      definedRegisters.add(reg);
      captureRegisters.add(reg!);
      steps.push(_observe_step(host, cap, desc + "(第一次观测,捕获基线)", reg));
      steps.push(_observe_step(host, cmd, desc + "(第二次观测,产生被比较输出)"));
      const op = relation === "same" ? "found" : "not_found";
      steps.push({ E: "check_point", F: op, G: "", H: reg, desc: desc + (relation === "same" ? "(两次相同)" : "(两次不同)") });
      produced = 3;
      const src = _dispatch_source(steps[steps.length - 3].E, steps[steps.length - 3].F, steps[steps.length - 3].G, b.ref);
      const [relationSource, relationError] = _derived_binding_source({
        sourceKind: "captured_relation",
        recipeId: "",
        ruleId: "capture.static-relation",
        sourceInput: { relation },
        outputStep: steps[steps.length - 1],
      });
      if (relationSource === null) {
        return [null, null, _err(i, kind, relationError)];
      }
      const relationProvenance: Record<string, any> = { layer: "V", source: relationSource };
      if (typeof b.assertion_type === "object" && b.assertion_type !== null) {
        relationProvenance.assertion_type = JSON.parse(JSON.stringify(b.assertion_type));
      }
      Object.assign(relationProvenance, assertionIds);
      blockAuto.push({ layer: "G", source: { ...src } });
      blockAuto.push({ layer: "G", source: { ...src } });
      blockAuto.push(relationProvenance);
    } else if (kind === "OBSERVE_ONLY") {
      const cmd = String(b.cmd || "").trim();
      const host = String(b.host || "").trim();
      if (!cmd || !host) {
        return [null, null, _err(i, kind, "host and cmd are required")];
      }
      steps.push(_observe_step(host, cmd, desc));
      produced = 1;
      blockAuto.push({ layer: "G", source: _dispatch_source(steps[steps.length - 1].E, steps[steps.length - 1].F, steps[steps.length - 1].G, b.cmd_ref || b.ref) });
    } else if (kind === "OBSERVE_DIST") {
      const cmd = String(b.cmd || "").trim();
      const host = String(b.host || "").trim();
      const total = b.total;
      const field = b.field;
      const buckets = b.buckets;
      if (!cmd || !host) {
        return [null, null, _err(i, kind, "host and cmd are required")];
      }
      if (total === null || total === undefined) {
        return [null, null, _err(i, kind, "total (total request count for the distribution check) is required")];
      }
      if (!Array.isArray(buckets) || !buckets.length) {
        return [null, null, _err(i, kind, "buckets must be a non-empty list of {anchor, expected, tol?, pattern?}")];
      }
      if (field === null || field === undefined) {
        return [null, null, _err(i, kind, "field (a same-line count-field regex prefix, not a complete pattern) is required; use an empty string when every bucket supplies its own complete pattern containing {range}")];
      }
      const bindingError = distribution_count_binding_error(field, buckets);
      if (bindingError) {
        return [null, null, _err(i, kind, bindingError)];
      }
      steps.push(_observe_step(host, cmd, desc));
      steps.push({ E: "check_point", F: "dist", dist: { total, field: String(field || ""), buckets }, desc });
      if (b.exempt === true) {
        steps[steps.length - 1].exempt = true;
        steps[steps.length - 1].reason_code = String(b.reason_code || "").trim();
      }
      produced = 2;
      blockAuto.push({ layer: "G", source: _dispatch_source(steps[steps.length - 2].E, steps[steps.length - 2].F, steps[steps.length - 2].G, b.cmd_ref || b.ref) });
      const parsedDistRef = _parse_ref(b.ref);
      const distProvenance: Record<string, any> = { layer: "V", source: { kind: "distribution_derived", ref: String(parsedDistRef.ref || "") } };
      if (typeof b.assertion_type === "object" && b.assertion_type !== null) {
        distProvenance.assertion_type = JSON.parse(JSON.stringify(b.assertion_type));
      }
      Object.assign(distProvenance, assertionIds);
      blockAuto.push(distProvenance);
    } else if (kind === "OBSERVE_MEMBER") {
      const cmd = String(b.cmd || "").trim();
      const host = String(b.host || "").trim();
      const ips = b.ips;
      const present = b.present;
      if (!cmd || !host) {
        return [null, null, _err(i, kind, "host and cmd are required")];
      }
      if (!Array.isArray(ips) || !ips.length) {
        return [null, null, _err(i, kind, "ips must be a non-empty list of member IP strings")];
      }
      if (present === null || present === undefined) {
        return [null, null, _err(i, kind, "present is required (true=expect output within ips, false=expect output NOT within ips)")];
      }
      steps.push(_observe_step(host, cmd, desc));
      steps.push({ E: "check_point", F: "member", member: { ips, present }, desc });
      produced = 2;
      blockAuto.push({ layer: "G", source: _dispatch_source(steps[steps.length - 2].E, steps[steps.length - 2].F, steps[steps.length - 2].G, b.cmd_ref || b.ref) });
      const parsedMemberRef = _parse_ref(b.ref);
      const memberProvenance: Record<string, any> = { layer: "V", source: { kind: "membership_derived", ref: String(parsedMemberRef.ref || "") } };
      if (typeof b.assertion_type === "object" && b.assertion_type !== null) {
        memberProvenance.assertion_type = JSON.parse(JSON.stringify(b.assertion_type));
      }
      Object.assign(memberProvenance, assertionIds);
      blockAuto.push(memberProvenance);
    } else if (kind === "CAPTURE") {
      const host = String(b.host || "").trim();
      const cmd = String(b.cmd || "").trim();
      const saveAs = String(b.save_as || "").trim();
      if (!host || !cmd) {
        return [null, null, _err(i, kind, "host and cmd are required")];
      }
      if (!saveAs || !_REGISTER_NAME_RE.test(saveAs)) {
        return [null, null, _err(i, kind, `save_as must be a non-empty identifier (letters/digits/underscore, not starting with a digit) naming the register this capture is stored under; got ${JSON.stringify(saveAs)}`)];
      }
      if (_AUTO_REGISTER_RE.test(saveAs)) {
        return [null, null, _err(i, kind, `save_as ${JSON.stringify(saveAs)} looks like the internal v<N> pattern CAPTURE_COMPARE auto-allocates — pick a descriptive name instead to avoid colliding with it in the shared runtime register namespace.`)];
      }
      if (captureRegisters.has(saveAs)) {
        return [null, null, _err(i, kind, `save_as ${JSON.stringify(saveAs)} was already captured earlier in this same blocks array — pick a distinct name, or drop this duplicate CAPTURE.`)];
      }
      captureRegisters.add(saveAs);
      definedRegisters.add(saveAs);
      steps.push(_observe_step(host, cmd, desc, saveAs));
      produced = 1;
      blockAuto.push({ layer: "G", source: _dispatch_source(steps[steps.length - 1].E, steps[steps.length - 1].F, steps[steps.length - 1].G, b.ref) });
    } else if (kind === "EXPECT_FROM") {
      const host = String(b.host || "").trim();
      const cmd = String(b.cmd || "").trim();
      const expectedFrom = String(b.expected_from || "").trim();
      const op = String(b.op || "").trim();
      if (!host || !cmd) {
        return [null, null, _err(i, kind, "host and cmd are required")];
      }
      if (!(_ASSERT_OPS as readonly string[]).includes(op)) {
        return [null, null, _err(i, kind, `op must be one of ${_ASSERT_OPS.join(", ")}; got ${JSON.stringify(op)}`)];
      }
      if (!expectedFrom) {
        return [null, null, _err(i, kind, "expected_from (the register name captured earlier by a CAPTURE combinator) is required")];
      }
      if (!captureRegisters.has(expectedFrom)) {
        return [null, null, _err(i, kind, `expected_from ${JSON.stringify(expectedFrom)} has not been captured by any earlier CAPTURE combinator in this blocks array — capture it first (add a CAPTURE block with save_as=${JSON.stringify(expectedFrom)} before this one), or fix the register name.`)];
      }
      steps.push(_observe_step(host, cmd, desc));
      steps.push({ E: "check_point", F: op, G: "", H: expectedFrom, desc });
      produced = 2;
      blockAuto.push({ layer: "G", source: _dispatch_source(steps[steps.length - 2].E, steps[steps.length - 2].F, steps[steps.length - 2].G, b.cmd_ref || b.ref) });
      const [expectedSource, expectedError] = _derived_binding_source({
        sourceKind: "captured_relation",
        recipeId: "",
        ruleId: "capture.static-reference",
        sourceInput: { operator: op, register: expectedFrom },
        outputStep: steps[steps.length - 1],
      });
      if (expectedSource === null) {
        return [null, null, _err(i, kind, expectedError)];
      }
      const expectedProvenance: Record<string, any> = { layer: "V", source: expectedSource };
      if (typeof b.assertion_type === "object" && b.assertion_type !== null) {
        expectedProvenance.assertion_type = JSON.parse(JSON.stringify(b.assertion_type));
      }
      Object.assign(expectedProvenance, assertionIds);
      blockAuto.push(expectedProvenance);
    } else if (kind === "SLEEP") {
      let sec: number;
      try {
        sec = parseInt(String(b.seconds), 10);
        if (Number.isNaN(sec)) throw new Error("nan");
      } catch {
        return [null, null, _err(i, kind, "seconds must be an integer")];
      }
      if (sec <= 0 || sec > 300) {
        return [null, null, _err(i, kind, `seconds must be within 1..300; got ${sec}`)];
      }
      steps.push({ E: "time", F: "sleep", G: String(sec), desc });
      produced = 1;
      blockAuto.push({ layer: "E", source: { kind: "emit_auto", ref: "" } });
    } else {
      const keys = Object.keys(b);
      const hint = !("kind" in b)
        ? " — you probably omitted kind, or used an alias."
        : `; kind value ${JSON.stringify(b.kind)} is not in the allowed set.`;
      return [null, null, _err(i, kind || "missing-kind", `each combinator needs a kind field: one of CONFIG/OBSERVE_ASSERT/OBSERVE_EXIT/CAPTURE_COMPARE/OBSERVE_ONLY/OBSERVE_DIST/OBSERVE_MEMBER/CAPTURE/EXPECT_FROM/SLEEP/SSL_CERT_LOAD/STEP. This combinator's keys=${JSON.stringify(keys)}${hint}`)];
    }

    if (provenanceSteps !== null) {
      const base = typeof pv === "object" && pv !== null ? pv : {};
      for (let offset = 0; offset < produced; offset++) {
        const entry: Record<string, any> = { ...base };
        const auto = offset < blockAuto.length ? blockAuto[offset] : {};
        const target = steps[blockStepStart + offset];
        if (String(target.E || "").trim() === "check_point") {
          for (const name of _ASSERTION_ID_FIELDS) {
            if (name in auto) {
              entry[name] = auto[name];
            }
          }
        }
        provOut.push(entry);
      }
    } else {
      while (blockAuto.length < produced) {
        blockAuto.push({ layer: "G", source: { kind: "emit_auto", ref: "" } });
      }
      provOut.push(...blockAuto.slice(0, produced));
    }
    for (let offset = 0; offset < produced; offset++) {
      if (String(steps[blockStepStart + offset].E || "").trim() === "check_point") {
        assertionSlots.push([_assertion_slot_label(kind, i, offset), blockProvStart + offset]);
      }
    }
    const bindingError = _bind_expanded_block({
      blockIndex: i,
      kind,
      block: b,
      steps: steps.slice(blockStepStart),
      provenance: provOut.slice(blockProvStart),
      occurrences: observationOccurrences,
      availableObservationRefs,
    });
    if (bindingError) {
      return [null, null, bindingError];
    }
  }

  if (deferredSslSteps.length) {
    const cleanupStepsAll: Record<string, any>[] = [];
    const cleanupProvAll: Record<string, any>[] = [];
    for (const [cleanupSteps, cleanupProv] of [...deferredSslSteps].reverse()) {
      cleanupStepsAll.push(...cleanupSteps);
      cleanupProvAll.push(...cleanupProv);
    }
    const assertionPositions = steps.map((s, idx) => (String(s.E || "").trim() === "check_point" ? idx : -1)).filter((idx) => idx >= 0);
    const insertion = assertionPositions.length ? Math.max(...assertionPositions) + 1 : steps.length;
    steps.splice(insertion, 0, ...cleanupStepsAll);
    provOut.splice(insertion, 0, ...cleanupProvAll);
  }
  const coverageError = _assertion_identity_coverage_error(provOut, assertionSlots);
  if (coverageError) {
    return [null, null, coverageError];
  }
  const contractError = _validate_expanded_contract_steps(steps);
  if (contractError) {
    return [null, null, contractError];
  }
  return [steps, provOut, null];
}

export function capture_register_final_operator(operator: any, register: any): string {
  const op = String(operator || "").trim();
  if (op === "found" && String(register || "").trim()) {
    return "abs_found";
  }
  return op;
}

export function lower_derived_assertions(
  steps: Record<string, any>[],
  provenanceSteps: Record<string, any>[] | null
): [Record<string, any>[] | null, Record<string, any>[] | null, string | null] {
  const { expand_distribution_steps, expand_provenance_steps_with_plan } = require("./distribution_assertion");
  const { attach_membership_derivation_receipts, expand_membership_steps } = require("./membership_assertion");
  const distributionSourceSteps = steps;
  let [expanded, plan, error] = expand_distribution_steps(steps);
  if (error || expanded === null || plan === null) {
    return [null, null, "distribution-interval assertion declaration is invalid: " + String(error || "expansion returned no steps")];
  }
  let expandedProvenance: Record<string, any>[];
  try {
    expandedProvenance = expand_provenance_steps_with_plan(provenanceSteps, plan, { sourceSteps: distributionSourceSteps, expandedSteps: expanded });
  } catch (exc: any) {
    return [null, null, "ConfigBinding distribution receipt could not be recomputed: " + String(exc.message || exc)];
  }
  const membershipSourceSteps = expanded;
  let membershipError: string | null;
  [expanded, membershipError] = expand_membership_steps(expanded);
  if (membershipError || expanded === null) {
    return [null, null, "hit-membership assertion declaration is invalid: " + String(membershipError || "expansion returned no steps")];
  }
  try {
    expandedProvenance = attach_membership_derivation_receipts(expandedProvenance, membershipSourceSteps, expanded);
  } catch (exc: any) {
    return [null, null, "ConfigBinding membership receipt could not be recomputed: " + String(exc.message || exc)];
  }
  const finalSteps: Record<string, any>[] = [];
  for (const step of expanded) {
    let s = step;
    if (String((s || {}).E || "").trim() === "check_point") {
      const finalOperator = capture_register_final_operator(s.F, s.H);
      if (finalOperator !== String(s.F || "").trim()) {
        s = { ...s, F: finalOperator };
      }
    }
    finalSteps.push(s);
  }
  return [finalSteps, expandedProvenance, null];
}
