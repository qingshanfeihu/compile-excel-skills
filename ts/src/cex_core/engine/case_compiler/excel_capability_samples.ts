import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";
import {
  canonical_json as _sealedCanonicalJson,
  lexical_absolute as _sealedLexicalAbsolute,
  open_directory_nofollow as _sealedOpenDirectoryNofollow,
  read_regular_at_nofollow as _sealedReadRegularAtNofollow,
  sha256_bytes as _sealedSha256Bytes,
  validate_json_budget as _sealedValidateJsonBudget,
} from "./_sealed_io";

export const CAPABILITY_SAMPLES_SCHEMA = "ist.ide.capability-samples";
export const CAPABILITY_SAMPLES_PATH = path.join(_cex_data_path("engine"), "capability", "capability_samples.json");
export const CAPABILITY_SAMPLES_VERSION = 1;
export const MAX_CAPABILITY_SAMPLES_BYTES = 4 * 1024 * 1024;
export const MAX_SAMPLE_TEXT_CHARS = 2000;
export const MAX_CAPABILITIES = 8;
export const MAX_SAMPLES_PER_CAPABILITY = 6;
export const SAMPLE_BEHAVIOUR_CLASSES: Record<string, string> = {
  config: "配置",
  runtime: "运行时",
  status: "状态",
  statistics: "统计",
  unclassified: "未分类",
};
export const BUCKET_CAPABILITY: Record<string, string[]> = {
  exp_recipe: ["capability_value", "capability_state", "capability_aggregate"],
  step_recipe: ["config_command"],
};
export const CAPABILITY_SAMPLE_ROLE_ORDER: Record<string, number> = { triggering: 0, config: 1, observation: 2, other: 3 };
export const CAPABILITY_CONSUMER_KEYS = ["mindmap", "behaviour", "mechanical", "structure"];
export const CAPABILITY_AXIS_LABELS: Record<string, string> = { capability_class: "能力类", value_axis: "取值轴", state_axis: "状态轴" };
const _ROLE_LIMITS: Record<string, number> = { observation: 3, config: 2, triggering: 1, other: 1 };
const _MAX_CAPABILITY_TEXT_CHARS = 2000;
const _OBSERVATION_CHARACTERISTIC_CLASSES = new Set(["runtime_behaviour", "observation_semantics", "prerequisites"]);
const _FULL_SHA_RE = /^[0-9a-f]{64}$/;
const _MAX_REFERENCE_SPAN_CHARS = 400;
const _MAX_DIGEST_LIST = 64;
let _capability_samples_cache: Record<string, any> | null = null;

function _sha256(value: any): string {
  return crypto.createHash("sha256").update(_sealedCanonicalJson(value)).digest("hex");
}

function _expect_value_sha(expected: any): string {
  const value = expected?.["value"];
  if (value === undefined || value === null || String(value).trim() === "") return "";
  return _sha256(String(value).trim());
}

function _expect_semantic_shape(entry: any, expected: any): Record<string, any> {
  let value = expected?.["value"];
  value = String(value ?? "").trim();
  const semanticKey = String(entry?.["semantic_key"] ?? "").trim();
  const authoredStep = entry?.["authored_step"];
  const out: Record<string, any> = {};
  if (semanticKey) out["semantic_key"] = semanticKey;
  if (typeof authoredStep === "number" && authoredStep >= 1) out["authored_step"] = authoredStep;
  if (value) out["value_sha256"] = _sha256(value);
  return out;
}

export function sanitize_sample_text(value: any, limit: number = MAX_SAMPLE_TEXT_CHARS): string {
  return String(value ?? "").trim().slice(0, limit);
}

export function capability_sample_text(entry: any): string {
  const value = entry?.["value"];
  const text = String(value ?? "").trim();
  return text ? sanitize_sample_text(text) : "";
}

