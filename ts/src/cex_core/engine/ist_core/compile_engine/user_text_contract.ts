export const USER_TEXT_VALIDATION_SCHEMA = "ist.user-text-validation";

export interface InternalTermViolation {
  code: "internal_term_in_user_text";
  field: string;
  terms: string[];
}

export interface UserTextValidationResult {
  schema: "ist.user-text-validation";
  accepted: boolean;
  violations: InternalTermViolation[];
}

let _INTERNAL_USER_TEXT_TERMS: Set<string> | null = null;

function _internal_user_text_terms(): Set<string> {
  if (_INTERNAL_USER_TEXT_TERMS !== null) return _INTERNAL_USER_TEXT_TERMS;
  const taxonomy = require("./blocking_taxonomy");
  const render = require("./render");
  const views = require("./views");
  const stateNames = Object.keys(views).filter((name) => name.startsWith("S_"));
  const words = new Set<string>();
  for (const name of stateNames) {
    words.add(String(views[name] ?? ""));
  }
  for (const name of stateNames) {
    words.add(name);
  }
  for (const cls of taxonomy.BLOCKING_CLASSES) words.add(cls);
  for (const cls of taxonomy.ABANDON_CLASSES) words.add(cls);
  words.add(taxonomy.B_UNCLASSIFIED);
  words.add(taxonomy.NOT_OBJECTIVE);
  for (const translations of [render.STATUS_CN, render.DISP_CN, render.SHAPE_CN, render.ACTION_CN, render.CTX_CN]) {
    for (const term of Object.keys(translations)) {
      words.add(String(term));
    }
  }
  for (const term of [
    "ask_panel",
    "adopted",
    "not_run",
    "gate_disabled",
    "writeback_failed",
    "rollback_failed",
    "emit_invalid",
    "report_mismatch",
    "delivery_incomplete",
    "needs_decision",
    "needs_decision.json",
    "manifest.json",
    "mechanical_case.json",
    "authoring_failure",
    "authoring_exhausted",
  ]) {
    words.add(term);
  }
  _INTERNAL_USER_TEXT_TERMS = new Set([...words].filter(Boolean));
  return _INTERNAL_USER_TEXT_TERMS;
}

export function internal_term_hits(text: string): string[] {
  const source = String(text ?? "");
  const hits: string[] = [];
  for (const term of _internal_user_text_terms()) {
    const pattern = new RegExp(`(?<![A-Za-z0-9_])${escapeRegExp(term)}(?![A-Za-z0-9_])`);
    if (pattern.test(source)) {
      hits.push(term);
    }
  }
  return hits.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()) || a.localeCompare(b));
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function validate_user_facing_text(fields: Record<string, any>): UserTextValidationResult {
  const violations: InternalTermViolation[] = [];
  for (const [field, value] of Object.entries(fields)) {
    const terms = internal_term_hits(String(value ?? ""));
    if (terms.length) {
      violations.push({ code: "internal_term_in_user_text", field: String(field), terms });
    }
  }
  return { schema: USER_TEXT_VALIDATION_SCHEMA, accepted: violations.length === 0, violations };
}
