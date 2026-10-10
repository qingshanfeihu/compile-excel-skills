import crypto from "node:crypto";

import { PyValueError } from "../../../_py";

export const SCHEMA = "ist.device-batch-result";
export const PREREQUISITE_RECEIPT_SCHEMA = "ist.device-prerequisite-receipt";
export const FAILURE_EVIDENCE_SCHEMA = "ist.device-batch-failure-evidence";
export const STATUSES = new Set(["completed", "device_busy", "env_pool_exhausted", "failed"]);
export const REASON_CODES = new Set(["completed", "device_busy", "env_pool_exhausted", "invalid_request", "environment_unavailable", "device_unreachable", "device_prerequisite_unmet", "bed_identity_mismatch", "artifact_identity_mismatch", "delivery_failed", "execution_failed", "session_desync", "result_channel_unavailable", "producer_protocol_error"]);
export const VERDICTS = new Set(["pass", "fail", "broken", "unknown"]);
export const ATTRIBUTIONS = new Set(["grammar_rejected", "unattributed"]);
const _AUTOID_RE = /^\d{18}$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _TASK_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
const _MAX_BYTES = 2 * 1024 * 1024;
export const MAX_ERROR_TEXT_CHARS = 1200;
const _TOP_KEYS = new Set(["schema", "status", "reason_code", "reason_zh", "error_text", "bed_host", "last_run_path", "counts", "alerts", "run_identity", "runtime_reverification", "cross_run", "crash_analysis", "verdicts", "guidance", "prerequisite_receipts", "failure_evidence"]);
const _COUNT_KEYS = new Set(["total", "pass", "fail", "broken", "unknown", "grammar_rejected", "unattributed"]);
const _ALERT_KEYS = new Set(["verified_runs_write_failed", "frozen_write_failed_autoids"]);
const _IDENTITY_KEYS = new Set(["run_id", "artifact_sha256", "bed_lease_id", "build", "module"]);
const _REVERIFY_KEYS = new Set(["autoid", "raw_device_verdict", "effective_verdict", "status", "reason", "completion_state"]);
const _CROSS_RUN_KEYS = new Set(["repeat_autoids", "transient_recur_autoids"]);
const _VERDICT_KEYS = new Set(["autoid", "verdict", "attribution", "reflow", "note"]);
const _PREREQUISITE_RECEIPT_KEYS = new Set(["schema", "autoid", "artifact_sha256", "bed_host", "run_id", "reason_code"]);
const _FAILURE_EVIDENCE_KEYS = new Set(["schema", "autoid", "task_id", "layer", "state", "source", "settle_attempts", "error_type", "evidence_file", "evidence_sha256"]);

function _loadsStrict(raw: string): any {
  return JSON.parse(raw, function (this: any, _key: string, value: any) {
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      const keys = Object.keys(value);
      if (new Set(keys).size !== keys.length) {
        throw new PyValueError("duplicate JSON key");
      }
    }
    if (typeof value === "number" && !Number.isFinite(value)) {
      throw new PyValueError("non-finite JSON constant");
    }
    return value;
  });
}

function _exactKeys(value: Record<string, any>, expected: Set<string>, label: string): void {
  const actual = new Set(Object.keys(value));
  if (actual.size !== expected.size || ![...expected].every((k) => actual.has(k))) {
    const missing = [...expected].filter((k) => !actual.has(k)).sort();
    const unknown = [...actual].filter((k) => !expected.has(k)).sort();
    throw new PyValueError(`${label} keys mismatch; missing=[${missing.map((k) => `'${k}'`).join(", ")}], unknown=[${unknown.map((k) => `'${k}'`).join(", ")}]`);
  }
}

function _text(value: any, label: string, nullable = false): void {
  if (nullable && (value === null || value === undefined)) return;
  if (typeof value !== "string") {
    throw new PyValueError(`${label} must be text${nullable ? " or null" : ""}`);
  }
}

function _autoidArray(value: any, label: string): void {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !_AUTOID_RE.test(item))) {
    throw new PyValueError(`${label} must be an array of 18-digit autoids`);
  }
}

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _isInt(v: any): boolean {
  return typeof v === "number" && Number.isInteger(v);
}