export function capability_sample_id(entry: any): string {
  const value = entry?.["sample_id"];
  const text = String(value ?? "").trim();
  return text && text.length <= 96 ? text : "";
}

export function normalize_capability_sample(entry: any): Record<string, any> | null {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) return null;
  const sampleId = capability_sample_id(entry);
  const text = capability_sample_text(entry);
  const capability = String(entry["capability"] ?? "").trim();
  const capabilityClass = String(entry["capability_class"] ?? "").trim();
  const roleRaw = String(entry["sample_role"] ?? "").trim();
  const role = CAPABILITY_SAMPLE_ROLE_ORDER.hasOwnProperty(roleRaw) ? roleRaw : "other";
  const reference = entry["reference"] && typeof entry["reference"] === "object" && !Array.isArray(entry["reference"]) ? entry["reference"] : {};
  const expectValueSha = _expect_value_sha(entry["expect"] ?? {});
  const semanticShape = _expect_semantic_shape(entry, entry["expect"] ?? {});
  const roles: Record<string, any> = {};
  const expectVal = reference["expect_value"];
  if (typeof expectVal === "string" && expectVal) roles["expect_value"] = expectVal;
  const expectSpan = reference["expect_span"];
  if (typeof expectSpan === "string" && expectSpan.trim()) roles["expect_span"] = sanitize_sample_text(expectSpan, _MAX_REFERENCE_SPAN_CHARS);
  if (expectValueSha) roles["expect_value_sha256"] = expectValueSha;
  if (Object.keys(semanticShape).length) roles["expect_semantic_shape"] = semanticShape;
  if (!capability || !capabilityClass || !text || !sampleId) return null;
  return { capability, capability_class: capabilityClass, sample_role: role, sample_id: sampleId, text, reference: roles };
}

function _sorted_sample_digests(samples: Iterable<Record<string, any>>): string[] {
  const seen = new Set<string>();
  for (const row of samples) {
    const canonical = _sealedCanonicalJson(row).toString("utf8");
    seen.add(_sha256(canonical));
  }
  return Array.from(seen).sort().slice(0, _MAX_DIGEST_LIST);
}

function _reference_projection(entry: any): Record<string, any> {
  const roles = entry["reference"] && typeof entry["reference"] === "object" && !Array.isArray(entry["reference"]) ? entry["reference"] : {};
  const out: Record<string, any> = {};
  if (typeof roles["expect_value"] === "string" && roles["expect_value"]) out["expect_value"] = roles["expect_value"];
  if (typeof roles["expect_span"] === "string" && roles["expect_span"].trim()) {
    out["expect_span"] = sanitize_sample_text(roles["expect_span"], _MAX_REFERENCE_SPAN_CHARS);
  }
  if (typeof roles["expect_value_sha256"] === "string" && roles["expect_value_sha256"]) out["expect_value_sha256"] = roles["expect_value_sha256"];
  const shape = roles["expect_semantic_shape"];
  if (shape && typeof shape === "object" && !Array.isArray(shape)) {
    const keys = ["authored_step", "semantic_key", "value_sha256"];
    const projection: Record<string, any> = {};
    for (const key of keys) {
      const value = shape[key];
      if (key === "authored_step" && typeof value === "number" && value >= 1) projection[key] = value;
      if (key !== "authored_step" && typeof value === "string" && value.trim()) projection[key] = value.trim();
    }
    if (Object.keys(projection).length) out["expect_semantic_shape"] = projection;
  }
  return out;
}

function _consumer_ready(reference: Record<string, any>): boolean {
  return Object.keys(reference).length > 0;
}

function _normalize_verification_axes(raw: any, capability: string): Record<string, any> | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const out: Record<string, any> = {};
  const valueAxis = raw["value_axis"];
  if (typeof valueAxis === "string" && valueAxis.trim()) out["value_axis"] = valueAxis.trim();
  const stateAxis = raw["state_axis"];
  if (typeof stateAxis === "string" && stateAxis.trim()) out["state_axis"] = stateAxis.trim();
  return Object.keys(out).length ? out : null;
}

