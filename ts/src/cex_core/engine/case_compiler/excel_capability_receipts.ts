import path from "node:path";
import { _cex_data_path } from "../_root";
import {
  canonical_json as _sealedCanonicalJson,
  lexical_absolute as _lexicalAbsolute,
  open_directory_nofollow,
  read_regular_at_nofollow,
  sha256_bytes as _sha256Bytes,
  validate_json_budget,
} from "./_sealed_io";
import fs from "node:fs";

export const SCHEMA = "ist.excel.capability-certification";
export const RUNTIME_VERSION = "ist.excel.runtime";
const _HEX_RE = /^[0-9a-f]{64}$/;
const _PHASES = new Set(["certification", "release"]);
const _VERDICTS = new Set(["pass", "fail", "unavailable"]);
const _CLEANUP = new Set(["pass", "fail", "unavailable", "not_required"]);
const _ROOT = _cex_data_path("");
const _DEFAULT_TRUSTED_ROOT = path.join(_ROOT, "runtime", "excel_capability_receipts");
const _MAX_RECEIPT_FILES = 4096;
const _MAX_RECEIPT_BYTES = 512 * 1024;

export class ExcelCapabilityReceiptError extends Error {}

export class ValidatedReceiptSet {
  receipts: Record<string, any>[];
  receipt_set_sha256: string;
  phase: string;
  constructor(receipts: Record<string, any>[], receipt_set_sha256: string, phase: string) {
    this.receipts = receipts;
    this.receipt_set_sha256 = receipt_set_sha256;
    this.phase = phase;
    Object.freeze(this);
  }
}

function _canonicalJson(value: any): Buffer {
  return _sealedCanonicalJson(value, { ensure_ascii: true });
}

function _requireSha(value: any, opts: { label: string }): string {
  if (typeof value !== "string" || !_HEX_RE.test(value)) {
    throw new ExcelCapabilityReceiptError(`${opts.label} must be a SHA-256 hex digest`);
  }
  return value;
}

function _requireText(value: any, opts: { label: string }): string {
  if (typeof value !== "string" || !value.trim() || value.includes("") || [...value].some((ch) => ch.codePointAt(0)! < 32)) {
    throw new ExcelCapabilityReceiptError(`${opts.label} must be non-empty safe text`);
  }
  return value;
}

export function receipt_sha256(receipt: Record<string, any>): string {
  const body = { ...receipt };
  delete body.receipt_sha256;
  return _sha256Bytes(_canonicalJson(body));
}

export function source_closure_sha256(contract: Record<string, any>): string {
  const hashes = contract.source_hashes;
  if (typeof hashes !== "object" || hashes === null || Array.isArray(hashes) || !Object.keys(hashes).length) {
    throw new ExcelCapabilityReceiptError("contract source hash closure is unavailable");
  }
  const normalized: Record<string, string> = {};
  for (const [p, digest] of Object.entries(hashes)) {
    if (typeof p !== "string" || !p || p.startsWith("/") || p.split(/[\\/]+/).includes("..")) {
      throw new ExcelCapabilityReceiptError("contract source path is unsafe");
    }
    normalized[p] = _requireSha(digest, { label: `source ${p}` });
  }
  return _sha256Bytes(_canonicalJson(normalized));
}

function _object(value: any, opts: { label: string }): Record<string, any> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ExcelCapabilityReceiptError(`${opts.label} must be an object`);
  }
  return value;
}

function _entryForReceipt(contract: Record<string, any>, capability: Record<string, any>): Record<string, any> {
  const eValue = _requireText(capability.e, { label: "capability.e" });
  const fValue = _requireText(capability.f, { label: "capability.f" });
  const symbol = _requireText(capability.python_symbol, { label: "capability.python_symbol" });
  const matches = (contract.entries || []).filter(
    (entry: any) =>
      typeof entry === "object" && entry !== null &&
      entry.e === eValue && entry.f === fValue && entry.python_symbol === symbol
  );
  if (matches.length !== 1) {
    throw new ExcelCapabilityReceiptError("receipt has no unique E/F contract binding");
  }
  return matches[0];
}

function _actionForReceipt(contract: Record<string, any>, capability: Record<string, any>): Record<string, any> {
  const eValue = _requireText(capability.e, { label: "capability.e" });
  const dispatcher = _requireText(capability.dispatcher, { label: "capability.dispatcher" });
  const normalized = _requireText(capability.normalized, { label: "capability.normalized" });
  const canonical = _requireText(capability.canonical, { label: "capability.canonical" });
  const symbol = _requireText(capability.python_symbol, { label: "capability.python_symbol" });
  const matches = (contract.execute_actions || []).filter(
    (action: any) =>
      typeof action === "object" && action !== null &&
      action.dispatcher === dispatcher && action.normalized === normalized &&
      action.canonical === canonical && action.python_symbol === symbol &&
      (action.allowed_es || []).includes(eValue)
  );
  if (matches.length !== 1) {
    throw new ExcelCapabilityReceiptError("receipt has no unique execute action/E contract binding");
  }
  return matches[0];
}

