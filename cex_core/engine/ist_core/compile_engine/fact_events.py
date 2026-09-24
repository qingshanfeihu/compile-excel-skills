# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/fact_events.py（sha256 8750e0bc39b13110）。不在这里手改。
"""事实流事件名登记表：`facts.jsonl` 里 `ev` 的闭集。

**这张表是 `ev` 的机器可读单源。** `docs/GLOSSARY_plain_language.md` 第三部分那张
人话词表是它的**子集视图**，两边由 `tests/docs/test_fact_event_vocabulary.py` 对账
（词表里的令牌必须在本表里），不是两份手抄。词表只登记需要人话解释的那些，本表
登记引擎**能写出来**的全部。

**闭集挂在写侧，不挂在解码期。** `facts.append_facts` 在碰文件之前先核一遍本表，
未登记的名字当场抛 `UnregisteredFactEvent`；`facts.load_facts` 读到未登记的名字
只记名不丢行。理由在 `_repair_torn_tail`：它拿 `_decode_fact_line` 解不解得开当
尾帧完整性判据，闭集一旦进解码期，一条完整但事件名没登记的旧尾行就会被判成撕裂帧
`os.ftruncate` 掉——冻结语料里的旧账会被读它的那次追加删掉。守门
`tests/ist_core/compile_engine/test_fact_event_registry.py`。

**表的边界（写清楚，别当成「引擎的全部事件」读）**：

- 登记的是**可以出现在 `facts.jsonl` 里**的名字。`bed.bed_record` 的床台账、
  worker session journal 是各自的文件，不走 `append_facts`，不归本表管。
- `compat_projection` / `compat_unmigratable` / `facts_migration_manifest` 由
  `scripts/maintenance/migrate_compat_shapes.py` 直接写进同一个文件，登记在此。
- 计算出来的名字按它们各自的域展开登记，不靠通配：
  `{carriers,feedback,supply}_check_result`（`authoring_evidence.CHECK_KINDS`）、
  `svc_*_{completed,failed}`（`tools/device/authoring_services.py` 十个服务）、
  `{delivery,subset}_dispatch_started`（`facts.EXECUTION_DISPATCH_EVENTS`）、
  `final_volume_{identity_failed,authority_unverified}`
  （`terminal_outcomes.final_volume_failure_event`）、`blocked` / `ist_core_defect`
  / `unable_to_compile`（`execution_failure.FailureAction`）。
  改了那些域就得改这张表，改不同步的那一刻写侧当场抛。

**怎么加一个新事件**：在本表加一行；要给人看就同时在词表补一行人话解释。
改名＝删旧名加新名，旧名从本表消失后**旧账照常读得出来**（读侧不认闭集），
只是再也写不出新的。
"""
from __future__ import annotations
from typing import Iterable
REGISTRY_LOCATION = 'main/ist_core/compile_engine/fact_events.py::FACT_EVENTS'

class UnregisteredFactEvent(ValueError):
    """事实流追加口拿到了一个没在 `FACT_EVENTS` 里登记的 `ev`。"""