function _sample_passport_row(row: any): Record<string, any> | null {
  const sample = normalize_capability_sample(row);
  if (sample === null) return null;
  const capability = sample["capability"];
  const verificationAxes = _normalize_verification_axes(row?.["verification_axes"], capability);
  const record: Record<string, any> = {
    capability,
    capability_class: sample["capability_class"],
    sample_role: sample["sample_role"],
    sample_id: sample["sample_id"],
    text_sha256: _sha256(sample["text"]),
    reference: _reference_projection(row),
  };
  if (verificationAxes) record["verification_axes"] = verificationAxes;
  const identitySha = _sealedSha256Bytes(_sealedCanonicalJson(record));
  return { ...record, sample_identity_sha256: identitySha };
}

function _aggregate_consumer_digests(rows: Record<string, any>[]): Record<string, any> {
  const digests: Record<string, any> = {};
  for (const row of rows) {
    for (const key of CAPABILITY_CONSUMER_KEYS) {
      const digest = String(row?.[key] ?? "").trim();
      if (digest) digests[key] = digest;
    }
  }
  const extras: Record<string, any> = {};
  for (const row of rows) {
    for (const [key, value] of Object.entries(row)) {
      if (CAPABILITY_CONSUMER_KEYS.includes(key) || key === "sample_digests" || key === "sha256") continue;
      extras[key] = value;
    }
  }
  const bySource: Record<string, any> = {};
  const byClass: Record<string, any> = {};
  for (const row of rows) {
    const source = String(row?.["source"] ?? "").trim();
    if (source) bySource[source] = (bySource[source] ?? 0) + 1;
    const klass = String(row?.["capability_class"] ?? "").trim();
    if (klass) byClass[klass] = (byClass[klass] ?? 0) + 1;
  }
  const out: Record<string, any> = { ...digests, ...extras, sample_digests: _sorted_sample_digests(rows) };
  if (Object.keys(bySource).length) out["by_source"] = Object.fromEntries(Object.entries(bySource).sort());
  if (Object.keys(byClass).length) out["by_class"] = Object.fromEntries(Object.entries(byClass).sort());
  return out;
}

function _normalize_consumer_digests(rows: Record<string, any>[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of rows) {
    for (const key of CAPABILITY_CONSUMER_KEYS) {
      const value = String(row?.[key] ?? "").trim();
      if (value && _FULL_SHA_RE.test(value)) out[key] = value;
    }
  }
  return out;
}

export function load_capability_samples(force: boolean = false): Record<string, any> | null {
  if (_capability_samples_cache !== null && !force) return _capability_samples_cache;
  let raw: Buffer;
  try {
    raw = fs.readFileSync(CAPABILITY_SAMPLES_PATH);
  } catch {
    _capability_samples_cache = null;
    return null;
  }
  try {
    _sealedValidateJsonBudget(raw, { errorType: Error, message: "capability samples exceed the JSON structure budget", maxTokens: 500000 });
  } catch {
    _capability_samples_cache = null;
    return null;
  }
  let payload: any;
  try {
    payload = JSON.parse(raw.toString("utf8"));
  } catch {
    _capability_samples_cache = null;
    return null;
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload) || payload["schema"] !== CAPABILITY_SAMPLES_SCHEMA) {
    _capability_samples_cache = null;
    return null;
  }
  const rows = Array.isArray(payload["capabilities"]) ? payload["capabilities"] : [];
  const capabilities = rows.filter((r: any) => r && typeof r === "object" && !Array.isArray(r) && typeof r["capability"] === "string" && r["capability"].trim());
  _capability_samples_cache = { ...payload, capabilities };
  return _capability_samples_cache;
}

export function capability_samples_payload(): Record<string, any> {
  return load_capability_samples() ?? { schema: CAPABILITY_SAMPLES_SCHEMA, version: CAPABILITY_SAMPLES_VERSION, capabilities: [] };
}