export function validate_capability_receipt(
  raw: Record<string, any>,
  opts: {
    contract: Record<string, any>;
    phase: string;
    contract_file_sha256: string;
    deployment_receipt_sha256: string;
  }
): Record<string, any> {
  const { contract, phase } = opts;
  if (!_PHASES.has(phase)) {
    throw new ExcelCapabilityReceiptError("unknown receipt phase");
  }
  const receipt = { ...raw };
  const { accepts_schema } = require("../common/schema_identity");
  if (!accepts_schema(receipt.schema, SCHEMA) || receipt.phase !== phase) {
    throw new ExcelCapabilityReceiptError("receipt schema or phase mismatch");
  }
  const stored = _requireSha(receipt.receipt_sha256, { label: "receipt_sha256" });
  if (receipt_sha256(receipt) !== stored) {
    throw new ExcelCapabilityReceiptError("receipt canonical digest mismatch");
  }
  const status = receipt.status;
  if (!_VERDICTS.has(status)) {
    throw new ExcelCapabilityReceiptError("receipt status is invalid");
  }
  const contractInfo = _object(receipt.contract, { label: "contract" });
  const basisSha = _requireSha(contractInfo.basis_sha256, { label: "contract.basis_sha256" });
  const observedSha = _requireSha(contractInfo.observed_sha256, { label: "contract.observed_sha256" });
  const expectedContractSha = _requireSha(contract.contract_sha256, { label: "contract.contract_sha256" });
  if (
    !accepts_schema(contractInfo.runtime_version, RUNTIME_VERSION) ||
    _requireSha(contractInfo.contract_file_sha256, { label: "contract.contract_file_sha256" }) !==
      _requireSha(opts.contract_file_sha256, { label: "expected contract file" })
  ) {
    throw new ExcelCapabilityReceiptError("receipt contract file/runtime identity mismatch");
  }
  if (phase === "certification") {
    if (basisSha !== expectedContractSha || observedSha !== expectedContractSha) {
      throw new ExcelCapabilityReceiptError("certification receipt does not observe the basis contract");
    }
  } else {
    const certification = contract.certification;
    const expectedBasisSha =
      typeof certification === "object" && certification !== null ? certification.basis_contract_sha256 : expectedContractSha;
    if (basisSha !== expectedBasisSha || observedSha !== expectedContractSha) {
      throw new ExcelCapabilityReceiptError("release receipt does not bind the basis/final contract identity");
    }
  }
  const source = _object(receipt.source, { label: "source" });
  const closureSha = source_closure_sha256(contract);
  if (
    _requireSha(source.closure_sha256, { label: "source.closure_sha256" }) !== closureSha ||
    _requireSha(source.remote_closure_sha256, { label: "source.remote_closure_sha256" }) !== closureSha ||
    _requireSha(source.runner_sha256, { label: "source.runner_sha256" }) !== (contract.runtime || {}).runner_sha256 ||
    _requireSha(source.deployment_receipt_sha256, { label: "source.deployment_receipt_sha256" }) !==
      _requireSha(opts.deployment_receipt_sha256, { label: "expected deployment receipt" })
  ) {
    throw new ExcelCapabilityReceiptError("receipt source/deployment closure mismatch");
  }
  const environment = _object(receipt.environment, { label: "environment" });
  for (const field of ["environment_id", "bed_lease_id", "host_key_sha256"]) {
    _requireText(environment[field], { label: `environment.${field}` });
  }
  _requireSha(environment.facts_sha256, { label: "environment.facts_sha256" });
  if (!String(environment.host_key_sha256).startsWith("SHA256:")) {
    throw new ExcelCapabilityReceiptError("environment host key fingerprint is invalid");
  }
  const device = _object(receipt.device, { label: "device" });
  _requireSha(device.device_id_sha256, { label: "device.device_id_sha256" });
  _requireSha(device.facts_sha256, { label: "device.facts_sha256" });
  _requireText(device.os_build, { label: "device.os_build" });
  _requireText(device.module, { label: "device.module" });
  const capability = _object(receipt.capability, { label: "capability" });
  const kind = capability.kind;
  let target: Record<string, any>;
  if (kind === "entry") {
    target = _entryForReceipt(contract, capability);
  } else if (kind === "execute_action") {
    target = _actionForReceipt(contract, capability);
  } else {
    throw new ExcelCapabilityReceiptError("receipt capability kind is invalid");
  }
  const sourceInfo = _object(target.source, { label: "capability source" });
  const sourcePath = sourceInfo.path;
  const expectedSourceSha = (contract.source_hashes || {})[sourcePath];
  if (_requireSha(capability.source_file_sha256, { label: "capability.source_file_sha256" }) !== expectedSourceSha) {
    throw new ExcelCapabilityReceiptError("receipt capability source SHA mismatch");
  }
  const sample = _object(receipt.sample, { label: "sample" });
  _requireText(sample.sample_id, { label: "sample.sample_id" });
  for (const field of ["sample_manifest_sha256", "g_sha256", "artifact_sha256", "remote_artifact_sha256"]) {
    _requireSha(sample[field], { label: `sample.${field}` });
  }
  if (sample.artifact_sha256 !== sample.remote_artifact_sha256) {
    throw new ExcelCapabilityReceiptError("local/remote sample artifact SHA mismatch");
  }
  const run = _object(receipt.run, { label: "run" });
  _requireText(run.run_id, { label: "run.run_id" });
  const verdict = run.verdict;
  const cleanup = run.cleanup_verdict;
  if (!_VERDICTS.has(verdict) || verdict !== status || !_CLEANUP.has(cleanup)) {
    throw new ExcelCapabilityReceiptError("receipt run verdict is inconsistent");
  }
  _requireSha(run.evidence_sha256, { label: "run.evidence_sha256" });
  _requireSha(run.cleanup_evidence_sha256, { label: "run.cleanup_evidence_sha256" });
  if (phase === "certification" && kind === "execute_action" && cleanup !== "pass") {
    throw new ExcelCapabilityReceiptError("execute action certification requires verified cleanup");
  }
  return JSON.parse(JSON.stringify(receipt));
}