export function validate_device_prerequisite_receipts(
  receipts: any,
  opts: { expected_autoids?: Set<string> | null; artifact_sha256?: string; bed_host?: string; run_id?: string; require_nonempty?: boolean } = {},
): Array<Record<string, string>> {
  const expectedAutoids = opts.expected_autoids ?? null;
  const artifactSha256 = opts.artifact_sha256 ?? "";
  const bedHost = opts.bed_host ?? "";
  const runId = opts.run_id ?? "";
  const requireNonempty = opts.require_nonempty ?? true;
  if (!Array.isArray(receipts)) {
    throw new PyValueError("device prerequisite receipts must be an array");
  }
  if (requireNonempty && receipts.length === 0) {
    throw new PyValueError("device prerequisite receipt is required");
  }
  const normalized: Array<Record<string, string>> = [];
  const seenAutoids = new Set<string>();
  for (const [index, receipt] of receipts.entries()) {
    const label = `prerequisite_receipts[${index}]`;
    if (!_isMapping(receipt)) {
      throw new PyValueError(`${label} must be an object`);
    }
    _exactKeys(receipt, _PREREQUISITE_RECEIPT_KEYS, label);
    if (receipt.schema !== PREREQUISITE_RECEIPT_SCHEMA) {
      throw new PyValueError("invalid device prerequisite receipt schema");
    }
    const autoid = receipt.autoid;
    if (typeof autoid !== "string" || !_AUTOID_RE.test(autoid)) {
      throw new PyValueError("device prerequisite receipt autoid is invalid");
    }
    if (seenAutoids.has(autoid)) {
      throw new PyValueError("device prerequisite receipt autoids must be unique");
    }
    seenAutoids.add(autoid);
    const artifact = receipt.artifact_sha256;
    if (typeof artifact !== "string" || !_SHA256_RE.test(artifact)) {
      throw new PyValueError("device prerequisite receipt artifact is invalid");
    }
    for (const key of ["bed_host", "run_id"]) {
      const value = receipt[key];
      if (typeof value !== "string" || !value.trim()) {
        throw new PyValueError(`device prerequisite receipt ${key.replace(/_host$/, "")} is invalid`);
      }
    }
    if (receipt.reason_code !== "device_prerequisite_unmet") {
      throw new PyValueError("invalid device prerequisite receipt reason_code");
    }
    if (expectedAutoids !== null && !expectedAutoids.has(autoid)) {
      throw new PyValueError("device prerequisite receipt autoid binding mismatch");
    }
    if (artifactSha256 && artifact !== artifactSha256) {
      throw new PyValueError("device prerequisite receipt artifact binding mismatch");
    }
    if (bedHost && receipt.bed_host !== bedHost) {
      throw new PyValueError("device prerequisite receipt bed binding mismatch");
    }
    if (runId && receipt.run_id !== runId) {
      throw new PyValueError("device prerequisite receipt run binding mismatch");
    }
    const row: Record<string, string> = {};
    for (const key of Object.keys(receipt).sort()) {
      row[key] = String(receipt[key]);
    }
    normalized.push(row);
  }
  return normalized;
}

export function device_prerequisite_receipt_sha256(receipt: Record<string, any>): string {
  const normalized = validate_device_prerequisite_receipts([receipt])[0];
  const keys = Object.keys(normalized).sort();
  const canonical = "{" + keys.map((k) => JSON.stringify(k) + ":" + JSON.stringify(normalized[k])).join(",") + "}";
  return crypto.createHash("sha256").update(Buffer.from(canonical, "utf8")).digest("hex");
}

