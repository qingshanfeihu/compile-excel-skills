import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "../_root";
import { read_regular_nofollow, sha256_bytes, validate_json_budget } from "./_sealed_io";

_cex_set_caller("cex_core.engine.case_compiler.ssl_lifecycle_contract");

export const SCHEMA = "ist.ssl-lifecycle-contract-source";
const _ROOT = _cex_data_path("");
const _ASSET_ROOT = path.join(_ROOT, "scripts", "maintenance", "assets");
const _SOURCE = path.join(_ASSET_ROOT, "ssl_lifecycle_contract.json");
const _HASH_RE = /^[0-9a-f]{64}$/;
const _MAX_JSON_BYTES = 256 * 1024;
const _MAX_REFERENCE_BYTES = 8 * 1024 * 1024;

export class SSLLifecycleContractError extends Error {}

function _read(p: string, opts: { root: string; max_bytes: number; label: string }): Buffer {
  return read_regular_nofollow(p, {
    errorType: SSLLifecycleContractError,
    invalid_message: `${opts.label} path is invalid`,
    directory_message: `${opts.label} parent is unavailable`,
    open_message: `${opts.label} is unavailable`,
    bounds_message: `${opts.label} exceeds its sealed size boundary`,
    changed_message: `${opts.label} changed while being read`,
    max_bytes: opts.max_bytes,
    min_bytes: 2,
    trusted_root: opts.root,
  }) as Buffer;
}

function _buildSuffix(value: string): string {
  const match = /(?:^|[._-])(\d+)$/.exec(String(value || "").trim());
  return match ? match[1] : String(value || "").trim();
}

function _hashField(value: any, label: string): string {
  const text = String(value || "");
  if (!_HASH_RE.test(text)) {
    throw new SSLLifecycleContractError(`${label} is not a SHA-256 digest`);
  }
  return text;
}

function _loadSourcePayload(): [Record<string, any>, Buffer] {
  const raw = _read(_SOURCE, { root: _ASSET_ROOT, max_bytes: _MAX_JSON_BYTES, label: "SSL lifecycle evidence" });
  validate_json_budget(raw, {
    errorType: SSLLifecycleContractError,
    message: "SSL lifecycle evidence exceeds its JSON structure boundary",
    maxDepth: 32,
    maxTokens: 20000,
  });
  let payload: any;
  try {
    payload = JSON.parse(raw.toString("utf8"));
  } catch (exc) {
    throw new SSLLifecycleContractError("SSL lifecycle evidence is not valid JSON");
  }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload) || payload.schema !== SCHEMA) {
    throw new SSLLifecycleContractError("SSL lifecycle evidence schema mismatch");
  }
  const contracts = payload.contracts;
  if (!Array.isArray(contracts) || contracts.some((item) => typeof item !== "object" || item === null || Array.isArray(item))) {
    throw new SSLLifecycleContractError("SSL lifecycle contract list is invalid");
  }
  return [payload, raw];
}

export function ssl_lifecycle_contract_declares_build(device_build: string): boolean {
  const requested = _buildSuffix(device_build);
  if (!requested) {
    return false;
  }
  const [payload] = _loadSourcePayload();
  const matches = (payload.contracts || []).filter(
    (item: any) => _buildSuffix(String(item.device_build || "")) === requested
  );
  if (matches.length > 1) {
    throw new SSLLifecycleContractError(`SSL lifecycle evidence has ${matches.length} contracts for build ${requested}`);
  }
  return matches.length === 1;
}