export function validate_receipt_set(
  raw_receipts: Iterable<Record<string, any>>,
  opts: {
    contract: Record<string, any>;
    phase: string;
    contract_file_sha256: string;
    deployment_receipt_sha256: string;
  }
): ValidatedReceiptSet {
  const receipts: Record<string, any>[] = [];
  const seenSha = new Set<string>();
  const seenRun = new Set<string>();
  for (const raw of raw_receipts) {
    const receipt = validate_capability_receipt(raw, opts);
    const digest = receipt.receipt_sha256;
    const capability = receipt.capability;
    const identity = [
      opts.phase,
      String(capability.kind || ""),
      String(capability.e || ""),
      String(capability.f || ""),
      String(capability.dispatcher || ""),
      String(capability.normalized || ""),
      String(receipt.sample.sample_id),
      String(receipt.run.run_id),
    ].join("");
    if (seenSha.has(digest) || seenRun.has(identity)) {
      throw new ExcelCapabilityReceiptError("duplicate capability receipt identity");
    }
    seenSha.add(digest);
    seenRun.add(identity);
    receipts.push(receipt);
  }
  if (!receipts.length) {
    throw new ExcelCapabilityReceiptError("capability receipt set is empty");
  }
  receipts.sort((a, b) => (a.receipt_sha256 < b.receipt_sha256 ? -1 : 1));
  const aggregate = _sha256Bytes(_canonicalJson(receipts.map((item) => item.receipt_sha256)));
  return new ValidatedReceiptSet(receipts, aggregate, opts.phase);
}

function _secureReceiptDirectory(p: string, trustedRoot: string): [string, string] {
  const root = _lexicalAbsolute(trustedRoot);
  const selected = _lexicalAbsolute(p);
  const rel = path.relative(root, selected);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new ExcelCapabilityReceiptError("receipt directory escapes the trusted root");
  }
  const dir = open_directory_nofollow(selected, {
    errorType: ExcelCapabilityReceiptError,
    invalid_message: "receipt directory path is invalid",
    unavailable_message: "receipt directory cannot be opened without following symlinks",
  });
  return [selected, dir];
}

function _readReceiptFileAt(directory: string, name: string): Buffer {
  if (!name.endsWith(".json") || name === "." || name === ".." || name.includes("/") || name.includes("\\")) {
    throw new ExcelCapabilityReceiptError(`receipt directory contains a non-JSON file: ${JSON.stringify(name)}`);
  }
  return read_regular_at_nofollow(directory, name, {
    errorType: ExcelCapabilityReceiptError,
    open_message: "capability receipt file cannot be opened safely",
    bounds_message: "capability receipt must be a bounded single-link regular file",
    changed_message: "capability receipt changed while being read",
    max_bytes: _MAX_RECEIPT_BYTES,
    min_bytes: 1,
    chunk_bytes: 64 * 1024,
  }) as Buffer;
}