FACT_EVENTS: frozenset[str] = frozenset({'terminal_reentry_held', 'adjudication_write_failed', 'adopted', 'ask_answer_rejected', 'ask_form_audit', 'ask_panel', 'ask_path_retired_disclosure', 'ask_shown', 'assertion_audit_suite', 'attribution', 'attribution_brief_bounded', 'attribution_evidence_hold', 'attribution_evidence_hold_cleanup', 'attribution_evidence_scrubbed', 'attribution_evidence_unavailable', 'attribution_evidence_working_copy_preserved', 'attribution_projection_identity_recovered', 'attribution_protocol_error', 'attribution_skipped', 'attribution_unrecoverable', 'author_definition_gap_disclosed', 'author_gap_rejected_signed_expectation', 'author_reauthor_unavailable', 'author_skipped_off_projection', 'authored', 'authored_scope_disclosed', 'authored_surface_conflict_cited', 'authored_surface_conflict_recovery', 'authored_surface_conflict_round_cap', 'authoring_account_submitted', 'authoring_account_supplement_failed', 'authoring_account_supplement_requested', 'authoring_account_supplement_unverified', 'authoring_account_supplement_usage', 'authoring_account_supplemented', 'authoring_attempt_accounting_unverified', 'authoring_attempt_reimbursed', 'authoring_attempt_scope', 'authoring_attempt_voided', 'authoring_brief_reference', 'authoring_budget_closed', 'authoring_budget_observed', 'authoring_check_disclosure', 'authoring_failure', 'authoring_failure_unconfirmed', 'authoring_scope_unverified', 'authoring_self_check', 'authoring_statement_unverified', 'authority_delivery_gate', 'authority_preflight_blocked', 'authority_reconcile_failed', 'authority_reconciled', 'awaiting_user_unasked', 'batch_backstop_reached', 'batch_backstop_reopened', 'batch_backstops_bound', 'batch_closing_unverified', 'batch_deadline_paused', 'batch_deadline_resumed', 'batch_dispatch_started', 'batch_execution_paused', 'batch_terminal_outcome', 'bed_checked', 'bed_cleaned', 'bed_closure_failed', 'bed_closure_unrecorded', 'bed_gate_mechanical_blocked', 'bed_reselection_requires_preflight', 'bed_restore_unparsed', 'blocked', 'blocking_card', 'capability_consumed_verified', 'capability_sync_failed', 'capability_synced', 'carriers_check_result', 'case_quarantined', 'case_quarantined_closing', 'case_source_inconsistency', 'case_terminal_outcome', 'case_terminal_static_void', 'claim_conflict_both_true_released', 'closing_archive_displaced', 'closing_case_untouched', 'closing_projection_unconfirmed', 'coexist_blocked', 'coexist_conflict', 'command_domain_case_excluded', 'command_domain_preflight_checked', 'command_heads_query_receipt', 'common_cause', 'compat_projection', 'compat_unmigratable', 'compilation_assessment', 'compile_attempt_resolved', 'compile_attempt_started', 'compose_rejected', 'composed', 'conditional_decision', 'conflict_chain_reentered', 'conflict_delta_decision', 'conflict_delta_reduced', 'consistency_verdict', 'context_degraded', 'contract_card_shown', 'contract_card_signed', 'contract_entry_blocked', 'credential_stale', 'criterion_adjudication_unavailable', 'criterion_binding_declared', 'criterion_engine_adjudicated', 'criterion_rule_updated', 'criterion_satisfiability_gap', 'de_escalated', 'decision', 'decision_outcome', 'decision_premise_void', 'deesc_keep', 'defect_spec_lookup_unresolved', 'delivery_blocked', 'delivery_dispatch_started', 'delivery_overwritten', 'device_disclosure', 'device_prerequisite_receipt', 'diagnosis', 'disclosure', 'drift_claim_retract_failed', 'emit_invalid', 'engine_aborted', 'engine_bug_released', 'engine_condition_disclosure', 'engine_debt_closed', 'engine_debt_entry', 'engine_debt_index_unavailable', 'engine_debt_occurrence', 'engine_error', 'engine_error_terminal_outcome', 'engine_error_unverifiable_disclosure', 'engine_gap_submitted', 'engine_halt', 'engine_incident_capture', 'engine_release_observed', 'engine_release_unverified', 'environment_execution_disclosure', 'environment_gap_evidence_verified', 'escalated', 'evidence_suspect', 'execution_failure', 'execution_pause', 'execution_reentry_artifact_reused', 'execution_success', 'expectation_assertion_bound', 'expected_authority_preflight', 'expected_source_claims_bound', 'facts_migration_manifest', 'feedback_check_result', 'final_volume_authority_disclosure', 'final_volume_authority_unverified', 'final_volume_identity_failed', 'fixture_values_disclosed', 'frozen_override_supplied', 'frozen_write_failed', 'gate_advisory', 'gate_disabled', 'gate_rejected', 'governing_spec_declaration_mismatch', 'governing_spec_entry_preflight', 'intent_stamp_failed', 'ir_gap', 'ir_gap_sink_health', 'ist_core_defect', 'ledger_unreadable', 'legacy_delivery_credential', 'llm_usage', 'machine_mindmap_mechanical_fields_filled', 'machine_mindmap_mechanical_rederived', 'machine_mindmap_step_structure_rejected', 'manual_audit', 'mechanical_case_repair_disclosure', 'mechanical_case_repaired', 'mechanical_case_submission_rejected', 'merge_declined', 'merge_pending_decision', 'merge_rejected', 'merged', 'metrics_cycle', 'metrics_scope', 'mirror_unverified', 'model_response_observed', 'mutation_control_miss', 'mutation_finalize_failed', 'needs_decision', 'needs_decision_binding_migrated', 'needs_decision_ledger', 'needs_decision_retired', 'network_outage', 'no_progress_decision', 'node_crash', 'not_compilable', 'not_fixpoint', 'pass_audit', 'policy_abandon', 'prediction_before_run', 'prerequisite_finding', 'previous_run_disclosure', 'prior_dispatch_sequence', 'prior_run_history', 'probe_evidence', 'quarantined_dispatch_refused', 'quarantined_result', 'question_form_blocked', 'question_unbuildable', 'read_window_truncated_claim', 'recompile_comparison', 'recompose_case_quarantined', 'recompose_consistency', 'recompose_dispatch_incomplete', 'recompose_dispatch_started', 'recompose_done', 'recompose_failed', 'recompose_grounding_rebound', 'recompose_grounding_revalidation_failed', 'recompose_redispatched', 'recompose_sealed_by_engine', 'recompose_shards_completed', 'report_mismatch', 'resumed', 'rollback', 'rollback_failed', 'round_cap_side_disclosure', 'route_no_progress_stop', 'rule_change', 'run_closed', 'run_controller_returned', 'run_start', 'run_started', 'runtime_actual_observed', 'runtime_actual_repeated', 's0_candidate', 's0_dispute', 'scenario_fidelity', 'service_worker_termination', 'session_admission_rejected', 'session_desync', 'session_desync_cluster', 'shadow_verdict', 'sibling_collision', 'sibling_contrast', 'source_conflict_auto_resolved', 'source_conflict_blocked', 'source_span_shadow_divergence', 'spec_lookup_auto_resolved_absent', 'spec_lookup_resolved_absent', 'spec_lookup_retry_requested', 'spec_lookup_unknown', 'spec_reference_set', 'staging_module_tie_broken', 'static_decision_batch_blocked', 'step_escape', 'strong_claim_unaddressed', 'structural_blocked', 'structural_quarantine_failed', 'structural_rejection_disclosure', 'structural_terminal_outcome', 'subset_dispatch_started', 'supply_check_result', 'suspend_kind_unclassified', 'suspended', 'suspension_premise_void', 'suspension_reentered', 'svc_ask_route_completed', 'svc_ask_route_failed', 'svc_brief_build_completed', 'svc_brief_build_failed', 'svc_close_actionable_override_disclosed', 'svc_close_deliver_completed', 'svc_close_deliver_failed', 'svc_dev_run_completed', 'svc_dev_run_failed', 'svc_emit_completed', 'svc_emit_failed', 'svc_merge_completed', 'svc_merge_failed', 'svc_recompose_completed', 'svc_recompose_failed', 'svc_reconcile_completed', 'svc_reconcile_failed', 'svc_submit_status_completed', 'svc_submit_status_failed', 'svc_writeback_completed', 'svc_writeback_failed', 'tool_call_invalid_downgrade', 'tool_call_repair_disclosure', 'tool_execution_fault', 'unable_to_compile', 'unbound_observation_target', 'unconfirmed_terminal_claim', 'unsupported_feature', 'user_stop', 'vendor_build_anchor_ok', 'verdict', 'verdict_flip_recovered', 'verdict_recovered', 'verdict_unrecognized', 'verdict_unrecognized_cluster', 'verified_runs_write_failed', 'vk_derivation_supplied', 'volume_composition_mismatch', 'volume_composition_superset', 'worker_brief_built', 'worker_claim', 'worker_declared_failure', 'worker_device_attempt', 'worker_device_attempt_accounted', 'worker_device_attempt_committed', 'worker_device_attempt_resolved', 'worker_device_attempt_started', 'worker_device_lease_acquired', 'worker_device_lease_released', 'worker_device_shared_bound', 'worker_device_task_bound', 'worker_dispatch_started', 'worker_dispatch_terminated', 'worker_identity_unavailable', 'worker_loop_outcome', 'worker_probe_evidence_rejected', 'worker_recovery_abandoned', 'worker_recovery_external_task_isolated', 'worker_recovery_uncommitted_resolved', 'writeback', 'writeback_failed', 'xml_absence_terminal', 'xml_expectation_auto_case'})

def unregistered_fact_events(facts: Iterable[dict]) -> list[str]:
    """挑出这批事实里没登记的事件名（去重、排序）。读侧披露用。"""
    return sorted({name for fact in facts if isinstance(fact, dict) and (name := str(fact.get('ev') or '')) and (name not in FACT_EVENTS)})

def require_registered(facts: Iterable[dict], *, where: str='') -> None:
    """写侧闭集：有一个没登记就整批抛，不落盘。

    抛出的话里带事件名与登记表位置——改名改漏了的人，看的就是这一句。
    """
    batch = list(facts)
    unknown = unregistered_fact_events(batch)
    if any((isinstance(fact, dict) and (not str(fact.get('ev') or '')) for fact in batch)):
        unknown = [*unknown, '<空事件名>']
    if not unknown:
        return
    raise UnregisteredFactEvent('事实流拒绝未登记的事件名: ' + f'events={unknown}, registry={REGISTRY_LOCATION}' + (f', ledger={where}' if where else '') + '；新事件先在登记表加一行，改名要同时删旧名加新名')