export function load_ssl_lifecycle_contract(device_build: string, opts: { verify_command_tree_receipts?: boolean } = {}): Record<string, any> {
  const verifyCommandTreeReceipts = opts.verify_command_tree_receipts ?? true;
  const requested = _buildSuffix(device_build);
  if (!requested) {
    throw new SSLLifecycleContractError("device build is not bound");
  }
  const [payload, raw] = _loadSourcePayload();
  const matches = (payload.contracts || []).filter(
    (item: any) => typeof item === "object" && item !== null && _buildSuffix(String(item.device_build || "")) === requested
  );
  if (matches.length !== 1) {
    throw new SSLLifecycleContractError(`SSL lifecycle evidence has ${matches.length} contracts for build ${requested}`);
  }
  const contract = { ...matches[0] };
  const required = contract.required_virtual_heads;
  const createHead = String(contract.ssl_host_create_head || "").trim();
  const startHead = String(contract.ssl_host_start_head || "").trim();
  const cleanupHead = String(contract.ssl_host_cleanup_head || "").trim();
  if (
    !Array.isArray(required) || !required.length ||
    required.some((head) => typeof head !== "string" || !head.trim()) ||
    !createHead || !startHead || !cleanupHead
  ) {
    throw new SSLLifecycleContractError("SSL lifecycle role map is incomplete");
  }
  const requiredHeads = [...new Set(required.map((head) => head.trim()))].sort();
  const device = contract.device_evidence;
  const reference = contract.reference_evidence;
  if (typeof device !== "object" || device === null || Array.isArray(device) || typeof reference !== "object" || reference === null || Array.isArray(reference)) {
    throw new SSLLifecycleContractError("SSL lifecycle evidence receipts are incomplete");
  }
  if (_buildSuffix(String(device.execution_build || "")) !== requested) {
    throw new SSLLifecycleContractError("device evidence build identity drift");
  }
  for (const field of ["framework_result_source_sha256", "framework_reference_source_sha256", "last_run_sha256", "raw_echo_sha256", "volume_artifact_sha256"]) {
    _hashField(device[field], `device_evidence.${field}`);
  }
  const clearRelative = String(reference.clear_source || "");
  const startManualRelative = String(reference.start_manual_source || "");
  const atlasRelative = String(reference.teardown_atlas || "");
  const clearPath = path.join(_ROOT, clearRelative);
  const startManualPath = path.join(_ROOT, startManualRelative);
  const atlasPath = path.join(_ROOT, atlasRelative);
  const clearRaw = _read(clearPath, { root: _ROOT, max_bytes: _MAX_REFERENCE_BYTES, label: "reference cleanup source" });
  const atlasRaw = _read(atlasPath, { root: _ROOT, max_bytes: 128 * 1024 * 1024, label: "command teardown atlas" });
  const startManualRaw = _read(startManualPath, { root: _ROOT, max_bytes: _MAX_REFERENCE_BYTES, label: "SSL start manual source" });
  if (sha256_bytes(clearRaw) !== _hashField(reference.clear_source_sha256, "reference_evidence.clear_source_sha256")) {
    throw new SSLLifecycleContractError("reference cleanup source identity drift");
  }
  if (sha256_bytes(startManualRaw) !== _hashField(reference.start_manual_source_sha256, "reference_evidence.start_manual_source_sha256")) {
    throw new SSLLifecycleContractError("SSL start manual source identity drift");
  }
  const cleanupLine = reference.cleanup_line;
  const lines = clearRaw.toString("utf8").split(/\r?\n/);
  if (
    typeof cleanupLine !== "number" || !Number.isInteger(cleanupLine) ||
    cleanupLine < 1 || cleanupLine > lines.length ||
    !lines[cleanupLine - 1].includes(cleanupHead)
  ) {
    throw new SSLLifecycleContractError("reference cleanup source no longer carries the object-scoped command");
  }
  const startManualLine = reference.start_manual_line;
  const startManualLines = startManualRaw.toString("utf8").split(/\r?\n/);
  if (
    typeof startManualLine !== "number" || !Number.isInteger(startManualLine) ||
    startManualLine < 1 || startManualLine > startManualLines.length ||
    !startManualLines[startManualLine - 1].includes(startHead)
  ) {
    throw new SSLLifecycleContractError("manual source no longer carries the SSL host start requirement");
  }
  let atlas: any;
  try {
    atlas = JSON.parse(atlasRaw.toString("utf8"));
  } catch {
    throw new SSLLifecycleContractError("command teardown atlas is invalid");
  }
  const atlasIdentity = (atlas.identity || {}).sha256;
  if (
    _hashField(atlasIdentity, "command_teardown_atlas.identity.sha256") !==
    _hashField(reference.teardown_atlas_identity_sha256, "reference_evidence.teardown_atlas_identity_sha256")
  ) {
    throw new SSLLifecycleContractError("command teardown atlas identity drift");
  }
  if (String(atlas.device_build || "") !== requested) {
    throw new SSLLifecycleContractError("command teardown atlas build identity drift");
  }
  const commands = atlas.commands;
  if (typeof commands !== "object" || commands === null || Array.isArray(commands)) {
    throw new SSLLifecycleContractError("command teardown atlas has no command map");
  }
  const createEntry = commands[createHead];
  if (typeof createEntry !== "object" || createEntry === null || Array.isArray(createEntry)) {
    throw new SSLLifecycleContractError("SSL host creation head is absent from the atlas");
  }
  if (typeof commands[startHead] !== "object" || commands[startHead] === null) {
    throw new SSLLifecycleContractError("SSL host start head is absent from the atlas");
  }
  if (String((createEntry.provenance || {}).clear_rule || "") !== String(reference.create_clear_rule_ref || "")) {
    throw new SSLLifecycleContractError("SSL host creation/cleanup reference drift");
  }
  for (const head of requiredHeads) {
    if (typeof commands[head] !== "object" || commands[head] === null) {
      throw new SSLLifecycleContractError(`certificate-required virtual head is absent from the atlas: ${JSON.stringify(head)}`);
    }
  }
  const receipts: Record<string, Record<string, string>> = {};
  if (verifyCommandTreeReceipts) {
    const { build_command_tree_resolver } = require("../ist_core/tools/device/emit_xlsx_tool");
    const [, , resolve] = build_command_tree_resolver({ device_build: requested });
    for (const [role, heads] of [
      ["required_virtual", requiredHeads],
      ["ssl_host_create", [createHead]],
      ["ssl_host_start", [startHead]],
      ["ssl_host_cleanup", [cleanupHead]],
    ] as Array<[string, string[]]>) {
      for (const head of heads) {
        const verdict = resolve(head);
        if (
          verdict.kind !== "hit" ||
          String(verdict.head || "") !== head ||
          String(verdict.device_build || "") !== requested ||
          String(verdict.origin || "") !== "vendor_xml"
        ) {
          throw new SSLLifecycleContractError(`${role} head does not resolve exactly in build ${requested}: ${JSON.stringify(head)}`);
        }
        receipts[head] = { role, src: String(verdict.src || ""), origin: String(verdict.origin || "") };
      }
    }
  } else {
    for (const [role, heads] of [
      ["required_virtual", requiredHeads],
      ["ssl_host_create", [createHead]],
      ["ssl_host_start", [startHead]],
    ] as Array<[string, string[]]>) {
      for (const head of heads) {
        const entry = commands[head];
        const xmlSources = (((entry || {}).xml || {}).src || []) as string[];
        if (typeof entry !== "object" || entry === null || String(entry.origin || "") !== "vendor_xml" || !xmlSources.length) {
          throw new SSLLifecycleContractError(`${role} head is not sealed by the verified atlas: ${JSON.stringify(head)}`);
        }
        receipts[head] = { role, src: String(xmlSources[0]), origin: "vendor_xml" };
      }
    }
    receipts[cleanupHead] = { role: "ssl_host_cleanup", src: `${clearRelative}:${cleanupLine}`, origin: "reference_clear_source" };
  }
  return {
    schema: SCHEMA,
    device_build: requested,
    required_virtual_heads: requiredHeads,
    ssl_host_create_head: createHead,
    ssl_host_start_head: startHead,
    ssl_host_cleanup_head: cleanupHead,
    preflight_transition_coverage: { [startHead]: createHead },
    source_sha256: sha256_bytes(raw),
    receipts,
    device_evidence: { ...device },
    reference_evidence: { ...reference },
  };
}