export function validate_device_failure_evidence(value: any): Array<Record<string, any>> {
  if (!Array.isArray(value)) {
    throw new PyValueError("device failure evidence must be an array");
  }
  const normalized: Array<Record<string, any>> = [];
  const seen = new Set<string>();
  for (const [index, item] of value.entries()) {
    const label = `failure_evidence[${index}]`;
    if (!_isMapping(item)) {
      throw new PyValueError(`${label} must be an object`);
    }
    _exactKeys(item, _FAILURE_EVIDENCE_KEYS, label);
    if (item.schema !== FAILURE_EVIDENCE_SCHEMA) {
      throw new PyValueError("invalid device failure evidence schema");
    }
    const autoid = item.autoid;
    if (typeof autoid !== "string" || !_AUTOID_RE.test(autoid)) {
      throw new PyValueError("device failure evidence autoid is invalid");
    }
    if (seen.has(autoid)) {
      throw new PyValueError("device failure evidence autoids must be unique");
    }
    seen.add(autoid);
    const taskId = item.task_id;
    if (typeof taskId !== "string" || !_TASK_ID_RE.test(taskId) || taskId.includes("..")) {
      throw new PyValueError("device failure evidence task_id is invalid");
    }
    if (item.layer !== "framework_result_channel" || !["query_error", "missing_after_done"].includes(item.state) || item.source !== "mysql") {
      throw new PyValueError("device failure evidence channel identity is invalid");
    }
    const attempts = item.settle_attempts;
    if (typeof attempts === "boolean" || !_isInt(attempts) || attempts < 0) {
      throw new PyValueError("device failure evidence settle_attempts is invalid");
    }
    const errorType = item.error_type;
    if (typeof errorType !== "string" || errorType.length > 120) {
      throw new PyValueError("device failure evidence error_type is invalid");
    }
    const evidenceFile = item.evidence_file;
    const evidenceSha256 = item.evidence_sha256;
    if (
      typeof evidenceFile !== "string" ||
      !["", "device_echo.raw.txt"].includes(evidenceFile) ||
      typeof evidenceSha256 !== "string" ||
      (evidenceSha256 !== "" && !_SHA256_RE.test(evidenceSha256)) ||
      Boolean(evidenceFile) !== Boolean(evidenceSha256)
    ) {
      throw new PyValueError("device failure evidence artifact identity is invalid");
    }
    normalized.push({ ...item });
  }
  return normalized;
}

