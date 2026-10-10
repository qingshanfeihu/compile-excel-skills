import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.case_compiler.rule_registry");

export const SCHEMA = "ist.ide.rule-registry";
const _REGISTRY_PATH = path.join(_cex_data_path(""), "knowledge", "data", "compile_ref", "rule_registry.json");

export class RuleRegistryUnavailable extends Error {}

let _cache: Record<string, any> | null = null;

function _canonicalJson(value: any): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(_canonicalJson).join(",") + "]";
  const keys = Object.keys(value).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + _canonicalJson(value[k])).join(",") + "}";
}

function _load(): Record<string, any> {
  if (_cache !== null) return _cache;
  let payload: any;
  try {
    payload = JSON.parse(fs.readFileSync(_REGISTRY_PATH, "utf8"));
  } catch (exc: any) {
    throw new RuleRegistryUnavailable(`rule registry unreadable: ${exc?.constructor?.name || "Error"}`);
  }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload) || payload.schema !== SCHEMA) {
    throw new RuleRegistryUnavailable("rule registry schema mismatch");
  }
  const body = { schema: payload.schema, rules: payload.rules };
  const recomputed = crypto.createHash("sha256").update(Buffer.from(_canonicalJson(body), "utf8")).digest("hex");
  const meta = payload._meta || {};
  if (recomputed !== String(meta.content_sha256 || "")) {
    throw new RuleRegistryUnavailable("rule registry content drifted from its generator output");
  }
  _cache = payload;
  return payload;
}

export function rule_registry_cache_clear(): void {
  _cache = null;
}

export function all_rule_ids(): string[] {
  return ((_load().rules || []) as any[]).map((r) => String(r.rule_id || ""));
}

export function get_rule(rule_id: string): Record<string, any> | null {
  for (const rule of (_load().rules || []) as any[]) {
    if (String(rule.rule_id || "") === String(rule_id || "")) {
      return { ...rule };
    }
  }
  return null;
}

function _similarity(a: string, b: string): number {
  // difflib-style ratio
  const la = a.length;
  const lb = b.length;
  if (!la && !lb) return 1;
  if (!la || !lb) return 0;
  const dp: number[][] = Array.from({ length: la + 1 }, () => new Array(lb + 1).fill(0));
  for (let i = 1; i <= la; i++) {
    for (let j = 1; j <= lb; j++) {
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }
  return (2 * dp[la][lb]) / (la + lb);
}

export function nearest_candidates(rule_id: string, limit = 3): string[] {
  const ids = all_rule_ids();
  const target = String(rule_id || "");
  return ids
    .map((id) => [id, _similarity(target, id)] as [string, number])
    .filter(([, s]) => s >= 0.4)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([id]) => id);
}

export function applicability_error(rule_id: string, capability_family: string, verification_shape = ""): string {
  const rule = get_rule(rule_id);
  if (rule === null) {
    const hint = nearest_candidates(rule_id);
    return (
      `selected_rule_id ${JSON.stringify(rule_id)} is not in the rule registry` +
      (hint.length ? `; nearest candidates: ${JSON.stringify(hint)}` : "")
    );
  }
  const applicability = rule.applicability || {};
  const families = (applicability.capability_families || []) as string[];
  if (families.length && !families.includes(String(capability_family || ""))) {
    return `rule ${JSON.stringify(rule_id)} does not apply to capability family ${JSON.stringify(capability_family)}; applicable families: ${JSON.stringify(families)}`;
  }
  const shapes = (applicability.verification_shapes || []) as string[];
  if (shapes.length && verification_shape && !shapes.includes(verification_shape)) {
    return `rule ${JSON.stringify(rule_id)} does not apply to verification shape ${JSON.stringify(verification_shape)}; applicable shapes: ${JSON.stringify(shapes)}`;
  }
  return "";
}

export function rule_snapshot(rule_id: string, capability_family: string): Record<string, any> {
  const rule = get_rule(rule_id) || {};
  const familyStatus = rule.family_status || {};
  const status = String(familyStatus[String(capability_family || "")] || rule.status || "");
  return {
    rule_id: String(rule.rule_id || rule_id),
    name_zh: String(rule.name_zh || ""),
    status,
    zh_template: String(rule.zh_template || ""),
  };
}
