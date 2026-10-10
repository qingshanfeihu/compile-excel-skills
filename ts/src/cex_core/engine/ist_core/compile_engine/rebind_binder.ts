export const REBINDABLE_VERDICT = "rebindable";
export const LOAD_BEARING_VERDICT = "load_bearing";
export const REBIND_VERDICTS = new Set([REBINDABLE_VERDICT, LOAD_BEARING_VERDICT]);

export class RebindBinderError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "RebindBinderError";
  }
}

function _validate_license_shape(license_: any, index: number): Record<string, any> | null {
  if (typeof license_ !== "object" || license_ === null || Array.isArray(license_)) return null;
  const author_literal = String(license_.author_literal ?? "").trim();
  const verdict = String(license_.verdict ?? "").trim();
  const occurrences = license_.occurrences;
  const constraints = license_.constraints;
  const reason = String(license_.reason ?? "").trim();
  if (
    !author_literal ||
    !REBIND_VERDICTS.has(verdict) ||
    !Array.isArray(occurrences) ||
    occurrences.some((item: any) => typeof item !== "string" || !item.trim()) ||
    typeof constraints !== "string" ||
    !reason
  ) {
    return null;
  }
  return {
    author_literal,
    verdict,
    occurrences: occurrences.map((item: string) => item.trim()),
    constraints,
    reason,
    _index: index,
  };
}

function _concretization_author_text_grounded(case_: Record<string, any>, author_text: string): boolean {
  const { ground_source_span } = require("../../case_compiler/mindmap_contract_projector");
  for (const step of case_.steps ?? []) {
    if (typeof step !== "object" || step === null) continue;
    if (ground_source_span(author_text, String(step.text ?? "")) !== null) {
      return true;
    }
  }
  return false;
}

function _validate_concretization_shape(item: any, case_: Record<string, any> | null = null): Record<string, any> | null {
  if (typeof item !== "object" || item === null || Array.isArray(item)) return null;
  const slot = String(item.slot ?? "").trim();
  const author_text = String(item.author_text ?? "").trim();
  const value = String(item.value ?? "").trim();
  const source = String(item.source ?? "").trim();
  const reason = String(item.reason ?? "").trim();
  if (!slot || !author_text || !value || !reason || !["command_tree", "manual"].includes(source)) {
    return null;
  }
  if (case_ !== null && case_.steps && !_concretization_author_text_grounded(case_, author_text)) {
    return null;
  }
  return { slot, author_text, value, source, reason };
}

export function validate_case_enhancement_fields(case_: Record<string, any>): string[] {
  const errors: string[] = [];
  const licenses = case_.rebind_licenses;
  if (licenses !== undefined && licenses !== null) {
    if (!Array.isArray(licenses)) {
      errors.push("rebind_licenses must be an array");
    } else {
      const parsed: Record<string, any>[] = [];
      for (let index = 0; index < licenses.length; index++) {
        const item = _validate_license_shape(licenses[index], index);
        if (item === null) {
          errors.push(
            `rebind_licenses[${index}] is invalid; expected author_literal, verdict=rebindable|load_bearing, occurrences[], string constraints, and reason`
          );
        } else {
          parsed.push(item);
        }
      }
      const literals = parsed.map((item) => item.author_literal);
      if (literals.length !== new Set(literals).size) {
        errors.push("rebind_licenses author_literal values must be unique");
      }
    }
  }
  const concretizations = case_.concretizations;
  if (concretizations !== undefined && concretizations !== null) {
    if (!Array.isArray(concretizations)) {
      errors.push("concretizations must be an array");
    } else {
      for (let index = 0; index < concretizations.length; index++) {
        const item = concretizations[index];
        const author_text =
          typeof item === "object" && item !== null ? String(item.author_text ?? "").trim() : "";
        if (_validate_concretization_shape(item, case_) === null) {
          if (author_text && case_.steps) {
            errors.push(
              `concretizations[${index}] author_text does not occur in any authored step, even with whitespace runs normalized`
            );
          } else {
            errors.push(
              `concretizations[${index}] is invalid; expected exactly slot, non-empty author_text grounded in the authored steps, value, source=command_tree|manual, reason`
            );
          }
        }
      }
    }
  }
  const proposal = case_.proposal;
  if (proposal !== undefined && proposal !== null) {
    if (!Array.isArray(proposal) || proposal.some((item: any) => typeof item !== "string" || !item.trim())) {
      errors.push("proposal must be an array of non-empty strings");
    }
  }
  return errors;
}
