// 生成：tools/extract_engine.py ← InfoTest main/case_compiler/mechanical_case_gate.py（sha256 67c35edc10da202a）。不在这里手改。
import fs from "node:fs";
import { sha256_bytes } from "./_sealed_io";
import { SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY } from "./consistency_contract";
import {
  MECHANICAL_CASE_BODY_KEYS,
  MechanicalCaseError,
  escape_hatch_accounting_defects,
  seal_mechanical_case,
  validate_mechanical_case,
  type EscapeHatchDefect,
} from "./mechanical_case";
import { _canonical_sha256 } from "./mindmap_contract_projector";
import { accepts_schema } from "../common/schema_identity";
import { ADVISE_CODE_CONSUMERS } from "./gate_advisories";
import { CRITERION_TYPE_ALLOWED_SLOTS } from "./criterion_carriers";

const logger = console;
export const GATE_REPORT_SCHEMA = "ist.mechanical-case-gate-report";
export const GATE_ORDER = ["mechanical_case_body", "contract_description", "consistency_contract", "blocks_expansion", "structural_lint", "command_contract", "author_procedure_coverage", "https_certificate_lifecycle", "unreachable_ips", "trigger_reachability", "negative_probe_path", "paired_teardown", "provenance_receipts", "expectation_bijection", "criterion_type_binding", "semantic_key_group_rank", "answerer_statement", "escape_hatch_accounting", "document_consistency", "step_graph"] as const;
export const NUMBERED_GATES = ["blocks_expansion", "structural_lint", "expectation_bijection", "semantic_key_group_rank", "escape_hatch_accounting", "unreachable_ips", "trigger_reachability", "paired_teardown", "command_contract", "https_certificate_lifecycle"] as const;
export const AUDIENCE_WORKER = "worker_directive";
export const AUDIENCE_VERIFICATION_CARD = "verification_card";
const _PROVISIONAL_GATE_REPORT_SHA256 = "0".repeat(64);
const _CHECK_POINT_OBJECT = "check_point";
const _DESCRIPTIVE_FIRST_ARGUMENT = "<descriptive>";
const _CONFIG_STEP_FUNCTIONS = new Set(["cmd_config", "cmds_config"]);
const _ANSWERER_KINDS = ["device", "fixture", "bed_service", "undetermined"] as const;
const _DUT_HOSTS = ["APV_0", "APV_1"];
const _AUTHOR_STEP_ENUMERATOR_RE = /^\s*\d+\s*[.)、:：]\s*/;
export const DYNAMIC_ADVISE_CODE_FAMILIES: Record<string, string> = { _gate_structural_lint: "gate_advisory", _gate_step_graph: "gate_advisory" };

function _isMapping(value: any): value is Record<string, any> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

class _Report {
  autoid: string;
  hard_rejects: Record<string, any>[] = [];
  advisories: Record<string, any>[] = [];
  _ran = new Set<string>();
  _named_by: Record<string, string> = {};

  constructor(autoid: string) {
    this.autoid = autoid;
  }

  ran(gate: string): void {
    this._ran.add(gate);
  }

  reject(gate: string, code: string, locus: string, detail: string, opts: { expectation_ids?: string[] } = {}): void {
    this._ran.add(gate);
    const finding: Record<string, any> = { gate, code, locus, detail, audience: AUDIENCE_WORKER };
    const bound = [...new Set((opts.expectation_ids ?? []).map(String).filter((v) => v))].sort();
    if (bound.length) {
      finding["expectation_ids"] = bound;
    }
    this.hard_rejects.push(finding);
  }

  advise(gate: string, code: string, locus: string, detail: string, extra: Record<string, any> = {}): void {
    if (!(code in ADVISE_CODE_CONSUMERS)) {
      throw new Error(`unregistered gate advisory: ${code}`);
    }
    this._ran.add(gate);
    this.advisories.push({ gate, code, locus, detail, audience: AUDIENCE_VERIFICATION_CARD, ...extra });
  }

  reject_named_by(gate: string, other: string): void {
    this._ran.add(gate);
    this._named_by[gate] = other;
  }

  rejected(gate: string): boolean {
    return this.hard_rejects.some((item) => item["gate"] === gate);
  }

  status(gate: string): string {
    if (!this._ran.has(gate)) {
      return "skipped";
    }
    if (this.rejected(gate) || gate in this._named_by) {
      return "reject";
    }
    if (this.advisories.some((item) => item["gate"] === gate)) {
      return "advisory";
    }
    return "pass";
  }

  render(measurements: Record<string, any> | null, proof: Record<string, string>): Record<string, any> {
    const gates: Record<string, any>[] = [];
    for (const gate of GATE_ORDER) {
      const findings = [...this.hard_rejects, ...this.advisories].filter((item) => item["gate"] === gate);
      const entry: Record<string, any> = {
        gate,
        status: this.status(gate),
        reason_codes: [...new Set(findings.map((item) => String(item["code"] || "")).filter((v) => v))].sort(),
        evidence_loci: [...new Set(findings.map((item) => String(item["locus"] || "")).filter((v) => v))].sort(),
      };
      if (gate in this._named_by) {
        entry["named_by"] = this._named_by[gate];
      }
      gates.push(entry);
    }
    return {
      schema: GATE_REPORT_SCHEMA,
      autoid: this.autoid,
      ok: !this.hard_rejects.length,
      gates,
      hard_rejects: [...this.hard_rejects],
      advisories: [...this.advisories],
      measurements,
      proof: { ...proof },
    };
  }
}

export function gate_report_digest(report: Record<string, any>): string {
  return _canonical_sha256({ ...report });
}

export function load_frozen_contract(p: string): [Record<string, any>, string] {
  const raw = fs.readFileSync(String(p));
  const payload = JSON.parse(raw.toString("utf-8"));
  if (!_isMapping(payload)) {
    throw new Error("contract card must be a JSON object");
  }
  return [payload, sha256_bytes(raw)];
}

export function semantic_key_group_defects(assertions: any[]): [string, string[], number, number][] {
  const groups = new Map<string, any[]>();
  for (const step of assertions) {
    const key = String((step as any)["semantic_key"] ?? "") || "";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(step);
  }
  const defects: [string, string[], number, number][] = [];
  for (const key of [...groups.keys()].sort()) {
    const group = groups.get(key)!;
    const signatures = new Set(group.map((step) => JSON.stringify([String(step["observation_ref"] ?? "") || "", step["F"], step["G"]])));
    if (signatures.size !== group.length) {
      defects.push([key, group.map((step) => String(step["expectation_id"] ?? "") || ""), signatures.size, group.length]);
    }
  }
  return defects;
}

function _first_error(exc: any): string {
  return `${exc?.constructor?.name ?? "Error"}: ${exc?.message ?? exc}`;
}

function _validateBodySegment(name: string, value: any): void {
  if (name === "description") {
    if (!_isMapping(value)) throw new Error("description must be an object");
    if (typeof value["intent_verbatim"] !== "string" || !value["intent_verbatim"].trim()) throw new Error("intent_verbatim must be non-empty text");
    if (!Array.isArray(value["group_path"]) || !value["group_path"].length) throw new Error("group_path must be a non-empty array");
    value["group_path"].forEach((entry: any, index: number) => {
      if (typeof entry !== "string" || !entry.trim()) throw new Error(`group_path[${index}] must be non-empty text`);
    });
    return;
  }
  if (name === "binding") {
    if (!_isMapping(value)) throw new Error("binding must be an object");
    const sha = /^[0-9a-f]{64}$/;
    if (typeof value["contract_sha256"] !== "string" || !sha.test(value["contract_sha256"])) throw new Error("contract_sha256 does not match the required pattern");
    if (value["consistency_contract_sha256"] !== undefined && value["consistency_contract_sha256"] !== null) {
      if (typeof value["consistency_contract_sha256"] !== "string" || !sha.test(value["consistency_contract_sha256"])) throw new Error("consistency_contract_sha256 does not match the required pattern");
    }
    if (typeof value["mindmap_source_sha256"] !== "string" || !sha.test(value["mindmap_source_sha256"])) throw new Error("mindmap_source_sha256 does not match the required pattern");
    if (typeof value["capability_generation_id"] !== "string" || !value["capability_generation_id"].trim()) throw new Error("capability_generation_id must be non-empty text");
    if (typeof value["capability_projection_sha256"] !== "string" || !sha.test(value["capability_projection_sha256"])) throw new Error("capability_projection_sha256 does not match the required pattern");
    if (typeof value["authored_round"] !== "number" || !Number.isInteger(value["authored_round"]) || value["authored_round"] < 1) throw new Error("authored_round must be >= 1");
    return;
  }
  throw new Error(`unknown segment ${name}`);
}

function _validateExpectationBindingEntry(entry: any): void {
  if (!_isMapping(entry)) throw new Error("expectation binding entry must be an object");
  if (typeof entry["expectation_id"] !== "string" || !entry["expectation_id"]) throw new Error("expectation_id must be non-empty text");
  if (typeof entry["semantic_key"] !== "string" || !entry["semantic_key"]) throw new Error("semantic_key must be non-empty text");
  if (typeof entry["claim_kind"] !== "string" || !entry["claim_kind"]) throw new Error("claim_kind must be non-empty text");
  if (typeof entry["block_index"] !== "number" || !Number.isInteger(entry["block_index"]) || entry["block_index"] < 0) throw new Error("block_index must be a non-negative integer");
  const assertIndex = entry["assert_index"];
  if (assertIndex !== undefined && assertIndex !== null && (typeof assertIndex !== "number" || !Number.isInteger(assertIndex) || assertIndex < 0)) throw new Error("assert_index must be a non-negative index or null");
  const scopeRef = entry["scope_ref"];
  if (scopeRef !== undefined && scopeRef !== null && (typeof scopeRef !== "string" || !scopeRef.trim())) throw new Error("scope_ref must be non-empty text or null");
  const stateStep = entry["state_change_step"];
  if (stateStep !== undefined && stateStep !== null && (typeof stateStep !== "number" || !Number.isInteger(stateStep) || stateStep < 0)) throw new Error("state_change_step must be a non-negative index or null");
  const disclosure = entry["binding_disclosure"];
  if (disclosure !== undefined && disclosure !== null && (typeof disclosure !== "string" || !disclosure.trim())) throw new Error("binding_disclosure must be non-empty text or null");
  const hasState = stateStep !== undefined && stateStep !== null;
  const hasDisclosure = disclosure !== undefined && disclosure !== null;
  if (hasState !== hasDisclosure) throw new Error("state_change_step and binding_disclosure are declared together or not at all");
}

function _validateEscapeHatchEntry(entry: any): void {
  if (!_isMapping(entry)) throw new Error("escape hatch entry must be an object");
  if (typeof entry["block_index"] !== "number" || !Number.isInteger(entry["block_index"]) || entry["block_index"] < 0) throw new Error("block_index must be a non-negative integer");
  if (!Array.isArray(entry["capabilities_touched"])) throw new Error("capabilities_touched must be an array");
  entry["capabilities_touched"].forEach((value: any, index: number) => {
    if (typeof value !== "string" || !value.trim()) throw new Error(`capabilities_touched[${index}] must be non-empty text`);
  });
  if (typeof entry["reason"] !== "string" || !entry["reason"].trim()) throw new Error("escape hatch reason must be non-empty text");
}

