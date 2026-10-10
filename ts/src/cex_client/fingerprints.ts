import crypto from "node:crypto";

export const INIT_KEY = "__init__";
const _FIELDS = ["e", "f", "g", "h", "i"] as const;

export function canonicalJson(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "number" || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonicalJson(obj[k])).join(",") + "}";
}

function _canonicalSha256(value: unknown): string {
  return crypto.createHash("sha256").update(canonicalJson(value), "utf8").digest("hex");
}

function _field(step: Record<string, unknown>, key: string): string {
  for (const name of [key.toUpperCase(), key]) {
    if (name in step && step[name] !== null && step[name] !== undefined) {
      return String(step[name]);
    }
  }
  return "";
}

export function normalizeStep(step: unknown): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (typeof step !== "object" || step === null || Array.isArray(step)) {
    for (const key of _FIELDS) out[key] = "";
    return out;
  }
  const s = step as Record<string, unknown>;
  for (const key of _FIELDS) out[key] = _field(s, key);
  const source = s.source;
  if (typeof source === "object" && source !== null && !Array.isArray(source) &&
      ("kind" in source || "ref" in source)) {
    out.source = {
      kind: String((source as Record<string, unknown>).kind ?? ""),
      ref: String((source as Record<string, unknown>).ref ?? ""),
    };
  }
  return out;
}

export function caseFingerprints(casesDoc: Record<string, unknown>): Record<string, string> {
  const doc = typeof casesDoc === "object" && casesDoc !== null && !Array.isArray(casesDoc) ? casesDoc : {};
  const out: Record<string, string> = {};
  for (const case_ of (doc.cases as unknown[]) ?? []) {
    if (typeof case_ !== "object" || case_ === null) continue;
    const autoid = String((case_ as Record<string, unknown>).autoid ?? "").trim();
    if (autoid) {
      const steps = ((case_ as Record<string, unknown>).steps as unknown[]) ?? [];
      out[autoid] = _canonicalSha256(steps.map(normalizeStep));
    }
  }
  out[INIT_KEY] = _canonicalSha256(doc.init_commands ?? []);
  return out;
}

export const case_fingerprints = caseFingerprints;
