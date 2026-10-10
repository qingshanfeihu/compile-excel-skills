export const REGISTRY_LOCATION = 'main/ist_core/compile_engine/fact_events.py::FACT_EVENTS';

export class UnregisteredFactEvent extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "UnregisteredFactEvent";
  }
}

export const FACT_EVENTS: ReadonlySet<string> = new Set(['terminal_reentry_held', 'adjudication_write_failed', 'adopted', 'ask_answer_rejected', 'ask_form_audit', 'ask_panel', 'ask_path_retired_disclosure', 'ask_shown', 'assertion_audit_suite', 'attribution', 'attribution_brief_bounded', 'attribution_evidence_hold', 'attribution_evidence_hold_cleanup', 'attribution_evidence_scrubbed', 'attribution_evidence_unavailable', 'attribution_evidence_working_copy_preserved', 'attribution_projection_identity_recovered', 'attribution_protocol_error', 'attribution_skipped', 'attribution_unrecoverable', 'author_definition_gap_disclosed', 'author_gap_rejected_signed_expectation', 'author_reauthor_unavailable', 'author_skipped_off_projection', 'authored', 'authored_scope_disclosed', 'authored_surface_conflict_cited', 'authored_surface_conflict_recovery', 'authored_surface_conflict_round_cap', 'authoring_account_submitted', 'authoring_account_supplement_failed', 'authoring_account_supplement_requested', 'authoring_account_supplement_unverified', 'authoring_account_supplement_usage', 'authoring_account_supplemented', 'authoring_attempt_accounting_unverified', 'authoring_attempt_reimbursed', 'authoring_attempt_scope', 'authoring_attempt_voided', 'authoring_brief_reference', 'authoring_budget_closed', 'authoring_budget_observed', 'authoring_check_disclosure', 'authoring_failure', 'authoring_failure_unconfirmed', 'authoring_scope_unverified', 'authoring_self_check', 'authoring_statement_unverified', 'authority_delivery_gate', 'authority_preflight_blocked', 'authority_reconcile_failed', 'authority_reconciled', 'awaiting_user_unasked', 'batch_backstop_reached', 'batch_backstop_reopened', 'batch_backstops_bound', 'batch_closing_unverified', 'batch_deadline_paused', 'batch_deadline_resumed', 'batch_dispatch_started', 'batch_execution_paused', 'batch_terminal_outcome', 'bed_checked', 'bed_cleaned', 'bed_closure_failed', 'bed_closure_unrecorded', 'bed_gate_mechanical_blocked', 'bed_reselection_requires_preflight', 'bed_selected', 'bed_unavailable', 'blocked', 'carriers_check_result', 'case_adjudication_written', 'case_compiler_step_structure_invalid', 'case_dropped', 'case_rebind_proposal', 'case_rejected', 'case_terminal_static_void', 'closing_note', 'compat_projection', 'compat_unmigratable', 'composed', 'consistency_verdict', 'contradiction_stop', 'decision', 'defect_candidates_written', 'defect_conditional', 'defect_unverified', 'deliverable_written', 'delivery_blocked', 'delivery_dispatch_started', 'deescalated', 'device_characteristics_unavailable', 'device_info_queried', 'dispatch_attempt', 'dispatch_rebind_requested', 'dispatch_reimbursed', 'engine_error', 'engine_error_unverifiable_disclosure', 'engine_quarantine', 'env_blocked', 'escalated', 'execution_reentry_artifact_reused', 'execution_reentry_claimed', 'execution_reentry_conflict', 'facts_migration_manifest', 'feedback_check_result', 'final_volume_authority_unverified', 'final_volume_identity_failed', 'ist_core_defect', 'merged', 'needs_decision', 'not_compilable_report', 'objective_confirmed', 'objective_unconfirmed', 'policy_abandon', 'preflight_completed', 'preflight_disclosure', 'preflight_probe_refused', 'preflight_receipt', 'preflight_round', 'preflight_unavailable', 'projection_receipt', 'question_asked', 'recompose_done', 'recompose_started', 'resumed', 'round_cap', 'session_admission_rejected', 'session_desync_cluster', 'source_conflict_blocked', 'subset_dispatch_started', 'supply_check_result', 'suspended', 'terminal_reentry_rejected', 'unable_to_compile', 'unsupported_feature', 'verdict', 'worker_result_envelope', 'worker_timeout', 'xml_absence_terminal'].flatMap((e) => [e]));

export function unregistered_fact_events(facts: Iterable<Record<string, any>>): string[] {
  const unknown = new Set<string>();
  for (const fact of facts) {
    if (fact && typeof fact === "object") {
      const name = String(fact.ev ?? "");
      if (name && !FACT_EVENTS.has(name)) {
        unknown.add(name);
      }
    }
  }
  return [...unknown].sort();
}

export function require_registered(facts: Iterable<Record<string, any>>, opts: { where?: string } = {}): void {
  const batch = Array.from(facts);
  let unknown = unregistered_fact_events(batch);
  const hasEmpty = batch.some((fact) => fact && typeof fact === "object" && !String(fact.ev ?? ""));
  if (hasEmpty) {
    unknown = [...unknown, '<空事件名>'];
  }
  if (unknown.length === 0) {
    return;
  }
  const where = opts.where ?? '';
  throw new UnregisteredFactEvent(
    '事实流拒绝未登记的事件名: ' +
      `events=${JSON.stringify(unknown)}, registry=${REGISTRY_LOCATION}` +
      (where ? `, ledger=${where}` : '') +
      '；新事件先在登记表加一行，改名要同时删旧名加新名'
  );
}