function _gate_body(mc: any, report: _Report): Record<string, any> | null {
  const gate = "mechanical_case_body";
  report.ran(gate);
  if (!_isMapping(mc)) {
    report.reject(gate, "not_an_object", "case", "mechanical case body must be a JSON object");
    return null;
  }
  const body = { ...mc };
  if ("seal" in body) {
    report.reject(gate, "seal_self_reported", "seal", "the seal is minted by these submission rules after its report is final; submit the eight body keys only");
    return null;
  }
  const keys = new Set(Object.keys(body));
  const expected = MECHANICAL_CASE_BODY_KEYS;
  const sameSet = keys.size === expected.size && [...keys].every((k) => expected.has(k as any));
  if (!sameSet) {
    report.reject(gate, "body_keys_mismatch", "case", `missing=${JSON.stringify([...expected].filter((k) => !keys.has(k as string)).sort())}, unknown=${JSON.stringify([...keys].filter((k) => !expected.has(k as any)).sort())}`);
    return null;
  }
  for (const name of ["description", "binding"]) {
    try {
      _validateBodySegment(name, body[name]);
    } catch (exc: any) {
      report.reject(gate, "segment_invalid", name, _first_error(exc));
    }
  }
  for (const name of ["expectation_binding", "escape_hatches"]) {
    const entries = body[name];
    if (!Array.isArray(entries)) {
      report.reject(gate, "segment_invalid", name, `${name} must be an array`);
      continue;
    }
    entries.forEach((entry: any, index: number) => {
      try {
        if (name === "expectation_binding") _validateExpectationBindingEntry(entry);
        else _validateEscapeHatchEntry(entry);
      } catch (exc: any) {
        report.reject(gate, "segment_invalid", `${name}[${index}]`, _first_error(exc));
      }
    });
  }
  if (!Array.isArray(body["blocks"]) || !body["blocks"].length) {
    report.reject(gate, "segment_invalid", "blocks", "blocks must be a non-empty array of combinators");
  }
  if (!Array.isArray(body["init_commands"])) {
    report.reject(gate, "segment_invalid", "init_commands", "init_commands must be an array of command strings");
  }
  return report.rejected(gate) ? null : body;
}

function _gate_contract_description(body: Record<string, any>, contract: Record<string, any>, report: _Report): void {
  const gate = "contract_description";
  report.ran(gate);
  const description = body["description"];
  const mindmapGroup = contract["mindmap_group"];
  const expectedPath = _isMapping(mindmapGroup) ? mindmapGroup["group_path"] : null;
  if (!_isMapping(description)) {
    return;
  }
  const actualIntent = String(description["intent_verbatim"] || "");
  const expectedIntent = String(contract["intent_verbatim"] || "");
  if (actualIntent !== expectedIntent) {
    report.reject(gate, "intent_verbatim_mismatch", "description.intent_verbatim", `description.intent_verbatim must be copied byte-for-byte from the frozen contract card. Do not replace the author title with a procedure summary. expected=${JSON.stringify(expectedIntent)}; actual=${JSON.stringify(actualIntent)}`);
  }
  const actualPath = description["group_path"];
  if (!Array.isArray(expectedPath) || JSON.stringify(actualPath) !== JSON.stringify(expectedPath)) {
    report.reject(gate, "group_path_mismatch", "description.group_path", `description.group_path must be copied byte-for-byte and in order from contract.mindmap_group.group_path; expected=${JSON.stringify(expectedPath)}; actual=${JSON.stringify(actualPath)}`);
  }
}

function _first_argument_is_descriptive(token: string): boolean {
  return !/^[\x00-\x7F]*$/.test(String(token));
}

function _isIpLiteral(value: string): boolean {
  const v4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
  const m4 = v4.exec(value);
  if (m4) {
    return m4.slice(1).every((part) => Number(part) <= 255);
  }
  return /^[0-9a-fA-F:]+$/.test(value) && value.includes(":");
}

function _procedure_command_signature(vendor: any, command: string, verdict: Record<string, any>): string {
  const head = String(verdict["head"] || "").trim();
  const tokens = [...vendor.norm_command_tokens(command)];
  const headTokens = [...vendor.norm_command_tokens(head)];
  const remainder = JSON.stringify(tokens.slice(0, headTokens.length)) === JSON.stringify(headTokens) ? tokens.slice(headTokens.length) : [];
  let first = remainder.length ? remainder[0] : "";
  if (first && _first_argument_is_descriptive(first)) {
    first = _DESCRIPTIVE_FIRST_ARGUMENT;
  } else if (first) {
    if (_isIpLiteral(first)) {
      first = "<ip>";
    } else {
      first = /^\d+$/.test(first) ? "<number>" : first.toLowerCase();
    }
  }
  return `${head}␟${first}`;
}

function _counterAdd(counter: Map<string, number>, key: string, n = 1): void {
  counter.set(key, (counter.get(key) ?? 0) + n);
}