export function capability_samples_passport(): Record<string, any> {
  const payload = load_capability_samples();
  const rows = payload?.["capabilities"] ?? [];
  const samples = rows.map(_sample_passport_row).filter((r: any) => r !== null);
  const digest = _sealedSha256Bytes(_sealedCanonicalJson(samples));
  return {
    schema: "ist.ide.capability-samples-passport",
    version: CAPABILITY_SAMPLES_VERSION,
    sample_count: samples.length,
    digest,
    samples,
  };
}

export function capabilities_for_bucket(bucket: string): Record<string, any>[] {
  const payload = capability_samples_payload();
  const rows = payload["capabilities"] ?? [];
  const allowed = BUCKET_CAPABILITY[bucket] ?? BUCKET_CAPABILITY["exp_recipe"];
  const filtered = rows
    .map((row: any) => {
      const normalized = normalize_capability_sample(row);
      if (normalized === null) return null;
      const capability = String(row["capability"] ?? "");
      return { ...normalized, capability };
    })
    .filter((row: any) => row !== null && allowed.includes(row["capability"]));
  const grouped: Record<string, Record<string, any>[]> = {};
  for (const row of filtered) {
    const cap = row["capability"];
    if (!grouped[cap]) grouped[cap] = [];
    if (grouped[cap].length < MAX_SAMPLES_PER_CAPABILITY) grouped[cap].push(row);
  }
  const flattened = Object.values(grouped).flat();
  return flattened.slice(0, MAX_CAPABILITIES * MAX_SAMPLES_PER_CAPABILITY);
}

export function capability_sample_reference_payload(sample: Record<string, any>): Record<string, any> {
  const reference = sample["reference"] && typeof sample["reference"] === "object" && !Array.isArray(sample["reference"]) ? sample["reference"] : {};
  const out: Record<string, any> = {};
  const expectValue = reference["expect_value"];
  if (typeof expectValue === "string" && expectValue) out["expect_value"] = expectValue;
  const expectSpan = reference["expect_span"];
  if (typeof expectSpan === "string" && expectSpan.trim()) out["expect_span"] = sanitize_sample_text(expectSpan, _MAX_REFERENCE_SPAN_CHARS);
  const expectValueSha = reference["expect_value_sha256"];
  if (typeof expectValueSha === "string" && expectValueSha && _FULL_SHA_RE.test(expectValueSha)) out["expect_value_sha256"] = expectValueSha;
  const semanticShape = reference["expect_semantic_shape"];
  if (semanticShape && typeof semanticShape === "object" && !Array.isArray(semanticShape)) {
    const keys = ["authored_step", "semantic_key", "value_sha256"];
    const projection: Record<string, any> = {};
    for (const key of keys) {
      const value = semanticShape[key];
      if (key === "authored_step" && typeof value === "number" && value >= 1) projection[key] = value;
      if (key !== "authored_step" && typeof value === "string" && value.trim()) projection[key] = value.trim();
    }
    if (Object.keys(projection).length) out["expect_semantic_shape"] = projection;
  }
  return out;
}

export function _validate_capability_sample_rows(payload: Record<string, any>): Record<string, any> | null {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
  if (String(payload["schema"] ?? "") !== CAPABILITY_SAMPLES_SCHEMA) return null;
  if (!Number.isInteger(payload["version"]) || payload["version"] !== CAPABILITY_SAMPLES_VERSION) return null;
  const rows = payload["capabilities"];
  if (!Array.isArray(rows)) return null;
  const out: Record<string, any>[] = [];
  for (const row of rows) {
    const sample = normalize_capability_sample(row);
    if (sample === null) return null;
    out.push({ ...sample, verification_axes: _normalize_verification_axes(row?.["verification_axes"], sample["capability"]) });
  }
  return { ...payload, capabilities: out };
}