export function parse_device_batch_result(raw: any): Record<string, any> {
  if (typeof raw !== "string") {
    throw new PyValueError("device batch result must be text");
  }
  if (!raw.trim() || Buffer.byteLength(raw, "utf8") > _MAX_BYTES) {
    throw new PyValueError("device batch result is empty or exceeds its byte budget");
  }
  let payload: any;
  try {
    payload = _loadsStrict(raw);
  } catch (exc) {
    throw new PyValueError("device batch result must be one complete JSON object");
  }
  if (!_isMapping(payload)) {
    throw new PyValueError("device batch result must be a JSON object");
  }
  _exactKeys(payload, _TOP_KEYS, "device batch result");
  if (payload.schema !== SCHEMA) {
    throw new PyValueError("invalid device batch result schema");
  }
  const status = payload.status;
  const reasonCode = payload.reason_code;
  if (!STATUSES.has(status)) {
    throw new PyValueError("invalid device batch status");
  }
  if (!REASON_CODES.has(reasonCode)) {
    throw new PyValueError("invalid device batch reason_code");
  }
  const allowedReasons: Record<string, Set<string>> = {
    completed: new Set(["completed"]),
    device_busy: new Set(["device_busy"]),
    env_pool_exhausted: new Set(["env_pool_exhausted"]),
    failed: new Set([...REASON_CODES].filter((c) => !["completed", "device_busy", "env_pool_exhausted"].includes(c))),
  };
  if (!allowedReasons[status].has(reasonCode)) {
    throw new PyValueError("device batch status/reason_code mismatch");
  }
  _text(payload.reason_zh, "reason_zh");
  _text(payload.error_text, "error_text");
  if (payload.error_text.length > MAX_ERROR_TEXT_CHARS) {
    throw new PyValueError("error_text exceeds its character budget");
  }
  _text(payload.bed_host, "bed_host", true);
  _text(payload.last_run_path, "last_run_path", true);
  const prerequisiteReceipts = validate_device_prerequisite_receipts(payload.prerequisite_receipts, { require_nonempty: false });
  if (reasonCode === "device_prerequisite_unmet") {
    if (prerequisiteReceipts.length === 0) {
      throw new PyValueError("device prerequisite receipt is required");
    }
  } else if (prerequisiteReceipts.length > 0) {
    throw new PyValueError("device prerequisite receipts require device_prerequisite_unmet");
  }
  const failureEvidence = validate_device_failure_evidence(payload.failure_evidence);
  if (reasonCode === "result_channel_unavailable") {
    if (failureEvidence.length === 0) {
      throw new PyValueError("result channel failure evidence is required");
    }
  } else if (failureEvidence.length > 0) {
    throw new PyValueError("device failure evidence requires result_channel_unavailable");
  }
  const counts = payload.counts;
  if (!_isMapping(counts)) {
    throw new PyValueError("counts must be an object");
  }
  _exactKeys(counts, _COUNT_KEYS, "counts");
  if (Object.values(counts).some((v) => typeof v === "boolean" || !_isInt(v) || (v as number) < 0)) {
    throw new PyValueError("counts values must be non-negative integers");
  }
  if (counts.total !== counts.pass + counts.fail + counts.broken + counts.unknown) {
    throw new PyValueError("counts total does not equal verdict counts");
  }
  const alerts = payload.alerts;
  if (!_isMapping(alerts)) {
    throw new PyValueError("alerts must be an object");
  }
  _exactKeys(alerts, _ALERT_KEYS, "alerts");
  _text(alerts.verified_runs_write_failed, "alerts.verified_runs_write_failed", true);
  _autoidArray(alerts.frozen_write_failed_autoids, "alerts.frozen_write_failed_autoids");
  const identity = payload.run_identity;
  if (identity !== null && identity !== undefined) {
    if (!_isMapping(identity)) {
      throw new PyValueError("run_identity must be an object or null");
    }
    _exactKeys(identity, _IDENTITY_KEYS, "run_identity");
    if (Object.values(identity).some((v) => typeof v !== "string" || !(v as string))) {
      throw new PyValueError("run_identity fields must be non-empty text");
    }
    if (!_SHA256_RE.test(identity.artifact_sha256)) {
      throw new PyValueError("run_identity artifact_sha256 must be lowercase sha256");
    }
  }
  const reverification = payload.runtime_reverification;
  if (!Array.isArray(reverification)) {
    throw new PyValueError("runtime_reverification must be an array");
  }
  for (const [index, item] of reverification.entries()) {
    if (!_isMapping(item)) {
      throw new PyValueError(`runtime_reverification[${index}] must be an object`);
    }
    _exactKeys(item, _REVERIFY_KEYS, `runtime_reverification[${index}]`);
    if (typeof item.autoid !== "string" || !_AUTOID_RE.test(item.autoid)) {
      throw new PyValueError("runtime_reverification autoid must be exactly 18 digits");
    }
    for (const key of [..._REVERIFY_KEYS].filter((k) => !["autoid", "raw_device_verdict", "effective_verdict"].includes(k))) {
      _text(item[key], `runtime_reverification.${key}`);
    }
    for (const key of ["raw_device_verdict", "effective_verdict"]) {
      _text(item[key], `runtime_reverification.${key}`, true);
    }
  }
  const crossRun = payload.cross_run;
  if (!_isMapping(crossRun)) {
    throw new PyValueError("cross_run must be an object");
  }
  _exactKeys(crossRun, _CROSS_RUN_KEYS, "cross_run");
  _autoidArray(crossRun.repeat_autoids, "cross_run.repeat_autoids");
  _autoidArray(crossRun.transient_recur_autoids, "cross_run.transient_recur_autoids");
  _text(payload.crash_analysis, "crash_analysis", true);
  const verdicts = payload.verdicts;
  if (!Array.isArray(verdicts)) {
    throw new PyValueError("verdicts must be an array");
  }
  const seenAutoids = new Set<string>();
  const observedCounts: Record<string, number> = { pass: 0, fail: 0, broken: 0, unknown: 0 };
  const observedAttributions: Record<string, number> = { grammar_rejected: 0, unattributed: 0 };
  for (const [index, item] of verdicts.entries()) {
    if (!_isMapping(item)) {
      throw new PyValueError(`verdicts[${index}] must be an object`);
    }
    _exactKeys(item, _VERDICT_KEYS, `verdicts[${index}]`);
    if (typeof item.autoid !== "string" || !_AUTOID_RE.test(item.autoid)) {
      throw new PyValueError("verdict autoid must be exactly 18 digits");
    }
    if (seenAutoids.has(item.autoid)) {
      throw new PyValueError("verdict autoids must be unique");
    }
    seenAutoids.add(item.autoid);
    if (!VERDICTS.has(item.verdict)) {
      throw new PyValueError("invalid verdict value");
    }
    observedCounts[item.verdict] += 1;
    if (item.attribution !== null && item.attribution !== undefined && !ATTRIBUTIONS.has(item.attribution)) {
      throw new PyValueError("invalid verdict attribution");
    }
    const hasAttribution = item.attribution !== null && item.attribution !== undefined;
    const hasReflow = item.reflow !== null && item.reflow !== undefined;
    if (item.verdict === "fail") {
      if (!hasAttribution || !ATTRIBUTIONS.has(item.attribution)) {
        throw new PyValueError("fail verdict requires a closed attribution");
      }
      observedAttributions[item.attribution] += 1;
    } else if (hasAttribution || hasReflow) {
      throw new PyValueError("non-fail verdict cannot carry attribution or reflow");
    }
    if (item.attribution === "grammar_rejected" && item.reflow !== "G") {
      throw new PyValueError("grammar_rejected verdict requires reflow G");
    }
    if (item.attribution === "unattributed" && hasReflow) {
      throw new PyValueError("unattributed verdict cannot carry reflow");
    }
    _text(item.reflow, "verdict.reflow", true);
    _text(item.note, "verdict.note");
  }
  if (verdicts.length !== counts.total) {
    throw new PyValueError("verdict row count does not equal counts.total");
  }
  if (Object.keys(observedCounts).some((key) => counts[key] !== observedCounts[key])) {
    throw new PyValueError("verdict rows do not match verdict counts");
  }
  if (Object.keys(observedAttributions).some((key) => counts[key] !== observedAttributions[key])) {
    throw new PyValueError("verdict rows do not match attribution counts");
  }
  const guidance = payload.guidance;
  if (!Array.isArray(guidance) || guidance.some((item) => typeof item !== "string")) {
    throw new PyValueError("guidance must be an array of text");
  }
  if (status === "completed") {
    if (!payload.last_run_path) {
      throw new PyValueError("completed result requires last_run_path");
    }
  } else if (counts.total || verdicts.length || payload.last_run_path) {
    throw new PyValueError("non-completed result cannot carry verdict artifacts");
  }
  return payload;
}