function _gate_author_procedure_coverage(contract: Record<string, any>, steps: any[], init: string, report: _Report, opts: { device_build: string }): void {
  const gate = "author_procedure_coverage";
  report.ran(gate);
  const { ADAPTED_STEPS_KEY } = require("./step_structure");
  const adaptedRows = ((contract[ADAPTED_STEPS_KEY] || []) as any[]).filter((row) => _isMapping(row) && String(row["n"] || "") && String(row["text"] || ""));
  const authoredRows = contract["author_steps"];
  const authorSteps = adaptedRows.length ? adaptedRows : authoredRows;
  if (!Array.isArray(authorSteps) || !authorSteps.length) {
    return;
  }
  const { _ordered_apv_command_refs, build_command_tree_resolver } = require("../ist_core/tools/device/emit_xlsx_tool");
  const [vendor, _inventory, resolve] = build_command_tree_resolver({ device_build: opts.device_build });

  function _obligations(rows: any, label: string): [Map<string, number>, Map<string, string[]>, Map<string, number>] {
    const req = new Map<string, number>();
    const ev = new Map<string, string[]>();
    const heads = new Map<string, number>();
    for (const step of rows || []) {
      if (!_isMapping(step)) continue;
      const stepId = String(step["n"] || "");
      for (const rawLine of String(step["text"] || "").split("\n")) {
        const candidate = rawLine.trim().replace(_AUTHOR_STEP_ENUMERATOR_RE, "");
        if (!candidate) continue;
        const verdict = resolve(candidate);
        if (verdict["kind"] !== "hit") continue;
        const signature = _procedure_command_signature(vendor, candidate, verdict);
        _counterAdd(req, signature);
        _counterAdd(heads, signature.split("␟")[0]);
        if (!ev.has(signature)) ev.set(signature, []);
        ev.get(signature)!.push(`${label}[${stepId}]=${JSON.stringify(candidate)}`);
      }
    }
    return [req, ev, heads];
  }
  const [required, evidence, requiredHeads] = _obligations(authorSteps, "author_steps");
  if (adaptedRows.length && Array.isArray(authoredRows)) {
    const [authoredRequired, authoredEvidence, authoredHeads] = _obligations(authoredRows, "author_steps");
    const dropped: [string, number][] = [];
    for (const [head, count] of authoredHeads) {
      const missing = count - (requiredHeads.get(head) ?? 0);
      if (missing > 0) dropped.push([head, missing]);
    }
    for (const [head, missing] of dropped.sort((a, b) => a[0].localeCompare(b[0]))) {
      let restored = 0;
      for (const [signature, count] of authoredRequired) {
        if (signature.split("␟")[0] !== head || restored >= missing) continue;
        const take = Math.min(count, missing - restored);
        _counterAdd(required, signature, take);
        restored += take;
        if (!evidence.has(signature)) evidence.set(signature, []);
        evidence.get(signature)!.push(...(authoredEvidence.get(signature) ?? []).slice(0, take));
      }
      const sources = [...authoredEvidence.entries()]
        .filter(([signature]) => signature.split("␟")[0] === head)
        .flatMap(([, lines]) => lines)
        .join("; ");
      report.advise(gate, "adaptation_dropped_authored_command", `adapted_steps:${head}`, `the authored procedure resolves command head=${JSON.stringify(head)} ${authoredHeads.get(head)} time(s) but the adapted steps resolve it ${requiredHeads.get(head) ?? 0} time(s); the ${missing} missing occurrence(s) stay obligations as the author wrote them — adaptation may rewrite a command's arguments, never remove the command. Sources: ${sources}`, { head, authored: authoredHeads.get(head), adapted: requiredHeads.get(head) ?? 0, restored });
    }
  }
  const actual = new Map<string, number>();
  for (const ref of _ordered_apv_command_refs([...steps], init)) {
    const command = String(ref["command"] || "");
    const verdict = resolve(command);
    if (verdict["kind"] !== "hit") continue;
    _counterAdd(actual, _procedure_command_signature(vendor, command, verdict));
  }
  for (const [signature, needed] of [...required.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    const [head, objectId] = [signature.split("␟")[0], signature.split("␟").slice(1).join("␟")];
    if (objectId === _DESCRIPTIVE_FIRST_ARGUMENT) {
      const headTotal = [...actual.entries()].filter(([key]) => key.split("␟")[0] === head).reduce((sum, [, count]) => sum + count, 0);
      const othersRequired = [...required.entries()].filter(([key]) => key !== signature && key.split("␟")[0] === head).reduce((sum, [, count]) => sum + count, 0);
      const landed = headTotal - othersRequired;
      if (landed >= needed) {
        report.advise(gate, "authored_argument_descriptive", `author_steps:${head}:${_DESCRIPTIVE_FIRST_ARGUMENT}`, `the author wrote command head=${JSON.stringify(head)} followed by a descriptive condition instead of a CLI literal; the occurrence count was checked on the head only (${landed}/${needed}, after ${othersRequired} same-head literal obligation(s)) and the object identity behind that condition was not mechanically compared. Sources: ${(evidence.get(signature) ?? []).join("; ")}`, { head, landed, needed, same_head_literal_obligations: othersRequired, sources: [...(evidence.get(signature) ?? [])] });
        continue;
      }
      report.reject(gate, "authored_command_occurrence_missing", `author_steps:${head}:${_DESCRIPTIVE_FIRST_ARGUMENT}`, `the sealed author procedure contains ${needed} occurrence(s) of build-valid command head=${JSON.stringify(head)} whose first argument is a descriptive condition (not a CLI literal), but the final APV action stream leaves only ${landed} occurrence(s) of that head once the ${othersRequired} same-head literal obligation(s) are served. Realize the described condition with concrete arguments and land every authored occurrence before observing its result. Sources: ${(evidence.get(signature) ?? []).join("; ")}`);
      continue;
    }
    const landed = actual.get(signature) ?? 0;
    if (landed >= needed) {
      continue;
    }
    report.reject(gate, "authored_command_occurrence_missing", `author_steps:${head}:${objectId || "<no-first-arg>"}`, `the sealed author procedure contains ${needed} occurrence(s) of build-valid command head=${JSON.stringify(head)} for first object=${JSON.stringify(objectId)}, but the final APV action stream contains only ${landed}. A description saying the action happened is not execution evidence; land every authored occurrence before observing its result. Sources: ${(evidence.get(signature) ?? []).join("; ")}`);
  }
}

function _command_remainder_tokens(command: string, head: string): string[] {
  const { norm_command_tokens } = require("./vendor_stdlib");
  const tokens = [...norm_command_tokens(command)];
  const headTokens = [...norm_command_tokens(head)];
  if (JSON.stringify(tokens.slice(0, headTokens.length)) !== JSON.stringify(headTokens)) {
    return [];
  }
  return tokens.slice(headTokens.length).map((value: any) => String(value).trim().toLowerCase());
}

function _gate_https_certificate_lifecycle(steps: any[], init: string, report: _Report, opts: { device_build: string }): void {
  const gate = "https_certificate_lifecycle";
  report.ran(gate);
  const { parse_g_arguments } = require("./excel_contract");
  const { certified_ssl_release_fixture } = require("./excel_capability_samples");
  const { SSLLifecycleContractError, load_ssl_lifecycle_contract } = require("./ssl_lifecycle_contract");
  const { _SSL_ACTIVATE_FUNCTION, _SSL_IMPORT_FUNCTIONS, _ordered_apv_command_refs, _ssl_import_embeds_activation } = require("../ist_core/tools/device/emit_xlsx_tool");
  const httpsObservations = steps
    .map((step, index) => [index, step] as [number, any])
    .filter(([, step]) => _isMapping(step) && !String(step["E"] || "").trim().startsWith("APV") && String(step["G"] || "").toLowerCase().includes("https://"))
    .map(([index]) => index);
  if (!httpsObservations.length) {
    return;
  }
  let lifecycle: any;
  try {
    lifecycle = load_ssl_lifecycle_contract(String(opts.device_build || ""));
  } catch (exc: any) {
    if (exc instanceof SSLLifecycleContractError) {
      report.reject(gate, "https_lifecycle_contract_unavailable", "engine_context.ssl_lifecycle_contract", `this case carries a TLS client observation, but the engine-owned build-bound SSL lifecycle role map is unavailable or stale: ${exc}. This is not repairable by changing case commands; refresh and certify the engine-only lifecycle evidence for the current build.`);
      return;
    }
    throw exc;
  }
  const requiredVirtualHeads = new Set<string>(lifecycle["required_virtual_heads"]);
  const sslHostCreateHead = String(lifecycle["ssl_host_create_head"]);
  const sslHostStartHead = String(lifecycle["ssl_host_start_head"]);
  const sslHostCleanupHead = String(lifecycle["ssl_host_cleanup_head"]);
  const lifecycleHeads = [...requiredVirtualHeads, sslHostCreateHead, sslHostStartHead, sslHostCleanupHead].sort((a, b) => b.split(" ").length - a.split(" ").length || a.localeCompare(b));
  const refs: Record<string, any>[] = [];
  for (const ref of _ordered_apv_command_refs([...steps], init)) {
    const command = String(ref["command"] || "");
    const head = lifecycleHeads.find((candidate) => _command_remainder_tokens(command, candidate).length) || "";
    if (!head) continue;
    const stepIndex = Number(ref["step_index"] ?? -1);
    let host = "APV_0";
    if (stepIndex >= 0 && stepIndex < steps.length && _isMapping(steps[stepIndex])) {
      host = String(steps[stepIndex]["E"] || "").trim();
    }
    refs.push({ command, head, args: _command_remainder_tokens(command, head), step_index: stepIndex, host });
  }
  const services = refs.filter((ref) => requiredVirtualHeads.has(ref["head"]) && ref["args"].length);
  if (!services.length) {
    return;
  }
  const keyFunctions = new Set(Object.entries(_SSL_IMPORT_FUNCTIONS).filter(([key]) => key.split("|")[0] === "key" || JSON.parse(`[${key}]`)[0] === "key").map(([, name]) => String(name)));
  const certFunctions = new Set(Object.entries(_SSL_IMPORT_FUNCTIONS).filter(([key]) => {
    try { return JSON.parse(`[${key}]`)[0] === "cert"; } catch { return false; }
  }).map(([, name]) => String(name)));

  function _method_vhost(step: Record<string, any>): string {
    const method = String(step["F"] || "").trim();
    let parsed: [any[], Record<string, any>];
    try {
      parsed = parse_g_arguments(String(step["G"] || ""), method);
    } catch {
      return "";
    }
    const [args, kwargs] = parsed;
    let value = kwargs["vhost"];
    if ((value === undefined || value === null) && args.length) {
      value = args[0];
    }
    return String(value || "").trim().toLowerCase();
  }

  function _method_file(step: Record<string, any>, names: Set<string>): string {
    const method = String(step["F"] || "").trim();
    let parsed: [any[], Record<string, any>];
    try {
      parsed = parse_g_arguments(String(step["G"] || ""), method);
    } catch {
      return "";
    }
    const [args, kwargs] = parsed;
    for (const name of [...names].sort()) {
      if (kwargs[name] !== undefined && kwargs[name] !== null) {
        return String(kwargs[name]).trim();
      }
    }
    return args.length > 1 ? String(args[1]).trim() : "";
  }

  for (const service of services) {
    const virtualService = String(service["args"][0]).toLowerCase();
    const host = String(service["host"]);
    const serviceIndex = Number(service["step_index"]);
    const nextServiceIndex = Math.min(...services.filter((other) => String(other["host"]) === host && String(other["args"][0]).toLowerCase() === virtualService && Number(other["step_index"]) > serviceIndex).map((other) => Number(other["step_index"])), steps.length);
    const serviceObservations = httpsObservations.filter((index) => serviceIndex < index && index < nextServiceIndex);
    if (!serviceObservations.length) {
      continue;
    }
    const firstObservation = Math.min(...serviceObservations);
    const lastObservation = Math.max(...serviceObservations);
    const sslHosts = refs.filter((ref) => ref["head"] === sslHostCreateHead && ref["host"] === host && ref["args"].length >= 2 && String(ref["args"][1]).toLowerCase() === virtualService && serviceIndex < Number(ref["step_index"]) && Number(ref["step_index"]) < firstObservation);
    if (!sslHosts.length) {
      report.reject(gate, "https_certificate_setup_missing", `steps:${host}:${virtualService}`, "a build-valid HTTPS-list virtual service is exercised by an HTTPS observation, but no SSL_CERT_LOAD setup is bound to that exact virtual service after its creation and before the observation. Insert the engine-owned SSL_CERT_LOAD block in that lifecycle position and read its current fields from blocks_schema.json; do not hand-author or guess certificate-import commands.");
      continue;
    }
    const sslHost = sslHosts.reduce((best, item) => (Number(item["step_index"]) > Number(best["step_index"]) ? item : best));
    const vhost = String(sslHost["args"][0]).toLowerCase();
    const sslHostIndex = Number(sslHost["step_index"]);
    const methodSteps = steps
      .map((step, index) => [index, step] as [number, any])
      .filter(([index, step]) => sslHostIndex < index && index < firstObservation && _isMapping(step) && String(step["E"] || "").trim() === host && _method_vhost(step) === vhost);
    const keyIndices = methodSteps.filter(([, step]) => keyFunctions.has(String(step["F"] || "").trim())).map(([index]) => index);
    const certIndices = methodSteps.filter(([, step]) => certFunctions.has(String(step["F"] || "").trim())).map(([index]) => index);
    const activeIndices = methodSteps.filter(([, step]) => String(step["F"] || "").trim() === _SSL_ACTIVATE_FUNCTION).map(([index]) => index);
    const certMethods = methodSteps.filter(([, step]) => certFunctions.has(String(step["F"] || "").trim())).map(([, step]) => String(step["F"] || "").trim());
    let embeddedActivation: boolean;
    try {
      embeddedActivation = Boolean(certMethods.length) && certMethods.every((method) => _ssl_import_embeds_activation(method));
    } catch (exc: any) {
      report.reject(gate, "https_certificate_activation_contract_unavailable", `steps:${host}:${virtualService}`, `the engine cannot derive whether the selected certificate-import helper activates from the current framework source: ${exc}. This is an engine projection fault, not a case command to guess around.`);
      continue;
    }
    const activationClosed = embeddedActivation || Boolean(certIndices.length && activeIndices.length && Math.max(...certIndices) < Math.max(...activeIndices));
    const orderedSetup = Boolean(keyIndices.length && certIndices.length && Math.min(...keyIndices) < Math.max(...certIndices) && activationClosed);
    if (!orderedSetup) {
      report.reject(gate, "https_certificate_setup_incomplete", `steps:${host}:${virtualService}`, "the SSL host bound to the exercised HTTPS-list service does not carry a same-host, same-vhost key import -> certificate import -> activation sequence before the HTTPS observation. Activation may be embedded in the framework certificate-import helper or emitted as activeCert when the helper lacks it. Use SSL_CERT_LOAD so the engine derives that choice from the current mirror; prose and nearby unrelated imports are not setup evidence.");
      continue;
    }
    if (embeddedActivation && activeIndices.length) {
      report.reject(gate, "https_certificate_redundant_activation", `steps:${host}:${virtualService}`, "the selected certificate-import helper already activates according to the current mirror, but the case invokes activeCert again. The second call can return an already-active prompt shape and turn its confirmation into a standalone invalid command. Re-lower SSL_CERT_LOAD; do not append another activation step.");
      continue;
    }
    const activationAnchor = embeddedActivation ? Math.max(...certIndices) : Math.max(...activeIndices);
    const startOk = refs.some((ref) => ref["head"] === sslHostStartHead && ref["host"] === host && ref["args"].length && String(ref["args"][0]).toLowerCase() === vhost && activationAnchor < Number(ref["step_index"]) && Number(ref["step_index"]) < firstObservation);
    if (!startOk) {
      report.reject(gate, "https_certificate_start_missing", `steps:${host}:${virtualService}`, "the certificate is activated, but the same SSL host is not started before the HTTPS business observation. Re-lower SSL_CERT_LOAD so the engine inserts the build-bound lifecycle transition from its sealed role map; do not guess a product command in free text.");
      continue;
    }
    const fixturePaths = certified_ssl_release_fixture()["resolved_paths"];
    const resolvedKeys = methodSteps.filter(([, step]) => keyFunctions.has(String(step["F"] || "").trim())).map(([, step]) => _method_file(step, new Set(["keyfile", "keyFile"])));
    const resolvedCerts = methodSteps.filter(([, step]) => certFunctions.has(String(step["F"] || "").trim())).map(([, step]) => _method_file(step, new Set(["certfile", "certFile"])));
    if (JSON.stringify(resolvedKeys) !== JSON.stringify([...fixturePaths["keys"]]) || JSON.stringify(resolvedCerts) !== JSON.stringify([...fixturePaths["certs"]])) {
      report.reject(gate, "https_certificate_material_unverified", `steps:${host}:${virtualService}`, "the key/certificate paths used by the HTTPS-list lifecycle are not the material signed by the current same-source release replay. Repository-looking paths and filenames selected by the model are not device facts. Submit SSL_CERT_LOAD with all material fields omitted so the engine binds the certified default projected in blocks_schema.json.");
      continue;
    }
    let cleanupOk = false;
    for (const ref of refs) {
      if (!(ref["head"] === sslHostCleanupHead && ref["host"] === host && ref["args"].length && String(ref["args"][0]).toLowerCase() === vhost && Number(ref["step_index"]) > lastObservation)) {
        continue;
      }
      const index = Number(ref["step_index"]);
      if (index + 1 >= steps.length || !_isMapping(steps[index + 1])) {
        continue;
      }
      const confirmation = steps[index + 1];
      if (String(confirmation["E"] || "").trim() === host && String(confirmation["F"] || "").trim() === "cmd_config" && String(confirmation["G"] || "").trim().toUpperCase() === "YES") {
        cleanupOk = true;
        break;
      }
    }
    if (!cleanupOk) {
      report.reject(gate, "https_certificate_teardown_missing", `steps:${host}:${virtualService}`, "the certified SSL host remains unpaired, or its teardown occurs before the last HTTPS observation. Keep SSL_CERT_LOAD as a standard-library block: the engine defers its certified object-scoped teardown pair until after the final signed business assertion and before trailing dependent-object teardown.");
    }
  }
}

function _base_claim_kinds(contract: Record<string, any>): Record<string, string> {
  const { claim_authority_source } = require("./provenance_ir");
  const out: Record<string, string> = {};
  for (const item of contract["expectations"] || []) {
    if (!_isMapping(item)) continue;
    const author = item["author_claim"];
    const defect = item["defect_spec_claim"];
    const assertion = item["assertion"];
    let expectationId = "";
    let kind = "";
    if (_isMapping(author)) {
      expectationId = String(author["expectation_id"] || "");
      kind = claim_authority_source("author");
    } else if (_isMapping(defect)) {
      expectationId = String(defect["expectation_id"] || "");
      kind = claim_authority_source("defect_spec");
    } else if (_isMapping(assertion)) {
      expectationId = String(assertion["expectation_id"] || "");
      const source = assertion["source"];
      kind = claim_authority_source(_isMapping(source) ? String(source["kind"] || "") : "");
    } else {
      continue;
    }
    if (expectationId && kind) {
      out[expectationId] = kind;
    }
  }
  return out;
}

function _gate_consistency_contract(body: Record<string, any>, contract: Record<string, any>, contract_sha256: string, consistency_contract: Record<string, any> | null, consistency_contract_sha256: string, consistency_required: boolean, report: _Report): void {
  const gate = "consistency_contract";
  report.ran(gate);
  const binding = body["binding"];
  const declared = _isMapping(binding) ? binding["consistency_contract_sha256"] : null;
  if (!consistency_required) {
    if (declared !== null && declared !== undefined || consistency_contract !== null || consistency_contract_sha256) {
      report.reject(gate, "consistency_not_applicable_binding_present", "binding.consistency_contract_sha256", "the engine stamped consistency as not applicable; the mechanical body must carry null and cannot self-issue an overlay");
    }
    return;
  }
  if (!_isMapping(consistency_contract)) {
    report.reject(gate, "consistency_contract_absent", "binding.consistency_contract_sha256", "the engine-required linked consistency contract is unavailable");
    return;
  }
  if (String(declared || "") !== consistency_contract_sha256 || !/^[0-9a-f]{64}$/.test(consistency_contract_sha256)) {
    report.reject(gate, "consistency_contract_identity_drift", "binding.consistency_contract_sha256", "the mechanical binding does not equal the verified linked overlay SHA");
    return;
  }
  if (!accepts_schema(consistency_contract["schema"], "ist.consistency-contract") || consistency_contract["autoid"] !== body["autoid"] || consistency_contract["base_contract_sha256"] !== contract_sha256) {
    report.reject(gate, "consistency_contract_base_drift", "binding.consistency_contract_sha256", "the linked overlay does not bind this case and frozen U1 contract");
    return;
  }
  const expectedKinds = _base_claim_kinds(contract);
  const bindings = ((body["expectation_binding"] || []) as any[]).filter((item) => _isMapping(item));
  bindings.forEach((item, index) => {
    const expectationId = String(item["expectation_id"] || "");
    const expectedKind = expectedKinds[expectationId];
    if (expectedKind && String(item["claim_kind"] || "") !== expectedKind) {
      report.reject(gate, "consistency_endorsement_claim_kind_upgrade", `expectation_binding[${index}].claim_kind`, `a linked Spec+Author endorsement is additive; it cannot rewrite the base contract claim kind ${expectedKind}`);
    }
  });
  const endorsement = consistency_contract["spec_endorsement"];
  const scope = _isMapping(endorsement) ? endorsement["scope"] : null;
  if (_isMapping(scope) && scope["kind"] === "expectation") {
    const expectationId = String(scope["expectation_id"] || "");
    if (Object.keys(expectedKinds).filter((k) => k === expectationId).length !== SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY || bindings.filter((item) => String(item["expectation_id"] || "") === expectationId).length !== SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY) {
      report.reject(gate, "spec_endorsement_expectation_not_bound", "spec_endorsement.scope.expectation_id", "expectation-scoped endorsement must name one unique base expectation and one unique mechanical assertion binding");
    }
  }
}

function _init_g(init_commands: string[]): string {
  const joined = init_commands.map((item) => String(item)).join("\n").trim();
  if (joined) {
    return joined;
  }
  const { get_config } = require("./config");
  return get_config().default_init_g();
}

function _gate_blocks_expansion(body: Record<string, any>, report: _Report): [Record<string, any>[], Record<string, any>[]] | null {
  const gate = "blocks_expansion";
  report.ran(gate);
  const { expand_blocks } = require("./blocks");
  const blocks = JSON.parse(JSON.stringify(body["blocks"]));
  const [steps, provenanceSteps, error] = expand_blocks(blocks);
  if (error || steps === null || provenanceSteps === null) {
    report.reject(gate, "blocks_invalid", "blocks", String(error));
    return null;
  }
  return [steps, provenanceSteps];
}

function _gate_derived_assertion_expansion(steps: Record<string, any>[], provenanceSteps: Record<string, any>[], report: _Report): [Record<string, any>[], Record<string, any>[]] | null {
  const { lower_derived_assertions } = require("./blocks");
  const [expanded, expandedProvenance, error] = lower_derived_assertions(steps, provenanceSteps);
  if (error || expanded === null || expandedProvenance === null) {
    report.reject("blocks_expansion", "blocks_invalid", "blocks", String(error || "derived assertion expansion returned no steps"));
    return null;
  }
  return [expanded, expandedProvenance];
}

function _expectation_ids_consuming_step(steps: Record<string, any>[], provenanceSteps: Record<string, any>[], stepIndex: number): string[] {
  if (stepIndex < 0 || stepIndex >= steps.length) {
    return [];
  }
  const identities = new Set<string>();
  for (let index = stepIndex + 1; index < steps.length; index++) {
    if (String(steps[index]["E"] || "").trim() !== _CHECK_POINT_OBJECT) {
      break;
    }
    if (index >= provenanceSteps.length) {
      continue;
    }
    const expectationId = String(provenanceSteps[index]["expectation_id"] || "").trim();
    if (expectationId) {
      identities.add(expectationId);
    }
  }
  return [...identities].sort();
}

function _step_locus(stepIndex: number, offset: number): string {
  if (stepIndex < 0) {
    return "case";
  }
  if (offset && stepIndex === 0) {
    return "init_commands";
  }
  return `steps[${stepIndex - offset}]`;
}

function _gate_structural_lint(steps: Record<string, any>[], provenanceSteps: Record<string, any>[], init: string, report: _Report, opts: { device_build: string; author_ip_literals?: string[] | null }): void {
  const gate = "structural_lint";
  report.ran(gate);
  report.ran("command_contract");
  const boundBuild = String(opts.device_build || "").trim();
  if (!boundBuild) {
    report.reject(gate, "capability_build_unbound", "engine_context.capability_build", "the engine-owned capability build is missing; the submission rules refuse to fall back to the process-wide active command-tree generation");
    report.reject_named_by("command_contract", gate);
    return;
  }
  const { lint_draft } = require("../ist_core/tools/device/structural_gate");
  let linted = [...steps];
  if (init.trim()) {
    linted = [{ D: "初始化配置", E: "APV_0", F: "cmds_config", G: init }, ...linted];
  }
  const authorDriverHits: Record<string, any>[] = [];
  const result = lint_draft(linted, { init: "", final: true, device_build: boundBuild, author_ip_literals: opts.author_ip_literals ?? null, author_driver_hits: authorDriverHits });
  const offset = init.trim() ? 1 : 0;
  if (authorDriverHits.length) {
    const targets = [...new Set(authorDriverHits.map((item) => String(item["target"] || "")))].sort();
    report.advise(gate, "author_sourced_driver_target", "source_case_slice", "The sealed Author case text names a query target that no test-driver on this bed has a declared path to. This is an execution-environment disclosure, not a case rejection: authoring continues, the limitation is reported with the delivery, and no device actual signs expected.", { author_sourced_targets: targets.filter((value) => value), author_sourced_driver_hits: authorDriverHits.map((item) => ({ ...item, locus: _step_locus(Number(item["step_index"] ?? -1), offset) })) });
  }
  const { COMMAND_NOT_IN_TREE_CODE, COMMAND_PARAMETER_CONTRACT_CODE } = require("../ist_core/tools/device/emit_xlsx_tool");
  const commandCodes = new Set([COMMAND_NOT_IN_TREE_CODE, COMMAND_PARAMETER_CONTRACT_CODE]);
  for (const violation of result.violations) {
    const findingGate = commandCodes.has(violation.code) ? "command_contract" : gate;
    const expandedIndex = violation.step_index - offset;
    const expectationIds = violation.code === COMMAND_NOT_IN_TREE_CODE ? _expectation_ids_consuming_step(steps, provenanceSteps, expandedIndex) : [];
    report.reject(findingGate, violation.code, _step_locus(violation.step_index, offset), violation.detail, { expectation_ids: expectationIds });
  }
  for (const advisory of result.advisories) {
    report.advise(gate, advisory.code, _step_locus(advisory.step_index, offset), advisory.detail);
  }
  for (const disabled of result.disabled) {
    report.advise(gate, `gate_disabled:${disabled.code}`, _step_locus(disabled.step_index, offset), disabled.detail);
  }
}

function _gate_unreachable_ips(autoid: string, steps: Record<string, any>[], init: string, report: _Report, opts: { source_case_slice?: Record<string, any> | null; source_case_slice_sha256?: string } = {}): void {
  const gate = "unreachable_ips";
  report.ran(gate);
  const { _gate_unreachable_ips: unreachable, _unreachable_ip_admission } = require("../ist_core/tools/device/emit_xlsx_tool");
  const slice = _isMapping(opts.source_case_slice) ? { ...opts.source_case_slice } : null;
  const admission = _unreachable_ip_admission(autoid, [...steps], { init, source_case_slice: slice, source_case_slice_sha256: opts.source_case_slice_sha256 ?? "" });
  const message = unreachable(autoid, [...steps], { init, source_case_slice: slice, source_case_slice_sha256: opts.source_case_slice_sha256 ?? "" });
  if (message) {
    report.reject(gate, "environment_unreachable_ip", "steps", message);
  }
  const authorValues = [...(admission["author_unreachable_values"] || [])];
  if (authorValues.length) {
    report.advise(gate, "author_sourced_unreachable_setup", "source_case_slice", "The sealed Author case text contains environment-unreachable setup value(s). This is an execution-environment disclosure, not a case rejection: authoring continues and setup binding follows the contract value_grounding channel; no device actual signs expected.", { author_unreachable_values: authorValues, compiled_unreachable_values: [...(admission["compiled_unreachable_values"] || [])] });
  }
}

function _negative_probe_destinations(command: string): string[] {
  const { _extract_query_destinations } = require("../ist_core/tools/device/structural_gate");
  const out: string[] = [..._extract_query_destinations(command)];
  const tokens = command.split(/\s+/).filter((t) => t);
  for (const token of tokens) {
    let candidate = token.trim().replace(/^\[|\]$/g, "");
    const colonCount = (candidate.match(/:/g) || []).length;
    if (colonCount === 1 && candidate.includes(".")) {
      const splitAt = candidate.lastIndexOf(":");
      const host = candidate.slice(0, splitAt);
      const port = candidate.slice(splitAt + 1);
      if (/^\d+$/.test(port)) {
        candidate = host;
      }
    }
    if (!_isIpLiteral(candidate.split("%")[0])) {
      continue;
    }
    if (!out.includes(candidate)) {
      out.push(candidate);
    }
  }
  return out;
}

function _gate_negative_probe_path(blocks: Record<string, any>[], report: _Report): void {
  const gate = "negative_probe_path";
  report.ran(gate);
  const negatives = blocks
    .map((block, index) => [index, block] as [number, any])
    .filter(([, block]) => _isMapping(block) && String(block["kind"] || "").trim().toUpperCase() === "OBSERVE_EXIT" && String(block["expect"] || "").trim().toLowerCase() === "failure");
  if (!negatives.length) {
    return;
  }
  const { require_env_facts } = require("../ist_core/tools/_shared/env_facts");
  const facts = require_env_facts();
  for (const [index, block] of negatives) {
    const command = String(block["cmd"] || "");
    const host = String(block["host"] || "");
    const destinations = _negative_probe_destinations(command);
    if (!destinations.length) {
      report.reject(gate, "negative_probe_target_not_ip_literal", `blocks[${index}]`, "expect=failure asserts that the target did not answer, so the probe target must be an IP literal; a host name would let a name-resolution failure satisfy the assertion without the device being involved");
      continue;
    }
    for (const dest of destinations) {
      const verdict = facts.executor_path_verdict(host, dest);
      if (verdict === null || verdict === undefined) {
        continue;
      }
      report.reject(gate, "negative_probe_path_undeclared", `blocks[${index}]`, `expect=failure from ${JSON.stringify(host)} to ${dest} cannot be attributed to the device: the testbed topology declares no path from this executor to that address, so a transport failure could come from the executor's own routing. Probe from an executor with a declared path (reachable drivers: ${JSON.stringify(verdict["reachable_drivers"] || [])}).`);
    }
  }
}

function _author_ip_literals_for_submission(autoid: string, steps: Record<string, any>[], init: string, opts: { source_case_slice: Record<string, any> | null; source_case_slice_sha256: string }): string[] {
  const { _unreachable_ip_admission } = require("../ist_core/tools/device/emit_xlsx_tool");
  const admission = _unreachable_ip_admission(autoid, [...steps], { init, source_case_slice: _isMapping(opts.source_case_slice) ? { ...opts.source_case_slice } : null, source_case_slice_sha256: opts.source_case_slice_sha256 });
  return [...(admission["author_ip_literals"] || [])];
}

function _gate_trigger_reachability(autoid: string, steps: Record<string, any>[], init: string, blocks: Record<string, any>[], report: _Report, opts: { author_ip_literals?: string[] | null } = {}): void {
  const gate = "trigger_reachability";
  report.ran(gate);
  const { require_env_facts } = require("../ist_core/tools/_shared/env_facts");
  require_env_facts();
  const { _trigger_reachability_findings } = require("../ist_core/tools/device/emit_xlsx_tool");
  const findings = _trigger_reachability_findings(autoid, [...steps], { init, blocks: [...blocks], author_ip_literals: opts.author_ip_literals ?? null });
  const message = findings["message"];
  if (message) {
    report.reject(gate, "trigger_reachability_invalid", "steps", message);
  }
  const authorTargets = [...(findings["author_sourced_targets"] || [])];
  if (authorTargets.length) {
    report.advise(gate, "author_sourced_trigger_target", "source_case_slice", "The sealed Author case text names a listener/trigger target that sits in an APV interface segment no trigger host on this bed can reach, or that is not a registered listener/backend of this bed. This is an execution-environment disclosure, not a case rejection: authoring continues, the limitation is reported with the delivery, and no device actual signs expected.", { author_sourced_targets: authorTargets, author_blind_hits: [...(findings["author_blind_hits"] || [])], author_bad_targets: [...(findings["author_bad_targets"] || [])] });
  }
}

function _interaction_block_expectation_ids(block: Record<string, any>, kind: string): string[] {
  if (kind === "OBSERVE_ASSERT") {
    return [...new Set(((block["asserts"] || []) as any[]).filter((item) => _isMapping(item) && String(item["expectation_id"] || "")).map((item) => String(item["expectation_id"] || "")))].sort();
  }
  const single = String(block["expectation_id"] || "");
  return single ? [single] : [];
}

function _block_kind_label(block: any): string {
  if (!_isMapping(block)) {
    return "no block";
  }
  return String(block["kind"] || "").trim().toUpperCase() || "no block";
}

function _is_config_establishing_block(block: any, dutHosts: string[]): boolean {
  if (!_isMapping(block)) {
    return false;
  }
  const kind = String(block["kind"] || "").trim().toUpperCase();
  if (kind === "CONFIG") {
    return true;
  }
  if (kind !== "STEP") {
    return false;
  }
  return dutHosts.includes(String(block["E"] || "").trim()) && _CONFIG_STEP_FUNCTIONS.has(String(block["F"] || "").trim());
}

function _answerer_shape_error_local(answerer: any): string | null {
  if (answerer === null || answerer === undefined) {
    return null;
  }
  if (typeof answerer !== "object" || Array.isArray(answerer)) {
    return "answerer must be an object {kind, ref|note} naming who answers this observation";
  }
  const extra = Object.keys(answerer).filter((k) => !["kind", "ref", "note"].includes(k)).sort();
  if (extra.length) {
    return `answerer has unsupported field(s): ${extra.join(", ")} (closed set: kind, ref, note)`;
  }
  const aKind = String(answerer["kind"] || "").trim();
  if (!(_ANSWERER_KINDS as readonly string[]).includes(aKind)) {
    return `answerer.kind must be one of ${_ANSWERER_KINDS.join(", ")}; got ${JSON.stringify(aKind)}`;
  }
  if (aKind === "device" || aKind === "fixture") {
    const ref = answerer["ref"];
    if (typeof ref !== "number" || !Number.isInteger(ref) || ref < 0) {
      return `answerer.ref for kind=${aKind} must be a blocks[] index (non-negative integer) of the block that establishes the answerer`;
    }
  } else if (aKind === "bed_service") {
    const ref = answerer["ref"];
    if (typeof ref !== "string" || !ref.trim()) {
      return "answerer.ref for kind=bed_service must be a device name from the bed topology (non-empty text)";
    }
  } else {
    const note = answerer["note"];
    if (typeof note !== "string" || !note.trim()) {
      return "answerer.note for kind=undetermined must be one line naming what no source states about who answers";
    }
  }
  return null;
}

function _gate_answerer_statement(body: Record<string, any>, report: _Report): void {
  const gate = "answerer_statement";
  report.ran(gate);
  const blocks = body["blocks"];
  if (!Array.isArray(blocks)) {
    return;
  }
  const { require_env_facts } = require("../ist_core/tools/_shared/env_facts");
  const facts = require_env_facts();
  const topologyNames = new Set((facts.devices as any[]).map((dev) => String(dev["name"] || "").trim().toLowerCase()).filter((name) => name));
  blocks.forEach((block: any, index: number) => {
    if (!_isMapping(block)) {
      return;
    }
    const kind = String(block["kind"] || "").trim().toUpperCase();
    if (kind !== "OBSERVE_ASSERT" && kind !== "OBSERVE_EXIT") {
      return;
    }
    const host = String(block["host"] || "").trim();
    if (_DUT_HOSTS.includes(host)) {
      return;
    }
    const locus = `blocks[${index}].answerer`;
    const expectationIds = _interaction_block_expectation_ids(block, kind);
    const answerer = block["answerer"];
    if (answerer === null || answerer === undefined) {
      report.reject(gate, "answerer_statement_missing", locus, `this observation runs on host ${JSON.stringify(host)}, which is outside the two devices under test, so it drives traffic at a peer instead of reading device state — and the block names no answerer. A request sent with nothing behind it times out on device and burns a device round (real open-chain cases failed four times this way). Declare who answers: answerer {kind: "device"|"fixture", ref: <blocks[] index of the block that establishes the answerer>} or {kind: "bed_service", ref: <device name in the bed topology>}. When no source says who answers, write {kind: "undetermined", note: <one user-facing Chinese line>} and the submit boundary routes a typed user-decision claim instead of rejecting or sealing.`, { expectation_ids: expectationIds });
      return;
    }
    if (_answerer_shape_error_local(answerer) !== null) {
      report.reject_named_by(gate, "blocks_expansion");
      return;
    }
    const aKind = String(answerer["kind"] || "").trim();
    if (!(_ANSWERER_KINDS as readonly string[]).includes(aKind)) {
      report.reject_named_by(gate, "blocks_expansion");
      return;
    }
    const ref = answerer["ref"];
    if (aKind === "undetermined") {
      report.reject(gate, "answerer_undetermined_unrouted", locus, "answerer.kind=undetermined is routed by submit_mechanical_case into a typed answerer_undetermined user-decision claim before the submission rules run; a sealed mechanical case can never carry an undetermined answerer. Route it through the submit boundary instead of sealing.", { expectation_ids: expectationIds });
    } else if (aKind === "device") {
      const target = typeof ref === "number" && ref >= 0 && ref < blocks.length ? blocks[ref] : null;
      if (!_is_config_establishing_block(target, _DUT_HOSTS)) {
        report.reject(gate, "answerer_ref_unresolved", locus, `answerer.ref=${ref} must be the blocks[] index of the block that establishes the answering configuration on a device under test (a CONFIG combinator, or an accounted generic STEP writing device configuration); it resolves to ${_block_kind_label(target)}.`, { expectation_ids: expectationIds });
      }
    } else if (aKind === "fixture") {
      if (!(typeof ref === "number" && ref >= 0 && ref < blocks.length) || !_isMapping(blocks[ref])) {
        report.reject(gate, "answerer_ref_unresolved", locus, `answerer.ref=${ref} must be the blocks[] index of the block that establishes the in-case fixture answering this observation; no such block exists in this submission.`, { expectation_ids: expectationIds });
      }
    } else {
      const name = String(ref || "").trim().toLowerCase();
      if (!topologyNames.has(name)) {
        report.reject(gate, "answerer_ref_unresolved", locus, `answerer.ref ${JSON.stringify(ref)} is not a device name in the bed topology; kind=bed_service names a service the testbed itself provides, so the name must come from the topology fact source.`, { expectation_ids: expectationIds });
      }
    }
  });
}

function _gate_paired_teardown(steps: Record<string, any>[], init: string, report: _Report, opts: { device_build: string }): void {
  const gate = "paired_teardown";
  report.ran(gate);
  const { TauAtlasUnavailableError, check_tau_coverage, inverse_line } = require("./tau_coverage");
  let result: any;
  try {
    result = check_tau_coverage([...steps], init, { device_build: String(opts.device_build || "") });
  } catch (exc: any) {
    if (exc instanceof TauAtlasUnavailableError) {
      report.reject(gate, "tau_atlas_unavailable", "engine_context.device_build", `the engine-owned build-bound teardown atlas is unavailable: ${exc}. This is an engine projection fault, not a command to weaken or rewrite the case; finish with that stable error code instead of retrying.`);
      return;
    }
    report.reject(gate, "paired_teardown_uncomputable", "case", `the deterministic teardown coverage rule could not produce a verdict (${exc?.constructor?.name ?? "Error"}); sealing is blocked as an engine fault`);
    return;
  }
  if (result.residual_config) {
    report.advise(gate, "residual_config_disclosed", "blocks", `${result.residual_config.length} configuration write(s) are classified as residual-only by the bound atlas; emit will persist the disclosure`);
  }
  if (result.ok) {
    return;
  }
  const missingLines = result.missing.map((item: any) => `- ${JSON.stringify(item["cmd"])}: ${inverse_line(item)}`);
  report.reject(gate, "missing_teardown", "blocks", "the build-bound teardown atlas proves that this draft creates configuration outside framework C1 cleanup but carries no matching object-scoped restore after its assertions:\n" + missingLines.join("\n") + "\nAdd the atlas-backed object-scoped inverse steps in reverse order after the assertions. Where the atlas exposes only a module-wide reset or no inverse, do not guess or use a wider clear: choose an equivalent construction with a representable object-scoped teardown, or report the mechanical-language gap explicitly.");
}

function _gate_provenance_receipts(autoid: string, steps: Record<string, any>[], provenanceSteps: Record<string, any>[], report: _Report, outputsRoot: string | null): any {
  const gate = "provenance_receipts";
  report.ran(gate);
  const { CaseProvenance, backfill_efg, check_runtime_consistency, check_source_locators, compile_expect_authority, known_provenance_facts } = require("./provenance_ir");
  const caseProv = CaseProvenance.from_dict({ autoid, steps: JSON.parse(JSON.stringify([...provenanceSteps])) });
  if (!backfill_efg(caseProv, [...steps])) {
    report.reject(gate, "provenance_step_count_mismatch", "provenance", `provenance carries ${caseProv.steps.length} entries for ${steps.length} expanded steps; the expansion pairs them positionally`);
    return null;
  }
  const problems = [...check_source_locators(caseProv, { outputs_root: outputsRoot }), ...check_runtime_consistency(caseProv), ...compile_expect_authority(caseProv)];
  let guidance = "";
  if (problems.length) {
    const root = outputsRoot !== null ? String(outputsRoot) : "workspace/outputs";
    guidance = known_provenance_facts(autoid, { outputs_root: root }).join("\n");
  }
  problems.forEach((problem: string, index: number) => {
    const detail = problem + (index === 0 && guidance ? "\n" + guidance : "");
    report.reject(gate, "provenance_source_unresolved", "provenance", detail);
  });
  return problems.length ? null : caseProv;
}

function _contract_claim_maps(contract: Record<string, any>, report: _Report): [Record<string, any>, Record<string, any>, Record<string, any>, Record<string, Record<string, any>>] | null {
  const gate = "expectation_bijection";
  const { normalize_contract } = require("./contract_entry");
  const { author_fixture_policies_from_contract } = require("../ist_core/compile_engine/authority_reconcile");
  let normalized: Record<string, any>;
  let fixturePolicies: Record<string, Record<string, any>>;
  try {
    normalized = normalize_contract({ ...contract }, String(contract["autoid"] || ""));
    fixturePolicies = author_fixture_policies_from_contract(normalized);
  } catch (exc: any) {
    report.reject(gate, "contract_unreadable", "contract", `${exc?.constructor?.name ?? "Error"}: ${exc?.message ?? exc}`);
    return null;
  }
  const maps: Record<string, any>[] = [{}, {}, {}];
  const fields = ["assertion", "author_claim", "defect_spec_claim"];
  (normalized["expectations"] || []).forEach((item: any, index: number) => {
    maps.forEach((bucket, bucketIndex) => {
      const claim = _isMapping(item) ? item[fields[bucketIndex]] : null;
      if (!_isMapping(claim)) {
        return;
      }
      const expectationId = String(claim["expectation_id"] || "").trim();
      if (!expectationId) {
        report.reject(gate, "contract_identity_incomplete", `contract.expectations[${index}].${fields[bucketIndex]}`, "the contract card minted no expectation_id for this entry");
        return;
      }
      if (maps.some((other) => expectationId in other)) {
        report.reject(gate, "contract_identity_duplicated", `contract.expectations[${index}].${fields[bucketIndex]}`, `expectation_id ${JSON.stringify(expectationId)} occurs more than once`);
        return;
      }
      bucket[expectationId] = { ...claim };
    });
  });
  return report.rejected(gate) ? null : [maps[0], maps[1], maps[2], fixturePolicies];
}

function _product_assertions(caseProv: any): any[] {
  const { product_assertion_steps } = require("../ist_core/compile_engine/authority_reconcile");
  return product_assertion_steps(caseProv.steps, { mutation_receipt: null });
}

function _gate_expectation_bijection(body: Record<string, any>, contract: Record<string, any>, contract_sha256: string, finalSteps: any[], allSteps: any[], report: _Report): void {
  const gate = "expectation_bijection";
  report.ran(gate);
  const autoid = String(body["autoid"] || "");
  const declared = String((_isMapping(body["binding"]) ? body["binding"] : {})["contract_sha256"] || "");
  if (declared !== contract_sha256) {
    report.reject(gate, "contract_identity_drift", "binding.contract_sha256", `declares ${declared}, the frozen contract card hashes to ${contract_sha256}`);
    return;
  }
  if (String(contract["autoid"] || "") !== autoid) {
    report.reject(gate, "contract_autoid_mismatch", "binding.contract_sha256", `contract card is for autoid ${JSON.stringify(contract["autoid"])}, this case is ${JSON.stringify(autoid)}`);
    return;
  }
  const maps = _contract_claim_maps(contract, report);
  if (maps === null) {
    return;
  }
  const [expectations, authorClaims, defectClaims, fixturePolicies] = maps;
  const { check_expectation_assertion_bijection } = require("../ist_core/compile_engine/authority_reconcile");
  const error = check_expectation_assertion_bijection({ autoid, final_steps: [...finalSteps], all_steps: [...allSteps], stamped_expectations: expectations, stamped_author_claims: authorClaims, stamped_defect_spec_claims: defectClaims, stamped_author_fixture_policies: fixturePolicies });
  if (error) {
    report.reject(gate, "expectation_bijection_failed", "blocks", error);
  }
}

function _fixture_backref_error(body: Record<string, any>, opts: { block_index: number; assert_index: number | null; policy: Record<string, any> }): string {
  const policy = opts.policy;
  const blockIndex = opts.block_index;
  const assertIndex = opts.assert_index;
  const requiredPolicy = new Set(["value_prefix", "domain_suffix", "allowed_kinds", "expected_binding_rule", "disclosure_required"]);
  const policyKeys = new Set(Object.keys(policy));
  const samePolicy = policyKeys.size === requiredPolicy.size && [...policyKeys].every((k) => requiredPolicy.has(k));
  const allowedKinds = Array.isArray(policy["allowed_kinds"]) ? new Set(policy["allowed_kinds"]) : new Set();
  if (!samePolicy || !String(policy["value_prefix"] || "") || !String(policy["domain_suffix"] || "") || !(allowedKinds.size === 2 && allowedKinds.has("domain_name") && allowedKinds.has("text_value")) || policy["expected_binding_rule"] !== "config.fixture-literal-backref" || policy["disclosure_required"] !== true) {
    return "the frozen fixture policy is incomplete or outside its closed contract";
  }
  const blocks = body["blocks"] || [];
  if (typeof blockIndex !== "number" || !Number.isInteger(blockIndex) || blockIndex < 0 || blockIndex >= blocks.length || typeof assertIndex !== "number" || assertIndex === null || !Number.isInteger(assertIndex) || !_isMapping(blocks[blockIndex]) || String(blocks[blockIndex]["kind"] || "").trim().toUpperCase() !== "OBSERVE_ASSERT") {
    return "a fixture assertion must use an OBSERVE_ASSERT assertion slot";
  }
  const assertions = blocks[blockIndex]["asserts"];
  if (!Array.isArray(assertions) || assertIndex < 0 || assertIndex >= assertions.length || !_isMapping(assertions[assertIndex])) {
    return "the fixture assertion slot is unavailable";
  }
  const assertion = assertions[assertIndex];
  const ref = String(assertion["ref"] || "");
  const binding = assertion["binding_input"];
  if (!ref.startsWith("config_derived:") || !_isMapping(binding) || JSON.stringify(Object.keys(binding).sort()) !== JSON.stringify(["rule_id", "source_input"]) || binding["rule_id"] !== policy["expected_binding_rule"] || !_isMapping(binding["source_input"])) {
    return "fixture expected must use config.fixture-literal-backref; an LLM or free-text expected source cannot sign the value";
  }
  const sourceInput = binding["source_input"];
  const requiredInput = new Set(["operator", "value", "fixture_kind", "config_block_index", "config_command_index"]);
  const inputKeys = new Set(Object.keys(sourceInput));
  const sameInput = inputKeys.size === requiredInput.size && [...inputKeys].every((k) => requiredInput.has(k));
  if (!sameInput) {
    return "fixture back-reference source_input fields are not closed";
  }
  const operator = String(sourceInput["operator"] || "");
  const value = sourceInput["value"];
  const fixtureKind = String(sourceInput["fixture_kind"] || "");
  const configBlockIndex = sourceInput["config_block_index"];
  const configCommandIndex = sourceInput["config_command_index"];
  if (operator !== String(assertion["op"] || "") || typeof value !== "string" || value !== String(assertion["pattern"] || "") || !allowedKinds.has(fixtureKind) || typeof configBlockIndex !== "number" || !Number.isInteger(configBlockIndex) || configBlockIndex < 0 || configBlockIndex >= blockIndex || typeof configCommandIndex !== "number" || !Number.isInteger(configCommandIndex) || configCommandIndex < 0) {
    return "fixture expected tuple does not identify an earlier configuration literal";
  }
  const prefix = String(policy["value_prefix"]);
  const suffix = String(policy["domain_suffix"]);
  let safeName: boolean;
  if (fixtureKind === "domain_name") {
    safeName = Boolean(value.startsWith(prefix) && value.endsWith(suffix) && /^[A-Za-z0-9.-]+$/.test(value));
  } else {
    safeName = Boolean(value.startsWith(prefix) && /^[A-Za-z0-9._-]+$/.test(value));
  }
  if (!safeName) {
    return "fixture value violates the isolated autotest naming policy";
  }
  const configBlock = blocks[configBlockIndex];
  const commands = _isMapping(configBlock) ? configBlock["cmds"] : null;
  if (!_isMapping(configBlock) || String(configBlock["kind"] || "").trim().toUpperCase() !== "CONFIG" || !Array.isArray(commands) || configCommandIndex >= commands.length || typeof commands[configCommandIndex] !== "string") {
    return "fixture back-reference does not resolve to a CONFIG command";
  }
  const command = commands[configCommandIndex];
  const literal = new RegExp("(?<![A-Za-z0-9_.-])" + value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![A-Za-z0-9_.-])");
  if (!literal.test(command)) {
    return "fixture expected value is not a literal in the referenced CONFIG command";
  }
  return "";
}

export function criterion_satisfiability_gaps(contract: Record<string, any>): Record<string, any>[] {
  const gaps: Record<string, any>[] = [];
  ((contract["expectations"] || []) as any[]).forEach((item, index) => {
    if (!_isMapping(item)) {
      return;
    }
    const claim = item["normalized_claim"];
    if (!_isMapping(claim)) {
      return;
    }
    const criterionType = String(claim["criterion_type"] || "");
    if (String(claim["status"] || "") !== "matched" || !(criterionType in CRITERION_TYPE_ALLOWED_SLOTS)) {
      gaps.push({ expectation_id: String(claim["expectation_id"] || ""), criterion_type: criterionType, claim_status: String(claim["status"] || ""), check_scope: "claim_status_and_registered_type", locus: `contract.expectations[${index}].normalized_claim` });
    }
  });
  return gaps;
}

const _teardownReversalIndexCache = new Map<string, [string, string[]][]>();

function _teardown_reversal_index(deviceBuild: string): [string, string[]][] {
  let build = String(deviceBuild || "").trim();
  if (!build) {
    return [];
  }
  if (_teardownReversalIndexCache.has(build)) {
    return _teardownReversalIndexCache.get(build)!;
  }
  let index: [string, string[]][];
  try {
    const { device_os_build_suffix } = require("./vendor_stdlib");
    const { load_command_teardown_atlas, verify_atlas_source_identity } = require("../scripts/gen_command_teardown_atlas");
    build = device_os_build_suffix(build) || build;
    const atlas = load_command_teardown_atlas({ expected_build: build });
    verify_atlas_source_identity(atlas);
    const map = new Map<string, Set<string>>();
    for (const [head, entry] of Object.entries(atlas["commands"] || {})) {
      if (!_isMapping(entry)) continue;
      const teardown = entry["teardown"];
      if (!_isMapping(teardown)) continue;
      const inverses = ((teardown["suggested_inverses"] || []) as any[]).map((value) => String(value).trim().toLowerCase()).filter((value) => value);
      if (!inverses.length) continue;
      const forward = String(head || "").trim().toLowerCase();
      if (!forward) continue;
      if (String(teardown["matched_form"] || "") === "switch_sibling") {
        if (!map.has(forward)) map.set(forward, new Set());
        inverses.forEach((inverse) => map.get(forward)!.add(inverse));
        continue;
      }
      for (const inverse of inverses) {
        if (!map.has(inverse)) map.set(inverse, new Set());
        map.get(inverse)!.add(forward);
      }
    }
    index = [...map.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([key, values]) => [key, [...values].sort()] as [string, string[]]);
  } catch (exc) {
    logger.warn?.("teardown atlas 不可用——绑定声明不给豁免", exc);
    index = [];
  }
  if (_teardownReversalIndexCache.size >= 8) {
    _teardownReversalIndexCache.delete(_teardownReversalIndexCache.keys().next().value!);
  }
  _teardownReversalIndexCache.set(String(deviceBuild || "").trim(), index);
  return index;
}

function _gate_criterion_type_binding(body: Record<string, any>, contract: Record<string, any>, report: _Report, opts: { device_build?: string } = {}): void {
  const gate = "criterion_type_binding";
  report.ran(gate);
  const normalized: Record<string, Record<string, any>> = {};
  const claimTexts: Record<string, string> = {};
  ((contract["expectations"] || []) as any[]).forEach((item, index) => {
    if (!_isMapping(item)) {
      return;
    }
    const claim = item["normalized_claim"];
    if (!_isMapping(claim)) {
      return;
    }
    const expectationId = String(claim["expectation_id"] || "");
    if (!expectationId || expectationId in normalized) {
      report.reject(gate, "criterion_claim_identity_invalid", `contract.expectations[${index}].normalized_claim`, "normalized criterion claim has an empty or duplicate expectation_id");
      return;
    }
    normalized[expectationId] = { ...claim };
    const authorClaim = item["author_claim"];
    claimTexts[expectationId] = String(claim["original_text"] || (_isMapping(authorClaim) ? authorClaim["source_text"] : "") || item["text"] || "");
  });
  if (!Object.keys(normalized).length) {
    return;
  }
  const bindings = new Map<string, [string, string][]>();
  const bindingLoci = new Map<string, [number, number | null][]>();
  const declaredStateChange = new Map<string, [number, string][]>();
  const reversalIndex = new Map<string, string[]>(_teardown_reversal_index(String(opts.device_build || "")));
  const blocks = body["blocks"] || [];
  ((body["expectation_binding"] || []) as any[]).forEach((binding) => {
    if (!_isMapping(binding)) {
      return;
    }
    const expectationId = String(binding["expectation_id"] || "");
    const blockIndex = binding["block_index"];
    if (!(expectationId in normalized) || typeof blockIndex !== "number" || !Number.isInteger(blockIndex) || blockIndex < 0 || blockIndex >= blocks.length || !_isMapping(blocks[blockIndex])) {
      return;
    }
    const block = blocks[blockIndex];
    const kind = String(block["kind"] || "").trim().toUpperCase();
    let operator = "";
    if (kind === "OBSERVE_ASSERT") {
      const assertIndex = binding["assert_index"];
      const assertions = block["asserts"];
      if (typeof assertIndex === "number" && Number.isInteger(assertIndex) && Array.isArray(assertions) && assertIndex >= 0 && assertIndex < assertions.length && _isMapping(assertions[assertIndex])) {
        operator = String(assertions[assertIndex]["op"] || "").trim();
      }
    } else if (kind === "STEP") {
      operator = String(block["F"] || "").trim();
    }
    if (!bindings.has(expectationId)) bindings.set(expectationId, []);
    bindings.get(expectationId)!.push([kind, operator]);
    if (!bindingLoci.has(expectationId)) bindingLoci.set(expectationId, []);
    const rawAssert = binding["assert_index"];
    bindingLoci.get(expectationId)!.push([blockIndex, typeof rawAssert === "number" && Number.isInteger(rawAssert) ? rawAssert : null]);
    const declaredStep = binding["state_change_step"];
    const declaredText = String(binding["binding_disclosure"] || "").trim();
    if (typeof declaredStep === "number" && Number.isInteger(declaredStep) && declaredStep >= 0 && declaredText) {
      if (!declaredStateChange.has(expectationId)) declaredStateChange.set(expectationId, []);
      declaredStateChange.get(expectationId)!.push([declaredStep, declaredText]);
    }
  });
  const allowed = CRITERION_TYPE_ALLOWED_SLOTS;
  for (const [expectationId, claim] of Object.entries(normalized)) {
    const status = String(claim["status"] || "");
    const criterionType = String(claim["criterion_type"] || "");
    if (status !== "matched" || !(criterionType in allowed)) {
      report.reject(gate, "criterion_type_unresolved", `expectation_id=${expectationId}`, "the frozen contract has no identity-bound matched criterion type; return to the batch author-confirmation stage");
      continue;
    }
    const slots = bindings.get(expectationId) || [];
    if (!slots.length) {
      report.reject(gate, "criterion_binding_missing", `expectation_id=${expectationId}`, "no mechanical assertion slot redeems this normalized criterion");
      continue;
    }
    const allowedSlots = [...allowed[criterionType]];
    const invalid = slots.filter((slot) => !allowedSlots.some((s) => s[0] === slot[0] && s[1] === slot[1]));
    if (invalid.length) {
      const permitted = allowedSlots.map(([block, op]) => `(${block}, ${op || "no operator"})`).join(", ");
      report.reject(gate, "criterion_lowering_mismatch", `expectation_id=${expectationId}`, `criterion_type=${criterionType} cannot lower through ${JSON.stringify(invalid)}. It may only lower through: ${permitted}. Rebind this expectation to one of those slots, or, if none can express the authored assertion, report an engine-side criterion gap instead of forcing the nearest operator.`);
    } else if (criterionType === "status_value") {
      for (const [blockIndex, assertIndex] of bindingLoci.get(expectationId) || []) {
        const literalError = _status_value_claim_literalization_error(body, { block_index: blockIndex, assert_index: assertIndex, claim_text: claimTexts[expectationId] || "" });
        if (literalError) {
          report.reject(gate, "criterion_status_claim_literalized", `expectation_id=${expectationId}`, literalError);
          continue;
        }
        const error = _status_value_target_error(body, { block_index: blockIndex, assert_index: assertIndex });
        if (!error) {
          continue;
        }
        let declared = declaredStateChange.get(expectationId) || [];
        if (declared.length && !reversalIndex.size) {
          declared = [];
        }
        if (declared.length) {
          const fakePass = _declared_state_change_fake_pass_error(body, { block_index: blockIndex, assert_index: assertIndex, declared_steps: declared.map(([step]) => step), reversal_index: reversalIndex });
          if (fakePass) {
            report.reject(gate, "criterion_state_change_step_self_satisfying", `expectation_id=${expectationId}`, fakePass);
            continue;
          }
          const invalidStep = _declared_state_change_step_error(body, { observe_block_index: blockIndex, declared_steps: declared.map(([step]) => step) });
          if (invalidStep) {
            report.reject(gate, "criterion_state_change_step_invalid", `expectation_id=${expectationId}`, invalidStep);
            continue;
          }
          for (const [step, disclosure] of declared) {
            report.advise(gate, "criterion_binding_declared", `expectation_id=${expectationId}`, disclosure, { expectation_id: expectationId, state_change_step: Math.trunc(step), disclosure });
          }
          continue;
        }
        report.reject(gate, "criterion_status_target_unbound", `expectation_id=${expectationId}`, error);
      }
    }
    const fixturePolicy = claim["fixture_policy"];
    if (_isMapping(fixturePolicy)) {
      for (const [blockIndex, assertIndex] of bindingLoci.get(expectationId) || []) {
        const error = _fixture_backref_error(body, { block_index: blockIndex, assert_index: assertIndex, policy: fixturePolicy });
        if (error) {
          report.reject(gate, "fixture_expected_not_config_backref", `expectation_id=${expectationId}`, error);
        }
      }
    }
  }
}

function _status_value_claim_literalization_error(body: Record<string, any>, opts: { block_index: number; assert_index: number | null; claim_text: string }): string {
  const blocks = body["blocks"] || [];
  const blockIndex = opts.block_index;
  const assertIndex = opts.assert_index;
  if (!Array.isArray(blocks) || typeof blockIndex !== "number" || !Number.isInteger(blockIndex) || blockIndex < 0 || blockIndex >= blocks.length || !_isMapping(blocks[blockIndex]) || String(blocks[blockIndex]["kind"] || "").trim().toUpperCase() !== "OBSERVE_ASSERT" || typeof assertIndex !== "number" || assertIndex === null || !Number.isInteger(assertIndex)) {
    return "";
  }
  const assertions = blocks[blockIndex]["asserts"];
  if (!Array.isArray(assertions) || assertIndex < 0 || assertIndex >= assertions.length || !_isMapping(assertions[assertIndex])) {
    return "";
  }
  const assertion = assertions[assertIndex];
  if (!String(assertion["ref"] || "").trim().startsWith("intent:")) {
    return "";
  }
  const claim = String(opts.claim_text || "").trim();
  const pattern = String(assertion["pattern"] || "").trim();
  if (!claim || !pattern) {
    return "";
  }
  let candidate = pattern.replace(/^\(\?[aiLmsux-]+\)/, "");
  for (const [prefix, suffix] of [["^", "$"], ["\\A", "\\Z"]] as [string, string][]) {
    if (candidate.startsWith(prefix) && candidate.endsWith(suffix)) {
      candidate = candidate.slice(prefix.length, candidate.length - suffix.length);
      break;
    }
  }
  if (candidate.endsWith("\\r?")) {
    candidate = candidate.slice(0, -3);
  }
  const escapedClaim = claim.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  if (candidate !== claim && candidate !== escapedClaim) {
    return "";
  }
  return `status-value assertion at blocks[${blockIndex}].asserts[${assertIndex}] uses the Author's semantic claim sentence itself as a device-output pattern. An intent claim signs the expected state or polarity, not the language or exact bytes emitted by this device build. Observe a structural consequence, use the engine-derived exit-status form, or cite an independent identity-bound source that explicitly declares the output bytes.`;
}

function _status_value_target_error(body: Record<string, any>, opts: { block_index: number; assert_index: number | null }): string {
  const blocks = body["blocks"] || [];
  const blockIndex = opts.block_index;
  const assertIndex = opts.assert_index;
  if (!Array.isArray(blocks) || typeof blockIndex !== "number" || !Number.isInteger(blockIndex) || blockIndex < 0 || blockIndex >= blocks.length) {
    return "status-value binding does not identify one block";
  }
  const block = blocks[blockIndex];
  if (!_isMapping(block) || String(block["kind"] || "").trim().toUpperCase() !== "OBSERVE_ASSERT") {
    return "";
  }
  if (typeof assertIndex !== "number" || assertIndex === null || !Number.isInteger(assertIndex)) {
    return "status-value OBSERVE_ASSERT binding does not identify one assertion slot";
  }
  const assertions = block["asserts"];
  if (!Array.isArray(assertions) || assertIndex < 0 || assertIndex >= assertions.length || !_isMapping(assertions[assertIndex])) {
    return "status-value binding points outside the assertion array";
  }
  const command = String(block["cmd"] || "").trim();
  const { observe_kind } = require("./observe_ops");
  if (!observe_kind(command)) {
    return "";
  }
  const assertion = assertions[assertIndex];
  const operator = String(assertion["op"] || "").trim();
  const pattern = String(assertion["pattern"] || "");

  function _matches(text: string): boolean {
    if (!text) {
      return false;
    }
    if (operator === "abs_found") {
      return text.includes(pattern);
    }
    try {
      return new RegExp(pattern, "m").test(text);
    } catch {
      return false;
    }
  }
  let nearestConfigIndex = -1;
  let nearestCommands: string[] = [];
  for (let index = blockIndex - 1; index >= 0; index--) {
    const candidate = blocks[index];
    if (_isMapping(candidate) && String(candidate["kind"] || "").trim().toUpperCase() === "CONFIG") {
      nearestConfigIndex = index;
      const commands = candidate["cmds"];
      nearestCommands = Array.isArray(commands) ? commands.filter((value: any) => typeof value === "string").map((value: any) => String(value)) : [];
      break;
    }
  }
  if (nearestConfigIndex < 0 || nearestCommands.some((value) => _matches(value))) {
    return "";
  }
  return `status-value assertion at blocks[${blockIndex}].asserts[${assertIndex}] uses a pattern that is not grounded by the nearest causal CONFIG block[${nearestConfigIndex}]. The signed claim text describes state semantics, not device-output bytes. It can therefore pass while that latest state change has a different outcome. Bind the assertion to the value changed by that CONFIG step, observe the action response directly, or use an independently signed derived expectation; do not prove progress by re-checking an older baseline. When the asserted value is a runtime outcome that no configuration command line can carry, the declared path is the fourth repair and not an engine gap: on this expectation's expectation_binding entry set state_change_step to ${nearestConfigIndex} and write binding_disclosure, one user-facing Chinese sentence saying why that command line cannot carry the value and how this step causes the change. The engine then records that binding instead of refusing it, so resubmitting the same shape without the declaration is not the only move left.`;
}

function _declared_causal_block_command_lines(block: Record<string, any>): string[] {
  const { APV_CONFIG_METHODS, is_apv_command_step } = require("../ist_core/tools/device/emit_xlsx_tool");
  if (String(block["kind"] || "").trim().toUpperCase() === "CONFIG") {
    const commands = block["cmds"];
    return Array.isArray(commands) ? commands.filter((value: any) => typeof value === "string" && value.trim()).map((value: any) => value.trim()) : [];
  }
  if (is_apv_command_step({ ...block }, { methods: APV_CONFIG_METHODS })) {
    return String(block["G"] || "").split("\n").map((line) => line.trim()).filter((line) => line);
  }
  return [];
}

function _declared_state_change_step_error(body: Record<string, any>, opts: { observe_block_index: number; declared_steps: number[] }): string {
  const blocks = body["blocks"] || [];
  if (!Array.isArray(blocks)) {
    return "blocks is not an array, so a declared causal step cannot be located";
  }
  for (const step of opts.declared_steps) {
    if (step < 0 || step >= blocks.length || !_isMapping(blocks[step])) {
      return `state_change_step ${step} does not name a block in this case's procedure (${blocks.length} blocks)`;
    }
    if (!_declared_causal_block_command_lines(blocks[step]).length) {
      return `state_change_step ${step} names a block that carries no product configuration command line; only a step that reaches the device under test can be declared as the cause of a state change`;
    }
    if (step >= opts.observe_block_index) {
      return `state_change_step ${step} runs at or after the observation at blocks[${opts.observe_block_index}]; a step that has not run yet cannot have caused the state this assertion reads`;
    }
  }
  return "";
}

function _declared_state_change_fake_pass_error(body: Record<string, any>, opts: { block_index: number; assert_index: number | null; declared_steps: number[]; reversal_index: Map<string, string[]> }): string {
  const blocks = body["blocks"] || [];
  const blockIndex = opts.block_index;
  const assertIndex = opts.assert_index;
  if (!Array.isArray(blocks) || typeof blockIndex !== "number" || !Number.isInteger(blockIndex) || blockIndex < 0 || blockIndex >= blocks.length || !_isMapping(blocks[blockIndex]) || typeof assertIndex !== "number" || assertIndex === null || !Number.isInteger(assertIndex)) {
    return "";
  }
  const assertions = blocks[blockIndex]["asserts"];
  if (!Array.isArray(assertions) || assertIndex < 0 || assertIndex >= assertions.length || !_isMapping(assertions[assertIndex])) {
    return "";
  }
  const assertion = assertions[assertIndex];
  if (String(assertion["op"] || "").trim() !== "not_found") {
    return "";
  }
  const pattern = String(assertion["pattern"] || "");
  if (!pattern) {
    return "";
  }

  function _matches(text: string): boolean {
    try {
      return new RegExp(pattern, "m").test(text);
    } catch {
      return false;
    }
  }
  for (const step of opts.declared_steps) {
    if (step < 0 || step >= blocks.length || !_isMapping(blocks[step])) {
      continue;
    }
    for (const line of _declared_causal_block_command_lines(blocks[step])) {
      const undone = _reversed_states_of(line, opts.reversal_index);
      if (!undone.length) {
        continue;
      }
      let hit = undone.find((state) => _matches(state)) || "";
      if (!hit && _matches(line)) {
        hit = line;
      }
      if (hit) {
        return `the not_found assertion at blocks[${blockIndex}].asserts[${assertIndex}] declares blocks[${step}] as its causal step, and that step's command line ${JSON.stringify(line)} is the build-bound inverse of ${JSON.stringify(hit)} — it removes the very state the assertion then reports as absent. The assertion is satisfied by that removal, so it verifies nothing about the behaviour under test. A declared causal step does not lift this refusal.`;
      }
    }
  }
  return "";
}

function _reversed_states_of(line: string, reversalIndex: Map<string, string[]>): string[] {
  const words = String(line || "").toLowerCase().split(/\s+/).filter((w) => w);
  for (let count = words.length; count > 0; count--) {
    const candidate = words.slice(0, count).join(" ");
    if (reversalIndex.has(candidate)) {
      return reversalIndex.get(candidate)!;
    }
  }
  return [];
}

function _gate_semantic_key_group_rank(body: Record<string, any>, finalSteps: any[], report: _Report): void {
  const gate = "semantic_key_group_rank";
  report.ran(gate);
  for (const [key, ids, rank, size] of semantic_key_group_defects(finalSteps)) {
    report.reject(gate, "semantic_key_group_rank_deficient", `semantic_key=${key}`, `${size} assertions share this semantic_key but only ${rank} distinct (observation_ref, F, G) triples: ${ids.join(", ")}. Two assertions doing the same thing verify one thing; give each claim its own observation or its own operator/expected value.`);
  }
  const scoped = new Map<string, string[]>();
  const missing = new Map<string, string[]>();
  ((body["expectation_binding"] || []) as any[]).forEach((item, index) => {
    if (!_isMapping(item)) {
      return;
    }
    const key = String(item["semantic_key"] || "");
    if (!scoped.has(key)) scoped.set(key, []);
    scoped.get(key)!.push(String(item["expectation_id"] || ""));
    if (!String(item["scope_ref"] || "").trim()) {
      if (!missing.has(key)) missing.set(key, []);
      missing.get(key)!.push(`expectation_binding[${index}]`);
    }
  });
  for (const key of [...missing.keys()].sort()) {
    if ((scoped.get(key) || []).length < 2) {
      continue;
    }
    report.advise(gate, "scope_ref_absent", `semantic_key=${key}`, `${(scoped.get(key) || []).length} claims share this semantic_key and ${(missing.get(key) || []).join(", ")} carry no scope_ref; without it the verification card cannot tell the sibling claims apart.`);
  }
}

function _gate_escape_hatch_accounting(body: Record<string, any>, report: _Report): EscapeHatchDefect[] {
  const gate = "escape_hatch_accounting";
  report.ran(gate);
  const positions: number[] = [];
  const indices: number[] = [];
  ((body["escape_hatches"] || []) as any[]).forEach((hatch, index) => {
    if (!_isMapping(hatch)) {
      return;
    }
    const blockIndex = hatch["block_index"];
    if (typeof blockIndex !== "number" || !Number.isInteger(blockIndex)) {
      return;
    }
    positions.push(index);
    indices.push(blockIndex);
  });
  const defects = escape_hatch_accounting_defects(body["blocks"] || [], indices);
  for (const defect of defects) {
    const locus = defect.entry_index < 0 ? "escape_hatches" : `escape_hatches[${positions[defect.entry_index]}]`;
    report.reject(gate, defect.code, locus, defect.detail);
  }
  return defects;
}

function _gate_document_consistency(body: Record<string, any>, measurements: Record<string, any>, escapeDefects: EscapeHatchDefect[], report: _Report): void {
  const gate = "document_consistency";
  report.ran(gate);
  let seal: Record<string, any>;
  try {
    seal = seal_mechanical_case({ ...body }, { capabilities_used: [...measurements["capabilities_used"]], expanded_step_count: Math.trunc(measurements["expanded_step_count"]), check_point_count: Math.trunc(measurements["check_point_count"]), gate_report_sha256: _PROVISIONAL_GATE_REPORT_SHA256 });
  } catch (exc: any) {
    if (exc instanceof MechanicalCaseError) {
      report.reject(gate, "seal_uncastable", "seal", String(exc.message ?? exc));
      return;
    }
    throw exc;
  }
  const [caseData, error] = validate_mechanical_case({ ...body, seal });
  if (caseData === null) {
    if (escapeDefects.some((defect) => error.includes(defect.detail))) {
      report.reject_named_by(gate, "escape_hatch_accounting");
      return;
    }
    report.reject(gate, "document_inconsistent", "case", error);
  }
}

export function run_mechanical_case_gate(
  mc: any,
  contract: Record<string, any>,
  opts: {
    contract_sha256: string;
    device_build: string;
    outputs_root?: string | null;
    consistency_contract?: Record<string, any> | null;
    consistency_contract_sha256?: string;
    consistency_required?: boolean;
    source_case_slice?: Record<string, any> | null;
    source_case_slice_sha256?: string;
  }
): [boolean, Record<string, any>] {
  const report = new _Report(_isMapping(mc) ? String(mc["autoid"] || "") : "");
  let measurements: Record<string, any> | null = null;
  const body = _gate_body(mc, report);
  if (body !== null) {
    _gate_contract_description(body, contract, report);
    _gate_consistency_contract(body, contract, opts.contract_sha256, opts.consistency_contract ?? null, opts.consistency_contract_sha256 ?? "", opts.consistency_required ?? false, report);
    _gate_criterion_type_binding(body, contract, report, { device_build: opts.device_build });
    const expanded = _gate_blocks_expansion(body, report);
    if (expanded !== null) {
      const [intermediateSteps, intermediateProvenance] = expanded;
      measurements = _measurements(intermediateSteps);
      const lowered = _gate_derived_assertion_expansion(intermediateSteps, intermediateProvenance, report);
      if (lowered !== null) {
        const [steps, provenanceSteps] = lowered;
        const init = _init_g(body["init_commands"]);
        const authorIpLiterals = _author_ip_literals_for_submission(report.autoid, steps, init, { source_case_slice: opts.source_case_slice ?? null, source_case_slice_sha256: opts.source_case_slice_sha256 ?? "" });
        _gate_structural_lint(steps, provenanceSteps, init, report, { device_build: opts.device_build, author_ip_literals: authorIpLiterals });
        _gate_author_procedure_coverage(contract, steps, init, report, { device_build: opts.device_build });
        _gate_https_certificate_lifecycle(steps, init, report, { device_build: opts.device_build });
        _gate_unreachable_ips(report.autoid, steps, init, report, { source_case_slice: opts.source_case_slice ?? null, source_case_slice_sha256: opts.source_case_slice_sha256 ?? "" });
        _gate_trigger_reachability(report.autoid, steps, init, body["blocks"], report, { author_ip_literals: authorIpLiterals });
        _gate_negative_probe_path(body["blocks"], report);
        _gate_paired_teardown(steps, init, report, { device_build: opts.device_build });
        const caseProv = _gate_provenance_receipts(report.autoid, steps, provenanceSteps, report, opts.outputs_root ?? null);
        if (caseProv !== null) {
          const finalSteps = _product_assertions(caseProv);
          _gate_expectation_bijection(body, contract, opts.contract_sha256, finalSteps, caseProv.steps, report);
          _gate_semantic_key_group_rank(body, finalSteps, report);
        }
      }
    }
    _gate_answerer_statement(body, report);
    const escapeDefects = _gate_escape_hatch_accounting(body, report);
    if (measurements !== null) {
      _gate_document_consistency(body, measurements, escapeDefects, report);
    }
    _gate_step_graph(body, report);
  }
  let bodySha256 = "";
  try {
    bodySha256 = body !== null ? _canonical_sha256(body) : "";
  } catch {
    bodySha256 = "";
  }
  const rendered = report.render(measurements, { mechanical_case_body_sha256: bodySha256, contract_sha256: String(opts.contract_sha256 || ""), device_build: String(opts.device_build || ""), consistency_contract_sha256: String(opts.consistency_contract_sha256 || "") });
  return [Boolean(rendered["ok"]), rendered];
}

function _gate_step_graph(mc: any, report: _Report): void {
  const { check_step_graph } = require("./step_graph");
  report.ran("step_graph");
  const blocks = _isMapping(mc) ? mc["blocks"] : null;
  const graph = check_step_graph(Array.isArray(blocks) ? blocks : []);
  for (const issue of graph.issues) {
    report.advise("step_graph", issue.code, issue.path, `${issue.message} | evidence=${issue.evidence}`);
  }
}

function _measurements(steps: Record<string, any>[]): Record<string, any> {
  const { _raw_capabilities_touched } = require("../ist_core/tools/device/emit_xlsx_tool");
  return { capabilities_used: _raw_capabilities_touched([...steps]), expanded_step_count: steps.length, check_point_count: steps.filter((step) => String(step["E"] || "").trim() === _CHECK_POINT_OBJECT).length };
}
