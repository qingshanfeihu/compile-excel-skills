import { GP_CODES } from "./step_graph";

export const STRUCTURAL_ADVISORY_CODES = new Set([
  "ambiguous_observation_binding",
  "driver_no_declared_path_author_sourced",
  "line_anchor_window_unverified",
  "config_existence_only",
  "no_assertion_in_case",
  "dead_capture",
]);
export const STRUCTURAL_DISABLED_CODES = new Set([
  "command_allowlist_footprint_unavailable",
  "destructive_command",
  "regex_anchor_analysis_unavailable",
]);
export const MECHANICAL_ADVISORY_CODES = new Set([
  "authored_argument_descriptive",
  "author_sourced_driver_target",
  "author_sourced_unreachable_setup",
  "author_sourced_trigger_target",
  "residual_config_disclosed",
  "criterion_binding_declared",
  "scope_ref_absent",
  "adaptation_dropped_authored_command",
]);
export const ADVISE_CODE_CONSUMERS: Record<string, string> = Object.fromEntries(
  [...STRUCTURAL_ADVISORY_CODES, ...MECHANICAL_ADVISORY_CODES, ...GP_CODES, ...[...STRUCTURAL_DISABLED_CODES].map((c) => `gate_disabled:${c}`)].map(
    (code) => [code, "gate_advisory"]
  )
);

export function advisory_check_status(code: string): string {
  if (!(code in ADVISE_CODE_CONSUMERS)) {
    return "unknown";
  }
  if (code.startsWith("gate_disabled:")) {
    return "not_checked";
  }
  return "checked_limitation";
}