function _sortedJson(value: any, indent: number, level: number): string {
  const pad = "\n" + " ".repeat(indent * (level + 1));
  const padEnd = "\n" + " ".repeat(indent * level);
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    return "[" + pad + value.map((x) => _sortedJson(x, indent, level + 1)).join(",") + padEnd + "]";
  }
  const keys = Object.keys(value).sort();
  if (keys.length === 0) return "{}";
  return "{" + pad + keys.map((k) => JSON.stringify(k) + ": " + _sortedJson(value[k], indent, level + 1)).join(",") + padEnd + "}";
}

export function render_device_batch_result(payload: Record<string, any>): string {
  const raw = _sortedJson(payload, 2, 0);
  parse_device_batch_result(raw);
  return raw;
}

export function empty_device_batch_result(opts: {
  status: string;
  reason_code: string;
  reason_zh: string;
  error_text?: string;
  prerequisite_receipts?: Array<Record<string, any>> | null;
  failure_evidence?: Array<Record<string, any>> | null;
}): Record<string, any> {
  return {
    schema: SCHEMA,
    status: opts.status,
    reason_code: opts.reason_code,
    reason_zh: opts.reason_zh,
    error_text: opts.error_text ?? "",
    prerequisite_receipts: [...(opts.prerequisite_receipts ?? [])],
    failure_evidence: [...(opts.failure_evidence ?? [])],
    bed_host: null,
    last_run_path: null,
    counts: { total: 0, pass: 0, fail: 0, broken: 0, unknown: 0, grammar_rejected: 0, unattributed: 0 },
    alerts: { verified_runs_write_failed: null, frozen_write_failed_autoids: [] },
    run_identity: null,
    runtime_reverification: [],
    cross_run: { repeat_autoids: [], transient_recur_autoids: [] },
    crash_analysis: null,
    verdicts: [],
    guidance: [],
  };
}
