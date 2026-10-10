import crypto from "node:crypto";
import { read_regular_nofollow } from "../../case_compiler/_sealed_io";
import { AUTHOR_RULE_PATH } from "../../case_compiler/criterion_author_rules";

export const AXES: Record<string, string> = {
  mindmap_source_sha256: "脑图源",
  governing_spec_status_sha256: "管辖SPEC",
  defect_spec_status_sha256: "DefectSpec",
  criterion_rules_sha256: "判据规则",
};

export function criterion_rules_sha256(): string | null {
  try {
    const raw = read_regular_nofollow(AUTHOR_RULE_PATH, {
      errorType: ValueError,
      invalid_message: "criterion rule path is invalid",
      directory_message: "criterion rule directory is unavailable",
      open_message: "criterion rules are unavailable",
      bounds_message: "criterion rules exceed the byte budget",
      changed_message: "criterion rules changed while reading",
      max_bytes: 32 * 1024 * 1024,
      min_bytes: 0,
    }) as Buffer;
    return crypto.createHash("sha256").update(raw).digest("hex");
  } catch {
    return null;
  }
}

export function compare_axes(previous: Record<string, any>, current: Record<string, any>): Record<string, any> {
  const changed: string[] = [];
  const unverified: string[] = [];
  for (const field of Object.keys(AXES)) {
    const old = previous[field];
    const new_ = current[field];
    if (![old, new_].every((v) => typeof v === "string" && /^[0-9a-f]{64}$/.test(v))) {
      unverified.push(field);
    } else if (old !== new_) {
      changed.push(field);
    }
  }
  return {
    changed_axes: changed,
    unverified_axes: unverified,
    error_text:
      "重封身份对照：变化轴=" +
      (changed.map((x) => AXES[x]).join("、") || "无已证变化轴") +
      "；未核轴=" +
      (unverified.map((x) => AXES[x]).join("、") || "无"),
  };
}

export function stamp_receipt(receipt: Record<string, any>, facts: Record<string, any>[]): Record<string, any> {
  const current = { ...receipt };
  current.criterion_rules_sha256 = criterion_rules_sha256();
  const previous = facts
    .slice()
    .reverse()
    .find((row) => row.ev === "recompose_done") ?? {};
  Object.assign(current, compare_axes(previous, current));
  return current;
}

class ValueError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "ValueError";
  }
}
