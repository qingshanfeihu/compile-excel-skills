export const ASSERTION_BINDINGS_SIDECAR_NAME = "assertion_bindings.json";
export const RUNTIME_FILL_RECEIPTS_SIDECAR_NAME = "runtime_fill_receipts.json";
export const RUNTIME_FILL_TRANSACTION_JOURNAL_NAME = ".runtime_fill_transaction.json";
export const RUNTIME_FILL_TRANSACTION_COMMIT_NAME = ".runtime_fill_transaction.commit.json";
export const MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME = "machine_mindmap_disclosures.json";
export const CONTRACT_WARNING_PANEL_SIDECAR_NAME = "contract_warning_panel.json";
export const RESIDUAL_CONFIG_DISCLOSURE_SIDECAR_NAME = "residual_config_disclosure.json";
export const MECHANICAL_FINDINGS_SIDECAR_NAME = "mechanical_findings.json";
export const RECOMPILE_COMPARISON_SIDECAR_NAME = "recompile_comparison.json";
export const RECOMPILE_HISTORY_DIRECTORY_NAME = "recompile_history";
export const ENGINE_TRACE_DIRECTORY_NAME = "engine_trace";
export const MECHANICAL_CASE_SIDECAR_NAME = "mechanical_case.json";
export const CONSISTENCY_DISPATCH_LEDGER_NAME = ".consistency_dispatch_ledger.jsonl";
export const CONSISTENCY_CONTRACT_SIDECAR_NAME = "consistency_contract.json";
export const MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME = ".machine_mindmap_submission.json";
export const MACHINE_MINDMAP_SUBMISSION_LOCK_NAME = ".machine_mindmap_submission.lock";
export const MACHINE_MINDMAP_PARTS_LEDGER_NAME = ".machine_mindmap_parts.jsonl";
export const RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME = "command_grounding.json";
export const COMPILE_DRAFT_CHECKPOINT_SIDECAR_NAME = "compile_draft_checkpoint.json";
export const ROLLBACK_RECEIPT_SIDECAR_NAME = "rollback_receipt.json";
export const ATTRIBUTION_EVIDENCE_HOLD_DIRECTORY_NAME = "attribution_evidence_holds";
export const BRIEF_OVERFLOW_DIRECTORY_NAME = "brief_overflow";
export const BRIEF_OVERFLOW_FILE_PREFIX = "brief_";
export const SPEC_REFERENCES_DIRECTORY_NAME = "spec_references";
export const ENGINE_MANAGED_OUTPUT_DIRECTORY_NAMES = new Set([
  ATTRIBUTION_EVIDENCE_HOLD_DIRECTORY_NAME,
  BRIEF_OVERFLOW_DIRECTORY_NAME,
  RECOMPILE_HISTORY_DIRECTORY_NAME,
  ENGINE_TRACE_DIRECTORY_NAME,
  SPEC_REFERENCES_DIRECTORY_NAME,
]);
export const ENGINE_MANAGED_READABLE_DIRECTORY_NAMES = new Set([
  BRIEF_OVERFLOW_DIRECTORY_NAME,
  SPEC_REFERENCES_DIRECTORY_NAME,
]);
export const ENGINE_MANAGED_OUTPUT_BASENAMES = new Set([
  ".frozen.json",
  ".frozen_override_ack.json",
  ".grade_credential.json",
  ASSERTION_BINDINGS_SIDECAR_NAME,
  MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME,
  CONTRACT_WARNING_PANEL_SIDECAR_NAME,
  MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME,
  MACHINE_MINDMAP_SUBMISSION_LOCK_NAME,
  MACHINE_MINDMAP_PARTS_LEDGER_NAME,
  RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME,
  COMPILE_DRAFT_CHECKPOINT_SIDECAR_NAME,
  MECHANICAL_CASE_SIDECAR_NAME,
  MECHANICAL_FINDINGS_SIDECAR_NAME,
  RECOMPILE_COMPARISON_SIDECAR_NAME,
  CONSISTENCY_CONTRACT_SIDECAR_NAME,
  CONSISTENCY_DISPATCH_LEDGER_NAME,
  ROLLBACK_RECEIPT_SIDECAR_NAME,
  RESIDUAL_CONFIG_DISCLOSURE_SIDECAR_NAME,
  RUNTIME_FILL_RECEIPTS_SIDECAR_NAME,
  RUNTIME_FILL_TRANSACTION_COMMIT_NAME,
  RUNTIME_FILL_TRANSACTION_JOURNAL_NAME,
  "REPORT_MISMATCH.json",
  "ask_panel.json",
  "ask_user_answers.jsonl",
  "attr_evidence.json",
  "bed_before.json",
  "behavior_candidates.json",
  "case.mutation.json",
  "case.provenance.json",
  "contract_cards.json",
  "defect_candidates.json",
  "defect_spec_status.json",
  "emit_stats.jsonl",
  "engine_report.json",
  "env_capabilities.json",
  "facts.jsonl",
  "gate_events.jsonl",
  "gate_observability.jsonl",
  "gate_rejections.json",
  "governing_spec_status.json",
  "intent.json",
  "intent_stamp_status.json",
  "ir_gap.json",
  "last_run.json",
  "manifest.json",
  "metrics.json",
  "mindmap_source.json",
  "needs_decision.json",
  "runtime_fills.json",
  "user_decision.json",
  "worker_device_runs.jsonl",
]);