export function load_receipt_directory(
  directory: string,
  opts: {
    contract: Record<string, any>;
    phase: string;
    contract_file_sha256: string;
    deployment_receipt_sha256: string;
    trusted_root?: string;
  }
): ValidatedReceiptSet {
  const [, dir] = _secureReceiptDirectory(directory, opts.trusted_root ?? _DEFAULT_TRUSTED_ROOT);
  const rawReceipts: Record<string, any>[] = [];
  const names = fs.readdirSync(dir).filter((n) => !n.startsWith(".")).sort();
  if (names.length > _MAX_RECEIPT_FILES) {
    throw new ExcelCapabilityReceiptError("capability receipt directory exceeds the file-count limit");
  }
  for (const name of names) {
    const raw = _readReceiptFileAt(dir, name);
    let payload: any;
    try {
      validate_json_budget(raw, { errorType: ExcelCapabilityReceiptError, message: "capability receipt exceeds the JSON structure budget" });
      payload = JSON.parse(raw.toString("utf8"));
    } catch (exc) {
      if (exc instanceof ExcelCapabilityReceiptError) throw exc;
      throw new ExcelCapabilityReceiptError("capability receipt JSON is unreadable");
    }
    if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
      throw new ExcelCapabilityReceiptError("capability receipt JSON is not an object");
    }
    rawReceipts.push(payload);
  }
  return validate_receipt_set(rawReceipts, opts);
}

function _capabilityGroup(receipt: Record<string, any>): string[] {
  const capability = receipt.capability;
  if (capability.kind === "entry") {
    return ["entry", capability.e, capability.f, capability.python_symbol];
  }
  return ["execute_action", capability.e, capability.dispatcher, capability.canonical, capability.python_symbol];
}

export function passed_receipt_groups(receipt_set: ValidatedReceiptSet): Map<string, string[]> {
  const grouped = new Map<string, Record<string, any>[]>();
  for (const receipt of receipt_set.receipts) {
    const key = JSON.stringify(_capabilityGroup(receipt));
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(receipt);
  }
  const passed = new Map<string, string[]>();
  for (const [key, items] of grouped) {
    const verdicts = new Set(items.map((item) => item.status));
    if (verdicts.size === 1 && verdicts.has("pass")) {
      passed.set(key, items.map((item) => item.receipt_sha256).sort());
    }
  }
  return passed;
}

export function validate_release_coverage(receipt_set: ValidatedReceiptSet, contract: Record<string, any>): Record<string, any> {
  if (receipt_set.phase !== "release") {
    throw new ExcelCapabilityReceiptError("release coverage requires release receipts");
  }
  const passed = passed_receipt_groups(receipt_set);
  const missingEntries: string[] = [];
  for (const entry of contract.entries || []) {
    if (typeof entry !== "object" || entry === null || entry.status !== "enabled") continue;
    if (entry.dispatch === "execute_registry") continue;
    const key = JSON.stringify(["entry", entry.e, entry.f, entry.python_symbol]);
    if (!passed.has(key)) {
      missingEntries.push(`${entry.e}::${entry.f}`);
    }
  }
  const enabledExecuteEs = new Set(
    (contract.entries || [])
      .filter((item: any) => typeof item === "object" && item !== null && item.status === "enabled" && item.dispatch === "execute_registry")
      .map((item: any) => item.e)
  );
  const requiredActions = new Set<string>();
  for (const action of contract.execute_actions || []) {
    if (typeof action !== "object" || action === null || action.status !== "enabled") continue;
    for (const eValue of action.allowed_es || []) {
      if (!enabledExecuteEs.has(eValue)) continue;
      requiredActions.add(JSON.stringify(["execute_action", eValue, action.dispatcher, action.canonical, action.python_symbol]));
    }
  }
  const missingActions = [...requiredActions]
    .filter((key) => !passed.has(key))
    .map((key) => JSON.parse(key).slice(1).join("::"))
    .sort();
  if (missingEntries.length || missingActions.length) {
    throw new ExcelCapabilityReceiptError(
      `release receipt coverage is incomplete: entries=${missingEntries.length}, actions=${missingActions.length}`
    );
  }
  return {
    schema: "ist.excel.capability-release-set",
    contract_sha256: contract.contract_sha256,
    receipt_set_sha256: receipt_set.receipt_set_sha256,
    receipt_count: receipt_set.receipts.length,
    enabled_entry_count: (contract.entries || []).filter(
      (item: any) => typeof item === "object" && item !== null && item.status === "enabled"
    ).length,
    enabled_action_binding_count: requiredActions.size,
  };
}
