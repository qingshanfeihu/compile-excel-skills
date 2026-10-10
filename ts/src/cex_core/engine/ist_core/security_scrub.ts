import crypto from "node:crypto";

import {
  scrub_text as _base_scrub_text,
  scrub_disclosure_text as _base_scrub_disclosure_text,
} from "../../security_scrub";
import { _cex_data_path } from "../_root";

export function scrub_text(text: any, opts: { scrub_paths?: boolean } = {}): string {
  return _base_scrub_text(text, opts);
}

export function scrub_disclosure_text(text: any, opts: { scrub_paths?: boolean } = {}): string {
  return _base_scrub_disclosure_text(text, opts);
}

const _SENSITIVE_KEY_RE = /(?:password|passwd|pwd|secret|token|authorization|cookie|api[_-]?key|apikey|access[_-]?key|private[_-]?key|credential|community|jumphost[_-]?pass|(?<![a-z])pin(?![a-z])|密码|口令|令牌|密钥|凭据)/i;
const _METRIC_AMBIGUOUS_KEY_RE = /(?:token|credential)/i;
const _STRONG_SECRET_KEY_RE = /(?:password|passwd|pwd|(?<![a-z])pin(?![a-z])|private[_-]?key|jumphost[_-]?pass|密码|口令)/i;
const _SHA256_HEX_RE = /^[0-9A-Fa-f]{64}$/;

const _BUSINESS_TOKENS = new Set(["auto_block", "author_definition_gap_disclosed", "batch_abandon", "batch_use_case", "batch_use_xml", "case_terminal_static_void", "confirm", "continue", "correct", "defect", "defect_conditional", "deesc_defect", "deesc_engineering_fault", "deesc_keep", "deesc_rebed", "deesc_reswitch", "deesc_retry", "downgrade", "keep", "reflow_tau", "reorder", "resume", "retry", "stop", "suspend"]);
const _NON_SECRET_CREDENTIAL_KEYS = new Set(["bed_lease_id", "credential_refs", "credential_valid", "lint_credential_id", "option_tokens", "tokens", "tokens_in", "tokens_out"]);
const _OVERRIDE_PROJECTION_KEYS = new Set(["override_schema", "override_class", "override_token_sha256"]);

let _PROJECT_ROOT: string | null = null;

function _projectRoot(): string {
  if (_PROJECT_ROOT === null) {
    _PROJECT_ROOT = String(_cex_data_path(""));
  }
  return _PROJECT_ROOT;
}

function _scrub_sha256_identity(value: any, opts: { scrub_paths: boolean }): string {
  if (typeof value !== "string") {
    return "****";
  }
  const scrubbed = scrub_text(value, opts);
  if (scrubbed !== value) {
    return "****";
  }
  return _SHA256_HEX_RE.test(value) ? value : "****";
}

function _closed_override_projection(value: Record<string, any>): Record<string, string> {
  if (String(value.ev ?? "") !== "decision") {
    return {};
  }
  const token = value.token;
  if (typeof token !== "string" || !token.startsWith("override:")) {
    return {};
  }
  try {
    const { project_override_decision } = require("./compile_engine/blocking_taxonomy");
    return project_override_decision(token);
  } catch {
    return {};
  }
}

export function scrub_value(value: any, opts: { scrub_paths?: boolean } = {}): any {
  const scrubPaths = opts.scrub_paths ?? true;
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, any>;
    const overrideProjection = _closed_override_projection(record);
    const cleaned: Record<string, any> = {};
    for (const [key, item] of Object.entries(record)) {
      const cleanedKey = typeof key === "string" ? scrub_text(key, { scrub_paths: scrubPaths }) : key;
      if (String(key) === "token" && _BUSINESS_TOKENS.has(String(item ?? ""))) {
        cleaned[cleanedKey] = String(item);
      } else if (["mutation_credential_sha256", "lint_credential_sha256", "override_token_sha256"].includes(String(key))) {
        if (String(key) === "lint_credential_sha256" && item !== null && typeof item === "object" && !Array.isArray(item)) {
          const inner: Record<string, string> = {};
          for (const [identity, digest] of Object.entries(item as Record<string, any>)) {
            inner[scrub_text(String(identity), { scrub_paths: scrubPaths })] = _scrub_sha256_identity(digest, { scrub_paths: scrubPaths });
          }
          cleaned[cleanedKey] = inner;
        } else {
          cleaned[cleanedKey] = _scrub_sha256_identity(item, { scrub_paths: scrubPaths });
        }
      } else if (_NON_SECRET_CREDENTIAL_KEYS.has(String(key))) {
        cleaned[cleanedKey] = scrub_value(item, { scrub_paths: scrubPaths });
      } else if (_SENSITIVE_KEY_RE.test(String(key))) {
        if (
          _METRIC_AMBIGUOUS_KEY_RE.test(String(key)) &&
          !_STRONG_SECRET_KEY_RE.test(String(key)) &&
          (typeof item === "boolean" || typeof item === "number")
        ) {
          cleaned[cleanedKey] = item;
        } else {
          cleaned[cleanedKey] = "****";
        }
      } else {
        cleaned[cleanedKey] = scrub_value(item, { scrub_paths: scrubPaths });
      }
    }
    if (Object.keys(overrideProjection).length > 0) {
      Object.assign(cleaned, overrideProjection);
    } else if (
      String(record.ev ?? "") === "decision" &&
      "token" in record &&
      String(record.token ?? "") !== "****"
    ) {
      for (const key of _OVERRIDE_PROJECTION_KEYS) {
        delete cleaned[key];
      }
    }
    return cleaned;
  }
  if (Array.isArray(value)) {
    return value.map((item) => scrub_value(item, { scrub_paths: scrubPaths }));
  }
  if (typeof value === "string") {
    return scrub_text(value, { scrub_paths: scrubPaths });
  }
  return value;
}

export function canonical_persisted_value(value: any): any {
  return scrub_value(value, { scrub_paths: false });
}

export function persisted_surface_sha256(value: any): string {
  const payload = Buffer.from(JSON.stringify(value), "utf8");
  return crypto.createHash("sha256").update(payload).digest("hex");
}
