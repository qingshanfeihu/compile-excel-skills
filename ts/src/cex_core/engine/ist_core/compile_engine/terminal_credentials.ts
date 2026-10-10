// 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/terminal_credentials.py（sha256 ad7d31ac9d02b624）。不在这里手改。
import crypto from "node:crypto";
import { Path, pyJsonDumps, pyJsonLoads, reFullmatch, strSplit } from "../../_py";
import { canonical_schema } from "../../common/schema_identity";
import { engine_schema_id } from "../../common/engine_track_schema";
import { canonical_persisted_value, persisted_surface_sha256, scrub_text } from "../security_scrub";
import {
  AUTHORITY_DELIVERY_SCHEMA,
  canonical_sha256 as _authority_sha256,
  is_volume_identity_failure,
  latest_delivery_match,
} from "./authority_delivery_policy";
import {
  authoring_round_causes,
  author_definition_gap_landing_facts,
  engine_budget_terminal_facts,
  surviving_underdetermined_declaration,
} from "./facts";

export const SCHEMA = 'ist.terminal-credential';
export const AUTHORING_FAILURE_RECEIPT_SCHEMA = engine_schema_id('authoring_failure_receipt');
export const AUTHORING_FAILURE_PROOF_SCHEMA = engine_schema_id('authoring_failure_proof');
export const ATTRIBUTION_LAYER_BY_DISPOSITION: Record<string, string> = { 'product_defect': 'device', 'expectation_suspect': 'ought', 'case_defect': 'compile', 'environment_blocked': 'device', 'env_blocked': 'device', 'device_defect': 'device', 'ought_gap': 'ought', 'compile_gap': 'compile' };
export const OUTCOME_BY_CREDENTIAL_KIND: Record<string, string> = { 'delivered': 'delivered', 'blocked': 'blocked', 'abandoned': 'abandoned', 'unable_to_compile': 'unable_to_compile', 'ist_core_defect': 'ist_core_defect', 'authoring_failure': 'authoring_failure' };
const _DELIVERY_FAILURE_KINDS: Record<string, string> = { 'delivered': 'delivery', 'blocked': 'delivery', 'abandoned': 'delivery', 'unable_to_compile': 'delivery', 'ist_core_defect': 'delivery', 'authoring_failure': 'delivery' };
const _NON_DELIVERY_LAYERS = new Set(['device', 'ought', 'compile']);
const _TO_BLOCKED = 'blocked';
const _TO_UNATTRIBUTED_LAYER = 'authoring_stop_unattributed';
const _EXECUTION_TERMINAL_OUTCOMES = new Set(['blocked', 'ist_core_defect', 'unable_to_compile']);
const _ROUND_CAP_BLOCK_EVENTS = new Set(['blocked', 'ist_core_defect']);
const _ROUND_CAP_REASON_CODE = 'round_cap_reached';
const _ROUND_CAP_RECEIPT_FIELDS = ['run_id', 'autoid', 'case_name', 'base_max_rounds', 'granted_rounds', 'rounds_used', 'effective_max_rounds', 'round_cap_receipt_sha256', 'source_block_event', 'source_block_fact_sha256', 'stop_reason', 'volume'] as const;
export const ROUND_CAP_RECEIPT_SCHEMA = 'ist.compile.round-cap-receipt.v1';
const _XML_ABSENCE_RECEIPT_FIELDS = ['run_id', 'autoid', 'case_name', 'blocking_class', 'claims', 'claims_sha256', 'reason', 'veto_claim_sha256s', 'xml_absence_receipt_sha256'] as const;
export const XML_ABSENCE_RECEIPT_SCHEMA = 'ist.compile.xml-absence-receipt.v1';
const _SUPPORTED_FEATURE_REJECTION_CODES = new Set(['signal_name_not_in_catalog', 'signal_type_not_supported', 'signal_semantics_unsupported', 'signal_value_out_of_range', 'signal_structure_unsupported', 'cli_argument_unsupported', 'cli_subcommand_missing', 'cli_io_mode_unsupported', 'cli_output_contract_unsupported', 'cli_timing_unsupported', 'cli_multi_step_unsupported', 'cli_report_unsupported', 'cli_safety_conflict', 'cli_environment_gap', 'cli_capability_unknown']);
const _FEATURE_TOKEN_RE = /^[a-z][a-z0-9_]*(?:-[a-z0-9_]+)*$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _ECHO_NAME_RE = /^(echo|echoes)\/[0-9a-f]{64}\.txt$/;
const _SUPPORTED_FEATURE_SAFE_FIELDS = new Set(['aid', 'case_name', 'reason_code', 'run_id', 'feature_id', 'signal_name', 'signal_type', 'cli_command', 'cli_subcommand', 'evidence', 'detail']);
const _SUPPORTED_FEATURE_LAYER = 'unsupported_feature';
const _NOT_COMPILABLE_LAYER = 'not_compilable';
const _SOURCE_CONFLICT_LAYER = 'source_conflict';
const _SOURCE_CONFLICT_BLOCKED_LAYER = 'source_conflict_blocked';
const _BATCH_USER_ABANDON_LAYER = 'batch_user_abandon';
const _AUTHORING_FAILURE_LAYER = 'authoring';
const _AUTHOR_DEFINITION_GAP_LAYER = 'author_definition_gap';
const _XML_ABSENCE_LAYER = 'xml_absence';
const _AUTHORING_FAILURE_PROOF_KINDS = new Set(['submission_rejected', 'no_output', 'device_result_case_side', 'compile_policy_exhausted', 'worker_claim_not_compilable', 'api_side', 'budget_governance', 'engine_side', 'environment', 'product']);
const _AUTHORING_FAILURE_WORKER_CLAIM_CODES = new Set(['author_gap_expectation_already_signed', 'environment_gap_unverified', 'no_cli_signed_expectation_unverified', 'author_conflict_surfaces_insufficient', 'author_conflict_expectation_unsigned']);
const _AUTHOR_DEFINITION_GAP_LANDING_FIELDS = new Set(['ev', 'aid', 'run_id', 'question_id', 'dispatch_id', 'batch_run_id', 'receipt_sha256', 'surface']);
const _AUTHOR_DEFINITION_GAP_LANDING_SURFACES = new Set(['needs_decision', 'authoring_failure', 'engine_error', 'worker_claim', 'attribution']);
const _AUTHORING_GAP_VARIANT = 'gap';
const _AUTHORING_CONFLICT_VARIANT = 'conflict';
const _AUTHOR_DEFINITION_GAP_INCOMPATIBLE_EVENTS = new Set(['verdict', 'device_attempt', 'execution_success', 'execution_failure', 'attribution', 'escalated', 'deescalated']);
const _AUTHOR_DEFINITION_GAP_REASON_CODES = new Set(['author_definition_gap', 'author_definition_conflict']);
const _AUTHORING_GAP_CODE = 'author_definition_gap';
const _AUTHORING_CONFLICT_CODE = 'author_definition_conflict';
const _NEEDS_DECISION_SCHEMA = 'ist.needs-decision';
const _NEEDS_DECISION_GATE_SCHEMA = 'ist.needs-decision-gate';
const _BATCH_USER_ABANDON_RECEIPT_FIELDS = ['run_id', 'autoid', 'case_name', 'batch_run_id', 'dispatch_id', 'decision_fact_sha256', 'decision_token', 'decision_text', 'member_autoids', 'receipt_sha256'] as const;
const _DECISION_ABANDON_TOKENS = new Set(['stop', 'batch_abandon']);
const _DELIVERY_EVIDENCE_TEXT_FIELDS = ['evidence', 'reason', 'detail', 'fix_direction', 'summary', 'text'] as const;
const _QUESTION_ID_RE = /^(q|panel):/;
const _DECISION_RESOLVE_EVENTS = new Set(['needs_decision', 'decision', 'batch_conflict_decision', 'conflict_chain_reentered']);
const _DEVICE_VERDICT_EVENTS = new Set(['verdict', 'worker_device_attempt']);
const _DEVICE_VERDICT_CONTEXTS = new Set(['delivery', 'subset']);
const _CENTRAL_DEVICE_CONTEXTS: Record<string, string> = { 'delivery': 'central_delivery', 'subset': 'central_subset' };
const _EMPTY_LEDGER_SHA256 = crypto.createHash('sha256').update(canonical_persisted_value([])).digest('hex');

export function authority_volume_not_ready(payload: Record<string, any>): boolean {
  return payload['ev'] === 'authority_delivery_gate' && payload['schema'] === AUTHORITY_DELIVERY_SCHEMA && payload['state'] === 'needs_decision' && Array.isArray(payload['failures']) && payload['failures'].includes('authority_not_ready') && typeof payload['artifact_sha256'] === 'string' && payload['artifact_sha256'] !== '';
}

export function authority_volume_pending(payload: Record<string, any>): boolean {
  return authority_volume_not_ready(payload) && !payload['spec_absent'];
}

export function authority_volume_blocked(payload: Record<string, any>): boolean {
  return authority_volume_not_ready(payload) && payload['spec_absent'] === true;
}

export function _fact_sha256(fact: Record<string, any>): string {
  return _authority_sha256(fact);
}

function _delivery_evidence_corpus_text(fact: Record<string, any>): string {
  const parts: string[] = [];
  for (const key of _DELIVERY_EVIDENCE_TEXT_FIELDS) {
    const value = fact[key];
    if (typeof value === 'string' && value.trim()) {
      parts.push(value);
    }
  }
  const steps = fact['steps'];
  if (Array.isArray(steps)) {
    for (const step of steps) {
      if (typeof step !== 'object' || step === null || Array.isArray(step)) {
        continue;
      }
      for (const key of _DELIVERY_EVIDENCE_TEXT_FIELDS) {
        const value = step[key];
        if (typeof value === 'string' && value.trim()) {
          parts.push(value);
        }
      }
    }
  }
  return parts.join('\n');
}

function _is_nonempty_text(value: any): boolean {
  return typeof value === 'string' && value.trim() !== '';
}

function _is_sha256(value: any): boolean {
  return typeof value === 'string' && _SHA256_RE.test(value);
}

export function authoring_auto_resolution_receipt(aid: string, case_name: string, facts: Record<string, any>[], opts: { terminal_fact?: Record<string, any> | null; run_id?: string; extra_fields?: Record<string, any> } = {}): Record<string, any> {
  const { terminal_fact = null, run_id = '', extra_fields = {} } = opts;
  let ledger: Record<string, any> = {};
  try {
    const readJson = require("./_shared").read_json;
    ledger = readJson(new Path('decision_ledgers').joinpath(`${aid}.json`)) || {};
  } catch {
    ledger = {};
  }
  const claims = ledger['claims'];
  const safe_claims = Array.isArray(claims) ? claims : [];
  const material = canonical_persisted_value(safe_claims);
  const ledger_sha256 = safe_claims.length > 0 ? crypto.createHash('sha256').update(material).digest('hex') : _EMPTY_LEDGER_SHA256;
  const terminal_sha256 = terminal_fact ? _fact_sha256(terminal_fact) : '';
  const receipt: Record<string, any> = {
    'run_id': String(run_id || (terminal_fact ? terminal_fact['run_id'] : '') || ''),
    'aid': aid,
    'case_name': String(case_name || ''),
    'terminal_fact_sha256': terminal_sha256,
    'ledger_sha256': ledger_sha256,
  };
  for (const [key, value] of Object.entries(extra_fields)) {
    receipt[key] = value;
  }
  const fields: [string, any][] = [
    ['decision', ''],
    ['ask', ''],
  ];
  for (const [key, def] of fields) {
    if (!(key in receipt)) {
      receipt[key] = def;
    }
  }
  if (claims !== undefined && claims !== null && !Array.isArray(claims)) {
    throw new Error('authoring ledger claims must be a list');
  }
  const receipt_copy = { ...receipt };
  delete receipt_copy['receipt_sha256'];
  receipt['receipt_sha256'] = crypto.createHash('sha256').update(Buffer.from(JSON.stringify(canonical_persisted_value(receipt_copy)), 'utf8')).digest('hex');
  return receipt;
}

export function authoring_failure_receipt_material(aid: string, case_name: string, run_id: string, facts: Record<string, any>[], opts: { ledger_sha256?: string; terminal_fact?: Record<string, any> | null } = {}): Record<string, any> {
  const { ledger_sha256 = '', terminal_fact = null } = opts;
  const causes = authoring_round_causes(facts, aid);
  const rounds_used = causes.length;
  const material: Record<string, any> = {
    'run_id': String(run_id || ''),
    'aid': aid,
    'case_name': String(case_name || ''),
    'ledger_sha256': String(ledger_sha256 || ''),
    'rounds_used': rounds_used,
    'causes': causes,
    'terminal_fact_sha256': terminal_fact ? _fact_sha256(terminal_fact) : '',
  };
  return material;
}

export function authoring_failure_receipt(material: Record<string, any>): string {
  const receipt_copy = { ...material };
  delete receipt_copy['receipt_sha256'];
  return crypto.createHash('sha256').update(Buffer.from(JSON.stringify(canonical_persisted_value(receipt_copy)), 'utf8')).digest('hex');
}

export function _structured_claims(value: any): Record<string, any>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item: any) => typeof item === 'object' && item !== null && !Array.isArray(item));
}

export function _object_sha256(value: any): string {
  return crypto.createHash('sha256').update(canonical_persisted_value(value)).digest('hex');
}

export function authoring_failure_receipt_validate(material: Record<string, any>, opts: { aid?: string; ledger_sha256?: string; facts?: Record<string, any>[] } = {}): string[] {
  const { aid = '', ledger_sha256 = '', facts = [] } = opts;
  const errors: string[] = [];
  if (material['schema'] !== AUTHORING_FAILURE_RECEIPT_SCHEMA) {
    errors.push('authoring_failure_receipt_schema_invalid');
  }
  if (material['autoid'] !== aid) {
    errors.push('authoring_failure_receipt_autoid_mismatch');
  }
  if (material['receipt_sha256'] !== authoring_failure_receipt(material)) {
    errors.push('authoring_failure_receipt_hash_mismatch');
  }
  const causes = material['causes'];
  if (!Array.isArray(causes) || causes.length === 0) {
    errors.push('authoring_failure_receipt_rounds_missing');
  }
  const case_side = facts.length > 0 ? authoring_round_causes(facts, aid) : [];
  if (case_side.length > 0 && JSON.stringify(causes) !== JSON.stringify(case_side)) {
    errors.push('authoring_failure_receipt_cause_mismatch');
  }
  if (ledger_sha256 && material['ledger_sha256'] !== ledger_sha256) {
    errors.push('authoring_failure_receipt_ledger_mismatch');
  }
  if (material['engine_attempted_fix'] !== false) {
    errors.push('authoring_failure_receipt_engine_fix_not_excluded');
  }
  return errors;
}

export function authoring_failure_proof_material(facts: Record<string, any>[], aid: string, opts: { receipt?: Record<string, any> | null } = {}): Record<string, any> {
  const { receipt = null } = opts;
  const causes = authoring_round_causes(facts, aid);
  const safe_causes = Array.isArray(causes) ? causes : [];
  const material: Record<string, any> = {
    'schema': AUTHORING_FAILURE_PROOF_SCHEMA,
    'aid': aid,
    'causes': safe_causes,
    'cause_count': safe_causes.length,
    'receipt_sha256': receipt ? String(receipt['receipt_sha256'] || '') : '',
  };
  return material;
}

export function authoring_failure_proof(material: Record<string, any>): string {
  const proof_copy = { ...material };
  delete proof_copy['proof_sha256'];
  return crypto.createHash('sha256').update(canonical_persisted_value(proof_copy)).digest('hex');
}

export function authoring_failure_proof_validate(material: Record<string, any>, opts: { aid?: string; facts?: Record<string, any>[] } = {}): string[] {
  const { aid = '', facts = [] } = opts;
  const errors: string[] = [];
  if (material['schema'] !== AUTHORING_FAILURE_PROOF_SCHEMA) {
    errors.push('authoring_failure_proof_schema_invalid');
  }
  if (material['aid'] !== aid) {
    errors.push('authoring_failure_proof_autoid_mismatch');
  }
  const causes = material['causes'];
  if (!Array.isArray(causes) || causes.length === 0) {
    errors.push('authoring_failure_proof_rounds_missing');
  }
  if (facts.length > 0) {
    const case_side = authoring_round_causes(facts, aid);
    if (JSON.stringify(causes) !== JSON.stringify(case_side)) {
      errors.push('authoring_failure_proof_cause_mismatch');
    }
  }
  if (material['engine_attempted_fix'] !== false) {
    errors.push('authoring_failure_proof_engine_fix_not_excluded');
  }
  if (material['proof_sha256'] !== authoring_failure_proof(material)) {
    errors.push('authoring_failure_proof_hash_mismatch');
  }
  return errors;
}

export function _attribution_projection(aid: string, facts: Record<string, any>[], opts: { layer?: string } = {}): Record<string, any>[] {
  const { layer = '' } = opts;
  return facts.filter((f: Record<string, any>) =>
    f['ev'] === 'attribution' && String(f['aid'] || '') === aid && (!layer || String(f['layer'] || '') === layer)
  );
}

export function _attribution_cascade(aid: string, facts: Record<string, any>[]): Record<string, any>[] {
  return _attribution_projection(aid, facts);
}

export function _current_attribution(aid: string, facts: Record<string, any>[], opts: { layer?: string } = {}): Record<string, any> | null {
  const { layer = '' } = opts;
  const cascades = _attribution_cascade(aid, facts);
  for (let index = cascades.length - 1; index >= 0; index--) {
    const attribution = cascades[index];
    if (!layer || String(attribution['layer'] || '') === layer) {
      return attribution;
    }
  }
  return null;
}

export function _find_fact_by_sha(facts: Record<string, any>[], opts: { aid?: string; ev?: string | Set<string> | string[]; expected_sha256?: string } = {}): Record<string, any> {
  const { aid = '', ev = '', expected_sha256 = '' } = opts;
  const evSet = ev instanceof Set ? ev : Array.isArray(ev) ? new Set(ev) : new Set([ev]);
  const candidates = facts.filter((f: Record<string, any>) =>
    evSet.has(String(f['ev'] || '')) && (!aid || String(f['aid'] || '') === aid)
  );
  for (const fact of candidates) {
    if (_fact_sha256(fact) === expected_sha256) {
      return fact;
    }
  }
  return {};
}

export function authoring_failure_terminal_credential(aid: string, facts: Record<string, any>[], opts: { outcome?: string; settlement_route?: string } = {}): Record<string, any> {
  const { outcome = '', settlement_route = '' } = opts;
  const causes = authoring_round_causes(facts, aid);
  if (!causes || !causes.every((row: Record<string, any>) => Boolean(row['case_side']))) {
    throw new Error('authoring failure requires case-side causes for every round');
  }
  const route = String(settlement_route || '');
  if (!['terminal_failure', 'outcome_terminal'].includes(route)) {
    throw new Error('authoring failure must declare a settlement route');
  }
  const credential: Record<string, any> = {
    'schema': SCHEMA,
    'aid': aid,
    'outcome': String(outcome || ''),
    'settlement_route': route,
    'causes': causes,
  };
  return credential;
}

export function _worker_device_attempt(aid: string, facts: Record<string, any>[], opts: { terminal_verdict?: Record<string, any> | null } = {}): Record<string, any> {
  const { terminal_verdict = null } = opts;
  const terminal_sha = terminal_verdict ? _fact_sha256(terminal_verdict) : '';
  let latest: Record<string, any> = {};
  let latest_index = -1;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] !== 'worker_device_attempt' || String(fact['aid'] || '') !== aid) {
      continue;
    }
    if (terminal_sha && fact['terminal_verdict_fact_sha256'] === terminal_sha) {
      return fact;
    }
    if (!latest_index || latest_index < 0) {
      latest = fact;
      latest_index = index;
    }
  }
  return latest;
}

export function _active_suspension_fact(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let last_suspended = -1;
  let last_resumed = -1;
  for (let index = 0; index < facts.length; index++) {
    const fact = facts[index];
    if (String(fact['aid'] || '') !== aid) continue;
    if (fact['ev'] === 'suspended') last_suspended = index;
    else if (fact['ev'] === 'resumed') last_resumed = index;
  }
  if (last_suspended < 0 || last_resumed > last_suspended) return {};
  return facts[last_suspended];
}
export function author_definition_gap_auto_resolution_valid(opts: { aid: string; ledger_sha256: string; facts: Record<string, any>[] }): boolean {
  const { aid, ledger_sha256, facts } = opts;
  const ledger_sha = String(ledger_sha256 || '');
  if (!ledger_sha) {
    return false;
  }
  const material = canonical_persisted_value([]);
  const empty_ledger_sha = crypto.createHash('sha256').update(material).digest('hex');
  if (ledger_sha !== empty_ledger_sha) {
    return false;
  }
  const declaration = surviving_underdetermined_declaration(facts, aid);
  if (!declaration || !declaration['claim_text']) {
    return false;
  }
  const authored = facts.filter((f: Record<string, any>) => f['ev'] === 'authored' && String(f['aid'] || '') === aid);
  return authored.length === 0;
}

export function authoring_auto_resolution_valid(opts: { aid: string; ledger_sha256: string; facts: Record<string, any>[] }): boolean {
  const { aid, ledger_sha256, facts } = opts;
  const ledger_sha = String(ledger_sha256 || '');
  if (!ledger_sha) {
    return false;
  }
  const authored = facts.filter((f: Record<string, any>) => f['ev'] === 'authored' && String(f['aid'] || '') === aid);
  if (authored.length > 0) {
    return false;
  }
  const causes = authoring_round_causes(facts, aid);
  return causes.length === 0;
}

export function _build_delivery_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  const verdicts = facts.filter((f: Record<string, any>) => f['ev'] === 'verdict' && String(f['aid'] || '') === aid && String(f['ctx'] || '') === 'delivery' && String(f['result'] || '') === 'pass');
  const verdict = verdicts.length > 0 ? verdicts[verdicts.length - 1] : null;
  if (!verdict) {
    return {};
  }
  const authored_rows = facts.filter((f: Record<string, any>) => f['ev'] === 'authored' && String(f['aid'] || '') === aid);
  const authored = authored_rows.length > 0 ? authored_rows[authored_rows.length - 1] : {};
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'delivery',
    'artifact': String(verdict['artifact'] || ''),
    'delivery_run_id': String(verdict['run_id'] || ''),
    'volume': String(verdict['volume'] || ''),
    'volume_artifact_sha256': String(verdict['volume_artifact_sha256'] || ''),
    'verdict_fact_sha256': _fact_sha256(verdict),
    'authored_fact_sha256': authored ? _fact_sha256(authored) : '',
    'mechanical_case_sha256': String(authored['from_mechanical_case_sha256'] || ''),
    'consistency_contract_sha256': authored['from_consistency_contract_sha256'] !== undefined ? authored['from_consistency_contract_sha256'] : null,
  };
  return refs;
}

export function _build_delivery_failure_credential(aid: string, facts: Record<string, any>[], outcome: string): Record<string, any> {
  const TO = require("./terminal_outcomes");
  const failures = facts.filter((f: Record<string, any>) => TO.FINAL_VOLUME_FAILURE_EVENTS.has(String(f['ev'] || '')) && String(f['aid'] || '') === aid);
  const failure = failures.length > 0 ? failures[failures.length - 1] : null;
  if (!failure) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'delivery_failure',
    'identity_fact_sha256': _fact_sha256(failure),
    'run_id': String(failure['run_id'] || ''),
    'volume': String(failure['volume'] || ''),
    'expected_artifact_sha256': String(failure['expected_artifact_sha256'] || ''),
    'observed_artifact_sha256': String(failure['observed_artifact_sha256'] || ''),
    'reasons': (failure['reasons'] || []).filter((v: any) => String(v)).map((v: any) => String(v)),
  };
  return refs;
}

export function _build_authority_decision_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let terminal: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'blocked' && String(fact['aid'] || '') === aid && String(fact['reason_code'] || '') === 'authority_needs_decision') {
      terminal = fact;
      break;
    }
  }
  if (!terminal) {
    return {};
  }
  const gate_sha = String(terminal['source_fact_sha256'] || '');
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'authority_decision',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'round': terminal['round'],
    'source_event': String(terminal['source_event'] || ''),
    'source_fact_sha256': gate_sha,
  };
  return refs;
}

export function _build_unsupported_feature_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  const NODES = require("./nodes");
  const terminal = NODES.latest_unsupported_feature_fact(facts, aid);
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'unsupported_feature',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'run_id': String(terminal['run_id'] || ''),
    'feature_id': String(terminal['feature_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  return refs;
}

export function _build_not_compilable_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  const NODES = require("./nodes");
  const terminal = NODES.latest_not_compilable_fact(facts, aid);
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'not_compilable',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'run_id': String(terminal['run_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  return refs;
}

export function _build_source_conflict_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  const NODES = require("./nodes");
  const terminal = NODES.latest_source_conflict_fact(facts, aid);
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'source_conflict',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'run_id': String(terminal['run_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  return refs;
}

export function _build_source_conflict_blocked_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  const NODES = require("./nodes");
  const terminal = NODES.latest_source_conflict_blocked_fact(facts, aid);
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'source_conflict_blocked',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'run_id': String(terminal['run_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  return refs;
}

export function _build_batch_user_abandon_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let decision: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'decision' && String(fact['aid'] || '') === aid && String(fact['token'] || '') === 'stop') {
      decision = fact;
      break;
    }
  }
  if (!decision) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'batch_user_abandon',
    'decision_fact_sha256': _fact_sha256(decision),
    'run_id': String(decision['run_id'] || ''),
    'batch_run_id': String(decision['batch_run_id'] || ''),
    'dispatch_id': String(decision['dispatch_id'] || ''),
    'decision_token': 'stop',
    'decision_text': String(decision['text'] || ''),
    'member_autoids': [],
  };
  return refs;
}

export function _build_round_cap_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  const shared = require("./_shared");
  const BT = require("./blocking_taxonomy");
  let policy: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'policy_abandon' && String(fact['aid'] || '') === aid && String(fact['blocking_class'] || '') === BT.A_ROUND_CAP) {
      policy = fact;
      break;
    }
  }
  if (!policy) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'round_cap',
    'abandon_fact_sha256': _fact_sha256(policy),
    'run_id': String(policy['run_id'] || ''),
    'autoid': aid,
    'case_name': String(policy['case_name'] || ''),
    'base_max_rounds': policy['base_max_rounds'],
    'granted_rounds': policy['granted_rounds'],
    'rounds_used': policy['rounds_used'],
    'effective_max_rounds': policy['effective_max_rounds'],
    'round_cap_receipt_sha256': String(policy['round_cap_receipt_sha256'] || ''),
    'source_block_event': String(policy['source_block_event'] || ''),
    'source_block_fact_sha256': String(policy['source_block_fact_sha256'] || ''),
    'stop_reason': String(policy['stop_reason'] || ''),
    'volume': String(policy['volume'] || ''),
  };
  return refs;
}

export function _build_authoring_failure_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let terminal: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'authoring_failure' && String(fact['aid'] || '') === aid) {
      terminal = fact;
      break;
    }
  }
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'authoring_failure',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'run_id': String(terminal['run_id'] || ''),
    'cause': String(terminal['cause'] || ''),
  };
  return refs;
}

export function _build_author_definition_gap_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let terminal: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'abandoned' && String(fact['aid'] || '') === aid && String(fact['blocking_class'] || '') === 'author_definition_gap') {
      terminal = fact;
      break;
    }
  }
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'author_definition_gap',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'run_id': String(terminal['run_id'] || ''),
    'variant': String(terminal['variant'] || ''),
  };
  return refs;
}

export function _build_xml_absence_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let terminal: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'xml_absence_terminal' && String(fact['aid'] || '') === aid) {
      terminal = fact;
      break;
    }
  }
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'xml_absence',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'run_id': String(terminal['run_id'] || ''),
    'blocking_class': String(terminal['blocking_class'] || ''),
    'claims': terminal['claims'],
    'claims_sha256': String(terminal['claims_sha256'] || ''),
    'reason': String(terminal['reason'] || ''),
    'veto_claim_sha256s': terminal['veto_claim_sha256s'],
    'xml_absence_receipt_sha256': String(terminal['xml_absence_receipt_sha256'] || ''),
  };
  return refs;
}

export function _xml_absence_receipt_material(fact: Record<string, any>): Record<string, any> {
  const material: Record<string, any> = {
    'run_id': String(fact['run_id'] || ''),
    'autoid': String(fact['aid'] || ''),
    'case_name': String(fact['case_name'] || ''),
    'blocking_class': String(fact['blocking_class'] || ''),
    'claims': fact['claims'],
    'claims_sha256': String(fact['claims_sha256'] || ''),
    'reason': String(fact['reason'] || ''),
    'veto_claim_sha256s': fact['veto_claim_sha256s'],
    'xml_absence_receipt_sha256': String(fact['xml_absence_receipt_sha256'] || ''),
  };
  return material;
}

export function _xml_absence_veto_claims(claims: any): Record<string, any>[] {
  if (!Array.isArray(claims)) {
    return [];
  }
  return claims.filter((claim: any) => typeof claim === 'object' && claim !== null && !Array.isArray(claim) && claim['claim_kind'] === 'xml_absence_veto');
}

export function _build_suspension_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let suspension: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'suspended' && String(fact['aid'] || '') === aid) {
      suspension = fact;
      break;
    }
  }
  if (!suspension) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'suspension',
    'suspension_fact_sha256': _fact_sha256(suspension),
    'run_id': String(suspension['run_id'] || ''),
    'reason': String(suspension['reason'] || ''),
    'question_id': String(suspension['question_id'] || ''),
  };
  return refs;
}

export function _build_execution_failure_credential(aid: string, outcome: string, facts: Record<string, any>[]): Record<string, any> {
  let terminal: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (String(fact['aid'] || '') !== aid) {
      continue;
    }
    if (fact['ev'] === 'blocked' && outcome === 'blocked') {
      terminal = fact;
      break;
    }
    if (fact['ev'] === 'ist_core_defect' && outcome === 'ist_core_defect') {
      terminal = fact;
      break;
    }
    if (fact['ev'] === 'unable_to_compile' && outcome === 'unable_to_compile') {
      terminal = fact;
      break;
    }
  }
  if (!terminal) {
    return {};
  }
  const failure_rows = facts.filter((f: Record<string, any>) => f['ev'] === 'execution_failure' && String(f['aid'] || '') === aid);
  const failure = failure_rows.length > 0 ? failure_rows[failure_rows.length - 1] : {};
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'execution_failure',
    'event': String(terminal['ev'] || ''),
    'terminal_fact_sha256': _fact_sha256(terminal),
    'failure_fact_sha256': failure ? _fact_sha256(failure) : '',
    'reason_code': String(terminal['reason_code'] || ''),
    'category': String(terminal['category'] || ''),
    'attempt': terminal['attempt'],
    'artifact_sha256': String(terminal['artifact_sha256'] || ''),
    'bed_host': String(terminal['bed_host'] || ''),
    'build': String(terminal['build'] || ''),
    'implementation_sha256': String(terminal['implementation_sha256'] || ''),
    'prerequisite_receipt_sha256': String(terminal['prerequisite_receipt_sha256'] || ''),
  };
  return refs;
}

export function _build_unattributed_stop_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let terminal: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'blocked' && String(fact['aid'] || '') === aid && String(fact['terminal_layer'] || '') === _TO_UNATTRIBUTED_LAYER) {
      terminal = fact;
      break;
    }
  }
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'unattributed_stop',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'reason_code': String(terminal['reason_code'] || ''),
    'stop_cause': String(terminal['stop_cause'] || ''),
    'round': terminal['round'],
    'source_event': String(terminal['source_event'] || ''),
    'source_fact_sha256': String(terminal['source_fact_sha256'] || ''),
  };
  return refs;
}

export function _build_engine_defect_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let terminal: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'ist_core_defect' && String(fact['aid'] || '') === aid) {
      terminal = fact;
      break;
    }
  }
  if (!terminal) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'engine_defect',
    'terminal_fact_sha256': _fact_sha256(terminal),
    'reason_code': String(terminal['reason_code'] || ''),
    'round': terminal['round'],
    'source_event': String(terminal['source_event'] || ''),
    'source_fact_sha256': String(terminal['source_fact_sha256'] || ''),
  };
  return refs;
}

export function _build_ought_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let latest: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'needs_decision' && String(fact['aid'] || '') === aid) {
      latest = fact;
      break;
    }
  }
  if (!latest) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'ought',
    'question_id': String(latest['question_id'] || ''),
    'question_fact_sha256': _fact_sha256(latest),
    'ledger_receipt': {},
    'claims': [],
    'claim_receipts': [],
  };
  return refs;
}

export function _build_compile_credential(aid: string, facts: Record<string, any>[]): Record<string, any> {
  let decision: Record<string, any> | null = null;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'no_progress_decision' && String(fact['aid'] || '') === aid && String(fact['domain'] || '') === 'compile' && fact['stop'] === true) {
      decision = fact;
      break;
    }
  }
  if (!decision) {
    return {};
  }
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'compile',
    'decision_fact_sha256': _fact_sha256(decision),
    'decision_id': String(decision['decision_id'] || ''),
    'domain': String(decision['domain'] || ''),
    'failure_key': String(decision['failure_key'] || ''),
    'streak': decision['streak'],
    'threshold': decision['threshold'],
    'revision_refs': decision['revision_refs'] || [],
    'stop': decision['stop'],
  };
  return refs;
}

export function _build_device_credential(aid: string, facts: Record<string, any>[], outcome: string): Record<string, any> {
  const terminal_verdict = outcome === 'device_defect' ? _find_fact_by_sha(facts, { aid, ev: 'verdict', expected_sha256: '' }) : {};
  const attempt = _worker_device_attempt(aid, facts, { terminal_verdict });
  const source = attempt ? 'worker_device_attempt' : _CENTRAL_DEVICE_CONTEXTS[String(terminal_verdict['ctx'] || '')] || 'central_delivery';
  const refs: Record<string, any> = {
    'schema': SCHEMA,
    'kind': 'device',
    'attempt_source': source,
    'attempt_fact_sha256': attempt ? _fact_sha256(attempt) : '',
    'terminal_verdict_fact_sha256': terminal_verdict ? _fact_sha256(terminal_verdict) : '',
    'attribution_fact_sha256': '',
    'echo_receipt': {},
    'verbatim_evidence': [],
  };
  return refs;
}

export function _read_case_file(case_dir: any, name: string): Buffer | null {
  if (!case_dir || !name) {
    return null;
  }
  try {
    const dir = case_dir instanceof Path ? case_dir : new Path(String(case_dir));
    const file_path = dir.joinpath(name);
    if (!file_path.is_file()) {
      return null;
    }
    return file_path.read_bytes();
  } catch {
    return null;
  }
}

export function _validate_delivery(aid: string, refs: Record<string, any>, facts: Record<string, any>[], case_dir: any): string[] {
  const errors: string[] = [];
  const required = ['artifact', 'delivery_run_id', 'volume', 'volume_artifact_sha256'] as const;
  if (required.slice(0, 3).some((key) => !_is_nonempty_text(refs[key]))) {
    errors.push('delivery_identity_incomplete');
  }
  if (!_is_sha256(refs['volume_artifact_sha256'])) {
    errors.push('delivery_volume_sha_invalid');
  }
  const verdict = _find_fact_by_sha(facts, { aid, ev: 'verdict', expected_sha256: String(refs['verdict_fact_sha256'] || '') });
  if (!verdict || Object.keys(verdict).length === 0) {
    errors.push('delivery_verdict_receipt_missing');
  } else if (!(verdict['ctx'] === 'delivery' && verdict['result'] === 'pass' && String(verdict['run_id'] || '') === refs['delivery_run_id'] && String(verdict['artifact'] || '') === refs['artifact'] && String(verdict['volume'] || '') === refs['volume'] && String(verdict['volume_artifact_sha256'] || '') === refs['volume_artifact_sha256'])) {
    errors.push('delivery_verdict_binding_mismatch');
  }
  const authored = _find_fact_by_sha(facts, { aid, ev: 'authored', expected_sha256: String(refs['authored_fact_sha256'] || '') });
  const mechanical_sha = String(refs['mechanical_case_sha256'] || '');
  const consistency_sha = refs['consistency_contract_sha256'];
  if (!authored || Object.keys(authored).length === 0) {
    errors.push('delivery_authored_receipt_missing');
  } else if (String(authored['artifact'] || '') !== String(refs['artifact'] || '') || String(authored['from_mechanical_case_sha256'] || '') !== mechanical_sha || authored['from_consistency_contract_sha256'] !== consistency_sha) {
    errors.push('delivery_authoring_identity_mismatch');
  }
  if (!_is_sha256(mechanical_sha)) {
    errors.push('delivery_mechanical_case_sha_invalid');
  }
  if (consistency_sha !== null && consistency_sha !== undefined && !_is_sha256(consistency_sha)) {
    errors.push('delivery_consistency_contract_sha_invalid');
  }
  const credential_raw = _read_case_file(case_dir, '.grade_credential.json');
  let lint_credential: Record<string, any> | null = null;
  try {
    lint_credential = credential_raw !== null ? pyJsonLoads(credential_raw) : null;
  } catch {
    lint_credential = null;
  }
  const scope = lint_credential && typeof lint_credential === 'object' && !Array.isArray(lint_credential) ? lint_credential['reachability_scope'] : null;
  const artifact_sha = String(refs['artifact'] || '').split(':').pop() || '';
  if (!(lint_credential && typeof lint_credential === 'object' && !Array.isArray(lint_credential) && lint_credential['source'] === 'lint' && lint_credential['lint_ok'] === true && lint_credential['verdict'] === 'PASS' && String(lint_credential['autoid'] || '') === aid && String(lint_credential['xlsx_sha256'] || '') === artifact_sha && scope && typeof scope === 'object' && !Array.isArray(scope) && scope['source'] === 'sealed_mechanical_case' && scope['mechanical_case_sha256'] === mechanical_sha && 'consistency_contract_sha256' in lint_credential && lint_credential['consistency_contract_sha256'] === consistency_sha)) {
    errors.push('delivery_lint_identity_mismatch');
  }
  return errors;
}

export function _validate_delivery_failure(aid: string, refs: Record<string, any>, facts: Record<string, any>[], outcome: string = ''): string[] {
  const TO = require("./terminal_outcomes");
  const errors: string[] = [];
  const failure = _find_fact_by_sha(facts, { aid, ev: TO.FINAL_VOLUME_FAILURE_EVENTS, expected_sha256: String(refs['identity_fact_sha256'] || '') });
  if (!failure || Object.keys(failure).length === 0) {
    return ['delivery_failure_receipt_missing'];
  }
  const copy_identity = require("./terminal_reentry_identity").copy_identity;
  let terminal: Record<string, any> = {};
  for (let index = facts.length - 1; index >= 0; index--) {
    const row = facts[index];
    if (row['aid'] === aid && ['blocked', 'ist_core_defect'].includes(String(row['ev'] || '')) && row['source_fact_sha256'] === _fact_sha256(failure)) {
      terminal = row;
      break;
    }
  }
  if (Object.keys(terminal).length > 0 && JSON.stringify(copy_identity(terminal)) !== JSON.stringify(copy_identity(failure))) {
    errors.push('delivery_failure_reentry_identity_mismatch');
  }
  const expected: Record<string, any> = {
    'run_id': String(failure['run_id'] || ''),
    'volume': String(failure['volume'] || ''),
    'expected_artifact_sha256': String(failure['expected_artifact_sha256'] || ''),
    'observed_artifact_sha256': String(failure['observed_artifact_sha256'] || ''),
    'reasons': (failure['reasons'] || []).filter((v: any) => String(v)).map((v: any) => String(v)),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('delivery_failure_binding_mismatch');
  }
  if (!_is_nonempty_text(expected['run_id']) || !expected['reasons'] || expected['reasons'].length === 0) {
    errors.push('delivery_failure_identity_incomplete');
  }
  if (outcome && outcome !== TO.authority_failure_position(expected['reasons'])) {
    errors.push('credential_kind_outcome_mismatch');
  }
  return errors;
}

export function _validate_authority_decision(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const AR = require("./authority_reconcile");
  function is_sha(value: any): boolean {
    return typeof value === 'string' && _SHA256_RE.test(value);
  }
  let terminal_index = -1;
  for (let index = 0; index < facts.length; index++) {
    const fact = facts[index];
    if (fact['aid'] === aid && fact['ev'] === 'blocked' && _fact_sha256(fact) === refs['terminal_fact_sha256']) {
      terminal_index = index;
      break;
    }
  }
  if (terminal_index < 0) {
    return ['authority_decision_terminal_receipt_missing'];
  }
  const terminal = facts[terminal_index];
  const errors: string[] = [];
  if (!_is_nonempty_text(aid) || terminal['reason_code'] !== 'authority_needs_decision' || terminal['terminal_layer'] !== 'delivery' || terminal['reentrant'] !== true || terminal['terminal'] !== false || typeof terminal['round'] !== 'number' || terminal['round'] < 0 || typeof refs['round'] !== 'number' || refs['source_event'] !== 'authority_delivery_gate' || !is_sha(refs['source_fact_sha256']) || ['round', 'source_event', 'source_fact_sha256'].some((key) => JSON.stringify(refs[key]) !== JSON.stringify(terminal[key]))) {
    errors.push('authority_decision_terminal_contract_mismatch');
  }
  let gate_index = -1;
  for (let index = 0; index < terminal_index; index++) {
    const fact = facts[index];
    if (fact['aid'] === aid && fact['ev'] === 'authority_delivery_gate' && _fact_sha256(fact) === refs['source_fact_sha256']) {
      gate_index = index;
      break;
    }
  }
  if (gate_index < 0) {
    return [...errors, 'authority_decision_gate_receipt_missing'];
  }
  const gate = facts[gate_index];
  const scope = gate['delivery_scope'];
  if (!scope || typeof scope !== 'object' || Array.isArray(scope)) {
    return [...errors, 'authority_decision_scope_missing'];
  }
  const binding = scope['binding'];
  const binding_fields = new Set(Object.getOwnPropertyNames(new AR.ExecutionBinding('', '', '', '', '', '', '', '')).filter((k) => k !== 'constructor'));
  if (!binding || typeof binding !== 'object' || Array.isArray(binding) || !Object.keys(binding).every((k) => binding_fields.has(k))) {
    return [...errors, 'authority_decision_binding_incomplete'];
  }
  if (Object.keys(binding_fields).some((key) => key !== 'consistency_contract_sha256' && !_is_nonempty_text(binding[key])) || !is_sha(binding['projection_receipt_sha256']) || !is_sha(binding['projection_sha256']) || !is_sha(binding['artifact_sha256']) || (binding['consistency_contract_sha256'] !== null && binding['consistency_contract_sha256'] !== undefined && !is_sha(binding['consistency_contract_sha256'])) || binding['autoid'] !== aid) {
    errors.push('authority_decision_binding_invalid');
  }
  const artifact = scope['artifact'];
  if (!_is_nonempty_text(scope['volume']) || !is_sha(scope['volume_artifact_sha256']) || typeof artifact !== 'string' || !new RegExp(`${aid}:[0-9a-f]{64}`).test(artifact) || !is_sha(scope['authored_fact_sha256']) || !is_sha(scope['merged_fact_sha256']) || !is_sha(scope['authority_fact_sha256'])) {
    errors.push('authority_decision_scope_invalid');
  }
  if (gate['state'] !== AR.AuthorityState.NEEDS_DECISION || JSON.stringify(gate['failures']) !== JSON.stringify([AR.ReconcileFailure.AUTHORITY_NOT_READY]) || gate['artifact_sha256'] !== scope['volume_artifact_sha256'] || binding['artifact_sha256'] !== scope['volume_artifact_sha256'] || !('consistency_contract_sha256' in gate) || JSON.stringify(gate['consistency_contract_sha256']) !== JSON.stringify(binding['consistency_contract_sha256'])) {
    errors.push('authority_decision_gate_binding_mismatch');
  }
  const prefix = facts.slice(0, gate_index);
  const authored = _find_fact_by_sha(prefix, { aid, ev: 'authored', expected_sha256: String(scope['authored_fact_sha256'] || '') });
  let current_authored: Record<string, any> = {};
  for (let index = prefix.length - 1; index >= 0; index--) {
    const row = prefix[index];
    if (row['aid'] === aid && row['ev'] === 'authored') {
      current_authored = row;
      break;
    }
  }
  if (!authored || Object.keys(authored).length === 0) {
    errors.push('authority_decision_authored_receipt_missing');
  } else if (_fact_sha256(authored) !== _fact_sha256(current_authored) || authored['artifact'] !== artifact || JSON.stringify(authored['from_consistency_contract_sha256']) !== JSON.stringify(binding['consistency_contract_sha256'])) {
    errors.push('authority_decision_authored_binding_mismatch');
  }
  const merged = _find_fact_by_sha(prefix, { aid: '', ev: 'merged', expected_sha256: String(scope['merged_fact_sha256'] || '') });
  let current_merged: Record<string, any> = {};
  for (let index = prefix.length - 1; index >= 0; index--) {
    const row = prefix[index];
    if (row['ev'] === 'merged' && row['ctx'] === 'delivery') {
      current_merged = row;
      break;
    }
  }
  if (!merged || Object.keys(merged).length === 0) {
    errors.push('authority_decision_merged_receipt_missing');
  } else if (_fact_sha256(merged) !== _fact_sha256(current_merged) || merged['ctx'] !== 'delivery' || merged['volume'] !== scope['volume'] || merged['artifact_sha256'] !== scope['volume_artifact_sha256'] || !Array.isArray(merged['composition']) || merged['composition'].filter((x: any) => x === aid).length !== 1 || !merged['member_artifacts'] || typeof merged['member_artifacts'] !== 'object' || Array.isArray(merged['member_artifacts']) || merged['member_artifacts'][aid] !== artifact) {
    errors.push('authority_decision_merged_binding_mismatch');
  }
  const authority = _find_fact_by_sha(prefix, { aid, ev: 'authority_reconciled', expected_sha256: String(scope['authority_fact_sha256'] || '') });
  if (!authority || Object.keys(authority).length === 0) {
    return [...errors, 'authority_decision_authority_receipt_missing'];
  }
  const receipt = authority['receipt'];
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) {
    return [...errors, 'authority_decision_authority_receipt_invalid'];
  }
  const receipt_fields = new Set(Object.getOwnPropertyNames(new AR.AuthorityReceipt('', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')).filter((k) => k !== 'constructor'));
  if (!Object.keys(receipt).every((k) => receipt_fields.has(k))) {
    return [...errors, 'authority_decision_authority_receipt_invalid'];
  }
  if (receipt['schema'] !== AR.AUTHORITY_SCHEMA || receipt['state'] !== AR.AuthorityState.NEEDS_DECISION || JSON.stringify(receipt['binding']) !== JSON.stringify(binding) || !is_sha(receipt['input_sha256']) || !is_sha(receipt['receipt_sha256']) || gate['receipt_sha256'] !== receipt['receipt_sha256']) {
    errors.push('authority_decision_authority_binding_mismatch');
  }
  const key = `${AR.AUTHORITY_SCHEMA}:${receipt['input_sha256']}`;
  if (receipt['idempotency_key'] !== key || authority['idempotency_key'] !== key) {
    errors.push('authority_decision_authority_idempotency_mismatch');
  }
  if (prefix.some((row: Record<string, any>) => row['ev'] === 'authority_reconciled' && row['idempotency_key'] === key && (row['aid'] !== aid || JSON.stringify(row['receipt']) !== JSON.stringify(receipt)))) {
    errors.push('authority_decision_authority_idempotency_conflict');
  }
  let receipt_sha256 = '';
  try {
    const receipt_copy = { ...receipt };
    delete receipt_copy['receipt_sha256'];
    receipt_sha256 = AR.canonical_sha256(receipt_copy);
  } catch {
    receipt_sha256 = '';
  }
  if (receipt['receipt_sha256'] !== receipt_sha256) {
    errors.push('authority_decision_authority_hash_mismatch');
  }
  const identities = receipt['source_identities'];
  const comparisons = receipt['comparisons'];
  if (!Array.isArray(identities) || identities.length === 0 || identities.some((item: any) => typeof item !== 'object' || item === null || Array.isArray(item)) || !Array.isArray(comparisons) || comparisons.length === 0 || comparisons.some((item: any) => typeof item !== 'object' || item === null || Array.isArray(item)) || !Array.isArray(receipt['conflicts']) || receipt['conflicts'].length === 0 || !Array.isArray(receipt['failures']) || receipt['failures'].length === 0) {
    return [...errors, 'authority_decision_authority_evidence_incomplete'];
  }
  let expected_state: any;
  try {
    expected_state = AR.authority_state_for_failures(receipt['failures'].map((value: any) => value));
  } catch {
    errors.push('authority_decision_authority_failure_invalid');
    expected_state = null;
  }
  if (expected_state !== null && expected_state !== AR.AuthorityState.NEEDS_DECISION) {
    errors.push('authority_decision_authority_state_inconsistent');
  }
  const layers = new Set(Object.values(AR.AuthorityLayer));
  const statuses = new Set(Object.values(AR.EvidenceStatus));
  if (new Set(identities.filter((item: any) => typeof item['layer'] === 'string').map((item: any) => item['layer'])) !== layers || identities.length !== layers.size || identities.some((item: any) => typeof item['status'] !== 'string' || !statuses.has(item['status']) || typeof item['identity'] !== 'string' || typeof item['build'] !== 'string' || (item['status'] === AR.EvidenceStatus.PRESENT && !_is_nonempty_text(item['identity'])))) {
    errors.push('authority_decision_authority_sources_invalid');
  }
  const comparison_fields = new Set(Object.getOwnPropertyNames(new AR.PairwiseComparison('', '', '', '', '', '', '', '')).filter((k) => k !== 'constructor'));
  const comparison_statuses = new Set(Object.values(AR.ComparisonStatus));
  const failures_set = new Set(Object.values(AR.ReconcileFailure));
  if (comparisons.some((item: any) => !Object.keys(item).every((k) => comparison_fields.has(k)) || !_is_nonempty_text(item['comparison_id']) || typeof item['left'] !== 'string' || !layers.has(item['left']) || typeof item['right'] !== 'string' || !layers.has(item['right']) || typeof item['status'] !== 'string' || !comparison_statuses.has(item['status']) || (item['failure'] !== null && item['failure'] !== undefined && (typeof item['failure'] !== 'string' || !failures_set.has(item['failure']))) || !_is_nonempty_text(item['left_identity']) || !_is_nonempty_text(item['right_identity']) || !Array.isArray(item['differences']))) {
    errors.push('authority_decision_authority_comparisons_invalid');
  } else {
    const expected_conflicts = comparisons.filter((item: any) => item['status'] === AR.ComparisonStatus.CONFLICT || item['status'] === AR.ComparisonStatus.UNAVAILABLE).map((item: any) => item['comparison_id']);
    const expected_failures = Array.from(new Set(comparisons.filter((item: any) => item['failure'] !== null && item['failure'] !== undefined).map((item: any) => item['failure'])));
    if (JSON.stringify(receipt['conflicts']) !== JSON.stringify(expected_conflicts) || JSON.stringify(receipt['failures']) !== JSON.stringify(expected_failures)) {
      errors.push('authority_decision_authority_state_inconsistent');
    }
  }
  return errors;
}

export function _validate_unsupported_feature(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'unsupported_feature_terminal', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['unsupported_feature_terminal_receipt_missing'];
  }
  const expected: Record<string, any> = {
    'run_id': String(terminal['run_id'] || ''),
    'feature_id': String(terminal['feature_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('unsupported_feature_binding_mismatch');
  }
  if (!_is_nonempty_text(expected['feature_id']) || !_is_nonempty_text(expected['reason_code'])) {
    errors.push('unsupported_feature_identity_incomplete');
  }
  if (!_SUPPORTED_FEATURE_REJECTION_CODES.has(expected['reason_code'])) {
    errors.push('unsupported_feature_reason_code_invalid');
  }
  return errors;
}

export function _validate_not_compilable(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'not_compilable_terminal', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['not_compilable_terminal_receipt_missing'];
  }
  const expected: Record<string, any> = {
    'run_id': String(terminal['run_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('not_compilable_binding_mismatch');
  }
  if (!_is_nonempty_text(expected['reason_code'])) {
    errors.push('not_compilable_identity_incomplete');
  }
  return errors;
}

export function _validate_source_conflict(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'source_conflict_terminal', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['source_conflict_terminal_receipt_missing'];
  }
  const expected: Record<string, any> = {
    'run_id': String(terminal['run_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('source_conflict_binding_mismatch');
  }
  if (!_is_nonempty_text(expected['reason_code'])) {
    errors.push('source_conflict_identity_incomplete');
  }
  return errors;
}

export function _validate_source_conflict_blocked(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'source_conflict_blocked_terminal', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['source_conflict_blocked_terminal_receipt_missing'];
  }
  const expected: Record<string, any> = {
    'run_id': String(terminal['run_id'] || ''),
    'reason_code': String(terminal['reason_code'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('source_conflict_blocked_binding_mismatch');
  }
  if (!_is_nonempty_text(expected['reason_code'])) {
    errors.push('source_conflict_blocked_identity_incomplete');
  }
  return errors;
}

export function _validate_batch_user_abandon(aid: string, refs: Record<string, any>, facts: Record<string, any>[], case_dir: any): string[] {
  const errors: string[] = [];
  const decision = _find_fact_by_sha(facts, { aid, ev: 'decision', expected_sha256: String(refs['decision_fact_sha256'] || '') });
  if (!decision || Object.keys(decision).length === 0) {
    return ['batch_user_abandon_decision_receipt_missing'];
  }
  const expected: Record<string, any> = {
    'run_id': String(decision['run_id'] || ''),
    'batch_run_id': String(decision['batch_run_id'] || ''),
    'dispatch_id': String(decision['dispatch_id'] || ''),
    'decision_token': String(decision['token'] || ''),
    'decision_text': String(decision['text'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('batch_user_abandon_binding_mismatch');
  }
  if (!_is_nonempty_text(expected['decision_token']) || !['stop', 'batch_abandon'].includes(expected['decision_token'])) {
    errors.push('batch_user_abandon_token_invalid');
  }
  const members = refs['member_autoids'];
  if (!Array.isArray(members)) {
    errors.push('batch_user_abandon_members_invalid');
  }
  return errors;
}

export function _validate_round_cap(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const shared = require("./_shared");
  const BT = require("./blocking_taxonomy");
  const fact_rules = require("./facts");
  const views = require("./views");
  const { ReentryAction, reduce_blocked_reentry } = require("./conflict_chain");
  const expected_policy_sha = String(refs['abandon_fact_sha256'] || '');
  let policy_index = -1;
  for (let index = facts.length - 1; index >= 0; index--) {
    const fact = facts[index];
    if (fact['ev'] === 'policy_abandon' && String(fact['aid'] || '') === aid && _fact_sha256(fact) === expected_policy_sha) {
      policy_index = index;
      break;
    }
  }
  if (policy_index < 0) {
    return ['round_cap_policy_receipt_missing'];
  }
  const policy = facts[policy_index];
  const prefix = facts.slice(0, policy_index);
  const errors: string[] = [];
  if (policy['blocking_class'] !== BT.A_ROUND_CAP || policy['reason_code'] !== _ROUND_CAP_REASON_CODE || policy['terminal'] !== true || policy['round_cap_receipt_schema'] !== ROUND_CAP_RECEIPT_SCHEMA) {
    errors.push('round_cap_policy_contract_mismatch');
  }
  const expected_refs: Record<string, any> = {};
  for (const field of _ROUND_CAP_RECEIPT_FIELDS) {
    expected_refs[field] = policy[field];
  }
  if (Object.entries(expected_refs).some(([field, value]) => JSON.stringify(refs[field]) !== JSON.stringify(value))) {
    errors.push('round_cap_binding_mismatch');
  }
  const material = _round_cap_receipt_material(policy);
  if (!_is_sha256(policy['round_cap_receipt_sha256']) || persisted_surface_sha256(material) !== policy['round_cap_receipt_sha256']) {
    errors.push('round_cap_receipt_hash_mismatch');
  }
  const source_sha = String(policy['source_block_fact_sha256'] || '');
  const source_event = String(policy['source_block_event'] || '');
  let source_index = -1;
  for (let index = prefix.length - 1; index >= 0; index--) {
    const fact = prefix[index];
    if (fact['ev'] === source_event && String(fact['aid'] || '') === aid && _fact_sha256(fact) === source_sha) {
      source_index = index;
      break;
    }
  }
  if (source_index < 0 || !_ROUND_CAP_BLOCK_EVENTS.has(source_event)) {
    errors.push('round_cap_source_block_receipt_missing');
    return errors;
  }
  let latest_block_index = -1;
  for (let index = 0; index < prefix.length; index++) {
    const fact = prefix[index];
    if (String(fact['aid'] || '') === aid && _ROUND_CAP_BLOCK_EVENTS.has(String(fact['ev'] || ''))) {
      latest_block_index = index;
    }
  }
  if (latest_block_index !== source_index || views.case_abandoned(prefix.filter((fact: Record<string, any>) => String(fact['aid'] || '') === aid))) {
    errors.push('round_cap_source_block_not_active');
  }
  const source = prefix[source_index];
  const { unconfirmed_processing_end } = require("./authoring_stops");
  if (unconfirmed_processing_end(source)) {
    errors.push('round_cap_processing_responsibility_unconfirmed');
    return errors;
  }
  const raw_block_round = source['round'] !== undefined ? source['round'] : 0;
  if (typeof raw_block_round !== 'number' || raw_block_round < 0) {
    errors.push('round_cap_counter_invalid');
    return errors;
  }
  const released = prefix.slice(source_index + 1).some((fact: Record<string, any>) =>
    fact['ev'] === 'conflict_chain_reentered' && String(fact['aid'] || '') === aid && typeof fact['round'] === 'number' && fact['round'] > raw_block_round
  );
  if (released) {
    errors.push('round_cap_source_block_not_active');
  }
  const prior_reentry_round = Math.max(0, ...prefix.filter((fact: Record<string, any>) => String(fact['aid'] || '') === aid && fact['ev'] === 'conflict_chain_reentered' && typeof fact['round'] === 'number' && fact['round'] >= 0).map((fact: Record<string, any>) => fact['round']));
  const expected_rounds = Math.max(raw_block_round, prior_reentry_round, fact_rules.effective_rounds_used(prefix, aid));
  const expected_granted = shared.granted_rounds(prefix, aid);
  const base_max = policy['base_max_rounds'];
  if (typeof base_max !== 'number' || base_max <= 0) {
    errors.push('round_cap_counter_invalid');
    return errors;
  }
  const effective_max = base_max + expected_granted;
  if (policy['rounds_used'] !== expected_rounds || policy['granted_rounds'] !== expected_granted || policy['effective_max_rounds'] !== effective_max) {
    errors.push('round_cap_counter_mismatch');
  }
  const reduction = reduce_blocked_reentry({ rounds_used: expected_rounds, max_rounds: effective_max });
  if (!reduction.valid || reduction.action !== ReentryAction.ABANDON || reduction.reason !== 'round_cap_reached') {
    errors.push('round_cap_reduction_not_abandon');
  }
  return errors;
}

export function _round_cap_receipt_material(policy: Record<string, any>): Record<string, any> {
  const material: Record<string, any> = {
    'run_id': String(policy['run_id'] || ''),
    'autoid': String(policy['aid'] || ''),
    'case_name': String(policy['case_name'] || ''),
    'base_max_rounds': policy['base_max_rounds'],
    'granted_rounds': policy['granted_rounds'],
    'rounds_used': policy['rounds_used'],
    'effective_max_rounds': policy['effective_max_rounds'],
    'source_block_event': String(policy['source_block_event'] || ''),
    'source_block_fact_sha256': String(policy['source_block_fact_sha256'] || ''),
    'stop_reason': String(policy['stop_reason'] || ''),
    'volume': String(policy['volume'] || ''),
  };
  return material;
}

export function _validate_xml_absence(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const fact = _find_fact_by_sha(facts, { aid, ev: 'xml_absence_terminal', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!fact || Object.keys(fact).length === 0) {
    return ['xml_absence_terminal_receipt_missing'];
  }
  const errors: string[] = [];
  const claims = fact['claims'];
  const vetoes = _xml_absence_veto_claims(claims);
  const valid_vetoes = vetoes.filter((claim: Record<string, any>) =>
    _is_nonempty_text(claim['command']) && _is_nonempty_text(claim['reason']) && claim['xml_basis'] && typeof claim['xml_basis'] === 'object' && !Array.isArray(claim['xml_basis']) && _is_nonempty_text(claim['xml_basis']['build']) && _is_nonempty_text(claim['xml_basis']['source_filename']) && _is_sha256(claim['xml_basis']['source_sha256'])
  );
  if (fact['blocking_class'] !== 'manual_error_confirmed' || fact['xml_absence_receipt_schema'] !== XML_ABSENCE_RECEIPT_SCHEMA || !Array.isArray(claims) || vetoes.length === 0 || valid_vetoes.length !== vetoes.length || String(fact['reason'] || '') !== String(vetoes.length > 0 ? vetoes[0]['reason'] : '设备 XML 命令树未收录该命令，设备不支持这个功能')) {
    errors.push('xml_absence_veto_contract_invalid');
  }
  const expected_claims_sha = Array.isArray(claims) ? persisted_surface_sha256(claims) : '';
  const expected_veto_hashes = vetoes.map((claim: Record<string, any>) => persisted_surface_sha256(claim));
  if (fact['claims_sha256'] !== expected_claims_sha || JSON.stringify(fact['veto_claim_sha256s']) !== JSON.stringify(expected_veto_hashes)) {
    errors.push('xml_absence_claim_receipt_mismatch');
  }
  const material = _xml_absence_receipt_material(fact);
  if (!_is_sha256(fact['xml_absence_receipt_sha256']) || persisted_surface_sha256(material) !== fact['xml_absence_receipt_sha256']) {
    errors.push('xml_absence_receipt_hash_mismatch');
  }
  const expected_refs: Record<string, any> = {};
  for (const field of _XML_ABSENCE_RECEIPT_FIELDS) {
    expected_refs[field] = fact[field];
  }
  if (Object.entries(expected_refs).some(([field, value]) => JSON.stringify(refs[field]) !== JSON.stringify(value))) {
    errors.push('xml_absence_binding_mismatch');
  }
  return errors;
}

export function _validate_central_delivery_device(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const verdict = _find_fact_by_sha(facts, { aid, ev: 'verdict', expected_sha256: String(refs['verdict_fact_sha256'] || '') });
  if (!verdict || Object.keys(verdict).length === 0 || !_CENTRAL_DEVICE_CONTEXTS[String(verdict['ctx'] || '')]) {
    return ['device_delivery_verdict_receipt_missing'];
  }
  const expected_source = _CENTRAL_DEVICE_CONTEXTS[String(verdict['ctx'])];
  if (refs['attempt_source'] !== expected_source || verdict['dispatch_scope'] !== expected_source) {
    errors.push('device_attempt_source_mismatch');
  }
  const run_id = String(verdict['run_id'] || '');
  const required_equal: Record<string, any> = {
    'run_id': run_id,
    'oracle_result': String(verdict['result'] || ''),
    'artifact': String(verdict['artifact'] || ''),
    'volume': String(verdict['volume'] || ''),
    'volume_artifact_sha256': String(verdict['volume_artifact_sha256'] || ''),
    'batch_run_id': String(verdict['batch_run_id'] || ''),
    'dispatch_id': String(verdict['dispatch_id'] || ''),
    'dispatch_scope': String(verdict['dispatch_scope'] || ''),
    'bed': String(verdict['bed'] || ''),
    'build': String(verdict['build'] || ''),
  };
  const terminal_binding: Record<string, any> = {
    'terminal_verdict_fact_sha256': _fact_sha256(verdict),
    'terminal_run_id': run_id,
    'terminal_artifact': String(verdict['artifact'] || ''),
    'terminal_oracle_result': String(verdict['result'] || ''),
  };
  if (Object.entries(required_equal).some(([key, value]) => key !== 'volume_artifact_sha256' && !_is_nonempty_text(value)) || !_is_sha256(required_equal['volume_artifact_sha256'])) {
    errors.push('device_attempt_identity_incomplete');
  }
  if (!['pass', 'fail'].includes(required_equal['oracle_result'])) {
    errors.push('device_delivery_verdict_inconclusive');
  }
  if (Object.entries(required_equal).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('device_attempt_binding_mismatch');
  }
  if (Object.entries(terminal_binding).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('device_terminal_binding_mismatch');
  }
  const attribution = _find_fact_by_sha(facts, { aid, ev: 'attribution', expected_sha256: String(refs['attribution_fact_sha256'] || '') });
  if (!attribution || Object.keys(attribution).length === 0 || String(attribution['run_id'] || '') !== run_id || ['user', 'engine_auto'].includes(String(attribution['source'] || '')) || refs['attribution_layer'] !== String(attribution['layer'] || '') || refs['attribution_disposition'] !== String(attribution['disposition'] || '')) {
    errors.push('device_attribution_receipt_missing');
  } else if (String(attribution['layer'] || '') !== 'product_defect') {
    errors.push('device_attribution_layer_mismatch');
  }
  const causality = _delivery_evidence_corpus_text(verdict);
  const quotes = Array.isArray(refs['verbatim_evidence']) ? refs['verbatim_evidence'] : [];
  if (quotes.length === 0 || quotes.some((quote: any) => typeof quote !== 'string' || quote.trim().length < 8 || !causality.includes(quote.trim())) || (attribution && Object.keys(attribution).length > 0 && !quotes.map((q: any) => String(q).trim()).includes(String(attribution['evidence'] || '').trim()))) {
    errors.push('device_verbatim_evidence_missing');
  }
  return errors;
}

export function _validate_device(aid: string, refs: Record<string, any>, facts: Record<string, any>[], case_dir: any, opts: { outcome: string }): string[] {
  const { outcome } = opts;
  const errors: string[] = [];
  let terminal_verdict: Record<string, any> = {};
  if (outcome === 'device_defect') {
    terminal_verdict = _find_fact_by_sha(facts, { aid, ev: 'verdict', expected_sha256: String(refs['terminal_verdict_fact_sha256'] || refs['verdict_fact_sha256'] || '') });
    if (!terminal_verdict || Object.keys(terminal_verdict).length === 0 || !_CENTRAL_DEVICE_CONTEXTS[String(terminal_verdict['ctx'] || '')] || !['pass', 'fail'].includes(String(terminal_verdict['result'] || ''))) {
      return ['device_terminal_verdict_receipt_missing'];
    }
    const selected_terminal = _attributed_central_device_verdict(aid, facts);
    if (!selected_terminal || Object.keys(selected_terminal).length === 0 || _fact_sha256(selected_terminal) !== _fact_sha256(terminal_verdict)) {
      return ['device_terminal_binding_mismatch'];
    }
  }
  const selected_attempt = _worker_device_attempt(aid, facts, { terminal_verdict: outcome === 'device_defect' ? terminal_verdict : null });
  const source = selected_attempt && Object.keys(selected_attempt).length > 0 ? 'worker_device_attempt' : _CENTRAL_DEVICE_CONTEXTS[String(terminal_verdict['ctx'] || '')] || 'central_delivery';
  if (String(refs['attempt_source'] || 'worker_device_attempt') !== source) {
    return ['device_attempt_source_mismatch'];
  }
  if (Object.values(_CENTRAL_DEVICE_CONTEXTS).includes(source)) {
    return _validate_central_delivery_device(aid, refs, facts);
  }
  const attempt = _find_fact_by_sha(facts, { aid, ev: 'worker_device_attempt', expected_sha256: String(refs['attempt_fact_sha256'] || '') });
  if (!attempt || Object.keys(attempt).length === 0) {
    errors.push('device_attempt_receipt_missing');
    return errors;
  }
  if (_fact_sha256(attempt) !== _fact_sha256(selected_attempt)) {
    errors.push('device_attempt_source_mismatch');
  }
  const required_equal: Record<string, any> = {
    'run_id': String(attempt['run_id'] || ''),
    'oracle_result': String(attempt['oracle_result'] || attempt['verdict'] || attempt['result'] || ''),
    'artifact': String(attempt['artifact'] || ''),
    'artifact_sha256': String(attempt['artifact_sha256'] || ''),
    'remote_artifact_sha256': String(attempt['remote_artifact_sha256'] || ''),
    'lint_credential_id': String(attempt['lint_credential_id'] || ''),
    'dispatch_id': String(attempt['dispatch_id'] || ''),
    'batch_run_id': String(attempt['batch_run_id'] || ''),
    'bed_lease_id': String(attempt['bed_lease_id'] || ''),
    'env_id': String(attempt['env_id'] || ''),
    'bed': String(attempt['bed'] || ''),
    'build': String(attempt['build'] || ''),
    'module': String(attempt['module'] || ''),
    'lease_acquired_persisted': attempt['lease_acquired_persisted'] === true,
    'lease_released_persisted': attempt['lease_released_persisted'] === true,
  };
  if (Object.entries(required_equal).some(([key, value]) => !['artifact_sha256', 'remote_artifact_sha256', 'lease_acquired_persisted', 'lease_released_persisted'].includes(key) && !_is_nonempty_text(value)) || !_is_sha256(required_equal['artifact_sha256']) || !_is_sha256(required_equal['remote_artifact_sha256'])) {
    errors.push('device_attempt_identity_incomplete');
  }
  if (!['pass', 'fail'].includes(required_equal['oracle_result'])) {
    errors.push('device_worker_verdict_inconclusive');
  }
  if (outcome === 'device_defect') {
    const terminal_binding: Record<string, any> = {
      'terminal_verdict_fact_sha256': _fact_sha256(terminal_verdict),
      'terminal_run_id': String(terminal_verdict['run_id'] || ''),
      'terminal_artifact': String(terminal_verdict['artifact'] || ''),
      'terminal_oracle_result': String(terminal_verdict['result'] || ''),
    };
    if (Object.entries(terminal_binding).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value)) || required_equal['run_id'] !== terminal_binding['terminal_run_id'] || required_equal['artifact'] !== terminal_binding['terminal_artifact'] || required_equal['oracle_result'] !== terminal_binding['terminal_oracle_result']) {
      errors.push('device_terminal_binding_mismatch');
    }
  }
  if (required_equal['artifact_sha256'] !== required_equal['remote_artifact_sha256']) {
    errors.push('device_remote_artifact_mismatch');
  }
  if (required_equal['lease_acquired_persisted'] !== true || required_equal['lease_released_persisted'] !== true) {
    errors.push('device_lease_lifecycle_incomplete');
  }
  if (attempt['credential_valid'] === false) {
    errors.push('device_attempt_identity_rejected');
  }
  if (Object.entries(required_equal).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('device_attempt_binding_mismatch');
  }
  const receipt = refs['echo_receipt'] && typeof refs['echo_receipt'] === 'object' && !Array.isArray(refs['echo_receipt']) ? refs['echo_receipt'] : {};
  const name = String(receipt['name'] || '');
  const payload = case_dir !== null && case_dir !== undefined && _ECHO_NAME_RE.test(name) ? _read_case_file(case_dir, name) : null;
  let evidence_surface = '';
  if (payload === null) {
    errors.push('device_echo_unavailable');
  } else {
    let echo_text = '';
    try {
      echo_text = payload.toString('utf8');
    } catch {
      echo_text = '';
      errors.push('device_echo_unavailable');
    }
    evidence_surface = scrub_text(echo_text, { scrub_paths: false });
    if (!_is_sha256(receipt['bytes_sha256']) || crypto.createHash('sha256').update(payload).digest('hex') !== String(receipt['bytes_sha256'] || '') || payload.length !== receipt['size']) {
      errors.push('device_echo_bytes_mismatch');
    }
    if (!_is_sha256(receipt['evidence_surface_sha256']) || crypto.createHash('sha256').update(evidence_surface, 'utf8').digest('hex') !== String(receipt['evidence_surface_sha256'] || '')) {
      errors.push('device_echo_evidence_surface_mismatch');
    }
  }
  const quotes = Array.isArray(refs['verbatim_evidence']) ? refs['verbatim_evidence'] : [];
  if (quotes.length === 0 || quotes.some((quote: any) => typeof quote !== 'string' || quote.trim().length < 8 || !evidence_surface.includes(quote.trim()))) {
    errors.push('device_verbatim_evidence_missing');
  }
  return errors;
}

export function _attributed_central_device_verdict(aid: string, facts: Record<string, any>[]): Record<string, any> {
  const attribution = _current_attribution(aid, facts, { layer: 'product_defect' });
  if (!attribution) {
    return {};
  }
  const run_id = String(attribution['run_id'] || '');
  const verdicts = facts.filter((f: Record<string, any>) => f['ev'] === 'verdict' && String(f['aid'] || '') === aid && String(f['run_id'] || '') === run_id && _CENTRAL_DEVICE_CONTEXTS[String(f['ctx'] || '')]);
  return verdicts.length > 0 ? verdicts[verdicts.length - 1] : {};
}

export function _validate_authoring_failure(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'authoring_failure', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['authoring_failure_terminal_receipt_missing'];
  }
  const expected: Record<string, any> = {
    'run_id': String(terminal['run_id'] || ''),
    'cause': String(terminal['cause'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('authoring_failure_binding_mismatch');
  }
  if (!_is_nonempty_text(expected['cause'])) {
    errors.push('authoring_failure_identity_incomplete');
  }
  return errors;
}

export function _validate_author_definition_gap(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'abandoned', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['author_definition_gap_terminal_receipt_missing'];
  }
  if (String(terminal['blocking_class'] || '') !== 'author_definition_gap') {
    errors.push('author_definition_gap_terminal_contract_mismatch');
  }
  const expected: Record<string, any> = {
    'run_id': String(terminal['run_id'] || ''),
    'variant': String(terminal['variant'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('author_definition_gap_binding_mismatch');
  }
  if (![_AUTHORING_GAP_VARIANT, _AUTHORING_CONFLICT_VARIANT].includes(expected['variant'])) {
    errors.push('author_definition_gap_variant_invalid');
  }
  return errors;
}

export function _validate_ought(aid: string, refs: Record<string, any>, facts: Record<string, any>[], case_dir: any): string[] {
  const errors: string[] = [];
  const qid = String(refs['question_id'] || '');
  const question_sha = String(refs['question_fact_sha256'] || '');
  const question = _find_fact_by_sha(facts, { aid, ev: 'needs_decision', expected_sha256: question_sha });
  if (!qid || !question || Object.keys(question).length === 0 || String(question['question_id'] || '') !== qid || facts.some((fact: Record<string, any>) => _decision_resolves_question(fact) && String(fact['aid'] || '') === aid && String(fact['question_id'] || '') === qid)) {
    errors.push('ought_latest_unanswered_question_missing');
  }
  const receipt = refs['ledger_receipt'] && typeof refs['ledger_receipt'] === 'object' && !Array.isArray(refs['ledger_receipt']) ? refs['ledger_receipt'] : {};
  let payload: Buffer | null = null;
  if (case_dir === null || case_dir === undefined) {
    errors.push('ought_ledger_unavailable');
  } else {
    payload = _read_case_file(case_dir, 'needs_decision.json');
    if (payload === null) {
      errors.push('ought_ledger_unavailable');
    }
  }
  if (payload !== null && (!_is_sha256(receipt['bytes_sha256']) || crypto.createHash('sha256').update(payload).digest('hex') !== String(receipt['bytes_sha256'] || '') || payload.length !== receipt['size'])) {
    errors.push('ought_ledger_bytes_mismatch');
  }
  const claims = Array.isArray(refs['claims']) ? refs['claims'] : [];
  const structured = _structured_claims(claims);
  const receipts = Array.isArray(refs['claim_receipts']) ? refs['claim_receipts'] : [];
  if (structured.length === 0 || structured.length !== claims.length) {
    errors.push('ought_structured_claim_missing');
  }
  const expected_receipts = structured.map((claim: Record<string, any>) => ({
    'claim_kind': String(claim['claim_kind'] || ''),
    'claim_sha256': _object_sha256(claim),
    'source_quote_sha256': (claim['sources'] || []).map((source: any) => crypto.createHash('sha256').update(String(source['quote'] || ''), 'utf8').digest('hex')),
  }));
  if (JSON.stringify(receipts) !== JSON.stringify(expected_receipts)) {
    errors.push('ought_claim_receipt_mismatch');
  }
  if (payload !== null) {
    let ledger: Record<string, any> | null = null;
    try {
      ledger = pyJsonLoads(payload);
    } catch {
      ledger = null;
    }
    const persisted_ledger_claims = ledger && typeof ledger === 'object' && !Array.isArray(ledger) ? _structured_claims(canonical_persisted_value(_structured_claims(ledger['claims']))) : [];
    if (!ledger || typeof ledger !== 'object' || Array.isArray(ledger) || JSON.stringify(persisted_ledger_claims) !== JSON.stringify(claims)) {
      errors.push('ought_claim_not_bound_to_ledger');
    }
  }
  return errors;
}

export function _decision_resolves_question(fact: Record<string, any>): boolean {
  return _DECISION_RESOLVE_EVENTS.has(String(fact['ev'] || ''));
}

export function _validate_compile(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const errors: string[] = [];
  const decision = _find_fact_by_sha(facts, { aid, ev: 'no_progress_decision', expected_sha256: String(refs['decision_fact_sha256'] || '') });
  if (!decision || Object.keys(decision).length === 0 || String(decision['decision_id'] || '') !== String(refs['decision_id'] || '')) {
    errors.push('compile_decision_receipt_missing');
    return errors;
  }
  const expected: Record<string, any> = {
    'domain': String(decision['domain'] || ''),
    'failure_key': String(decision['failure_key'] || ''),
    'streak': decision['streak'],
    'threshold': decision['threshold'],
    'revision_refs': decision['revision_refs'] || [],
    'stop': decision['stop'],
  };
  const observed: Record<string, any> = {};
  for (const key of Object.keys(expected)) {
    observed[key] = refs[key];
  }
  if (expected['domain'] !== 'compile' || expected['stop'] !== true || !_is_nonempty_text(expected['failure_key']) || !expected['revision_refs'] || expected['revision_refs'].length === 0 || JSON.stringify(observed) !== JSON.stringify(expected)) {
    errors.push('compile_no_progress_decision_invalid');
  }
  return errors;
}

export function _validate_suspension(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const fact = _find_fact_by_sha(facts, { aid, ev: 'suspended', expected_sha256: String(refs['suspension_fact_sha256'] || '') });
  const active = _active_suspension_fact(aid, facts);
  if (!fact || Object.keys(fact).length === 0 || !active || Object.keys(active).length === 0 || _fact_sha256(active) !== _fact_sha256(fact)) {
    return ['suspension_active_receipt_missing'];
  }
  const errors: string[] = [];
  const expected_reason = String(fact['reason'] || '');
  const expected_question_id = String(fact['question_id'] || '');
  if (!_is_nonempty_text(expected_reason)) {
    errors.push('suspension_reason_missing');
  }
  if (String(refs['reason'] || '') !== expected_reason || String(refs['question_id'] || '') !== expected_question_id) {
    errors.push('suspension_binding_mismatch');
  }
  if (fact['suspension_kind'] === 'execution_pause') {
    if (fact['source'] !== 'engine_auto') {
      errors.push('execution_pause_issuer_invalid');
    }
    const fields = ['suspension_kind', 'pause_kind', 'basis_status', 'source_fact_sha256', 'source_event', 'source_run_id', 'evidence', 'fix_direction'] as const;
    if (fields.some((key) => JSON.stringify(refs[key]) !== JSON.stringify(fact[key]))) {
      errors.push('execution_pause_binding_mismatch');
    }
    const { PAUSE_CREDENTIAL_KINDS: _PAUSE_KINDS } = require("./forced_closure");
    if (!_PAUSE_KINDS.has(String(fact['pause_kind'] || ''))) {
      errors.push('execution_pause_kind_invalid');
    }
    if (fact['basis_status'] === 'source_bound') {
      const source = _find_fact_by_sha(facts, { aid, ev: String(fact['source_event'] || ''), expected_sha256: String(fact['source_fact_sha256'] || '') });
      if (!source || Object.keys(source).length === 0) {
        errors.push('execution_pause_source_missing');
      } else if (!(fact['pause_kind'] === 'env' && source['ev'] === 'attribution' && source['disposition'] === 'env_blocked' || fact['pause_kind'] === 'bed' && source['ev'] === 'diagnosis' && String(source['h_position'] || '').startsWith('h_s0') || fact['pause_kind'] === 'contra' && source['ev'] === 'verdict' || fact['pause_kind'] === 'api' && ['escalated', 'worker_loop_outcome', 'engine_error'].includes(String(source['ev'] || '')))) {
        errors.push('execution_pause_source_kind_mismatch');
      } else if (fact['pause_kind'] !== 'api' && (String(source['run_id'] || '') !== fact['source_run_id'] || String(source['evidence'] || source['reason'] || source['basis'] || '') !== fact['evidence'] || String(source['fix_direction'] || '') !== fact['fix_direction'])) {
        errors.push('execution_pause_source_mismatch');
      }
    } else if (fact['basis_status'] !== 'source_unavailable' || fact['source_fact_sha256'] || fact['evidence']) {
      errors.push('execution_pause_source_status_invalid');
    }
  }
  return errors;
}

export function _validate_execution_failure(aid: string, outcome: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const { MAX_EXECUTION_ATTEMPTS, NO_DEVICE_REEXECUTION_REASON_CODES, classify_reason_code, current_execution_implementation_sha256, is_runtime_infrastructure_terminal_fact, reason_code_categories, terminal_action_for_category } = require("./execution_failure");
  const { device_prerequisite_receipt_sha256, validate_device_prerequisite_receipts } = require("../tools/device/batch_result_protocol");
  const terminal_event = String(refs['event'] || '');
  const terminal = _find_fact_by_sha(facts, { aid, ev: terminal_event, expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  const failure = _find_fact_by_sha(facts, { aid, ev: 'execution_failure', expected_sha256: String(refs['failure_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['execution_terminal_receipt_missing'];
  }
  if (!failure || Object.keys(failure).length === 0) {
    return ['execution_failure_receipt_missing'];
  }
  const errors: string[] = [];
  const runtime_infrastructure_terminal = is_runtime_infrastructure_terminal_fact(terminal);
  if (!(outcome === 'blocked' && runtime_infrastructure_terminal || outcome === 'ist_core_defect' && terminal_event === 'ist_core_defect' || outcome === 'unable_to_compile' && terminal_event === outcome)) {
    errors.push('execution_terminal_outcome_mismatch');
  }
  const expected: Record<string, any> = {
    'event': terminal_event,
    'reason_code': String(terminal['reason_code'] || ''),
    'category': String(terminal['category'] || ''),
    'attempt': terminal['attempt'],
    'artifact_sha256': String(terminal['artifact_sha256'] || ''),
    'bed_host': String(terminal['bed_host'] || ''),
    'build': String(terminal['build'] || ''),
    'implementation_sha256': String(terminal['implementation_sha256'] || ''),
    'prerequisite_receipt_sha256': String(terminal['prerequisite_receipt_sha256'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('execution_terminal_binding_mismatch');
  }
  const no_reexecution = NO_DEVICE_REEXECUTION_REASON_CODES.has(expected['reason_code']);
  const terminal_attempt = expected['attempt'];
  if (typeof terminal_attempt !== 'number' || terminal_attempt < 1 || terminal_attempt > MAX_EXECUTION_ATTEMPTS || (!no_reexecution && terminal_attempt !== MAX_EXECUTION_ATTEMPTS) || failure['attempt'] !== terminal_attempt || String(failure['action'] || '') !== terminal_event) {
    errors.push('execution_retry_budget_not_exhausted');
  }
  let terminal_index = facts.length;
  for (let index = 0; index < facts.length; index++) {
    if (facts[index] === terminal) {
      terminal_index = index;
      break;
    }
  }
  const comparable: Record<string, any>[] = [];
  for (const fact of facts.slice(0, terminal_index)) {
    if (String(fact['aid'] || '') !== aid || ['artifact_sha256', 'bed_host', 'build', 'implementation_sha256'].some((key) => String(fact[key] || '') !== expected[key])) {
      continue;
    }
    if (fact['ev'] === 'execution_success') {
      comparable.length = 0;
    } else if (fact['ev'] === 'execution_failure') {
      comparable.push(fact);
    }
  }
  const expected_attempts = Array.from({ length: Number(terminal_attempt || 0) }, (_, i) => i + 1);
  const expected_actions = [...Array(Math.max(0, expected_attempts.length - 1)).fill('retry'), terminal_event];
  if (JSON.stringify(comparable.map((f: Record<string, any>) => f['attempt'])) !== JSON.stringify(expected_attempts) || JSON.stringify(comparable.map((f: Record<string, any>) => String(f['action'] || ''))) !== JSON.stringify(expected_actions)) {
    errors.push('execution_attempt_sequence_invalid');
  }
  for (const key of ['reason_code', 'category', 'artifact_sha256', 'bed_host', 'build', 'implementation_sha256', 'prerequisite_receipt_sha256']) {
    if (String(failure[key] || '') !== String(terminal[key] || '')) {
      errors.push('execution_failure_terminal_mismatch');
      break;
    }
  }
  if (!_is_sha256(expected['artifact_sha256'])) {
    errors.push('execution_artifact_identity_invalid');
  }
  if (!_is_nonempty_text(expected['bed_host']) || typeof expected['build'] !== 'string') {
    errors.push('execution_environment_identity_invalid');
  }
  if (!_is_sha256(expected['implementation_sha256']) || expected['implementation_sha256'] !== current_execution_implementation_sha256()) {
    errors.push('execution_implementation_identity_stale');
  }
  if (!reason_code_categories()[expected['reason_code']]) {
    errors.push('execution_reason_code_invalid');
  } else {
    const category = classify_reason_code(expected['reason_code']);
    const legacy_runtime_category = runtime_infrastructure_terminal && terminal_event === 'ist_core_defect' && expected['category'] === 'engine_rejection';
    if (category !== expected['category'] && !legacy_runtime_category) {
      errors.push('execution_category_mismatch');
    }
    if (runtime_infrastructure_terminal) {
      const allowed_outcomes = new Set(['blocked']);
      if (terminal_event === 'ist_core_defect') {
        allowed_outcomes.add('ist_core_defect');
      }
      if (!allowed_outcomes.has(outcome)) {
        errors.push('execution_terminal_action_mismatch');
      }
    } else if (terminal_action_for_category(category) !== outcome) {
      errors.push('execution_terminal_action_mismatch');
    }
  }
  const prerequisite_sha256 = expected['prerequisite_receipt_sha256'];
  if (expected['reason_code'] === 'device_prerequisite_unmet') {
    const receipt_fact = facts.find((fact: Record<string, any>) =>
      typeof fact === 'object' && fact !== null && !Array.isArray(fact) &&
      fact['ev'] === 'device_prerequisite_receipt' && String(fact['aid'] || '') === aid &&
      fact['attempt'] === MAX_EXECUTION_ATTEMPTS && String(fact['receipt_sha256'] || '') === prerequisite_sha256 &&
      ['artifact_sha256', 'bed_host', 'build', 'implementation_sha256'].every((key) => String(fact[key] || '') === expected[key])
    ) || {};
    if (!_is_sha256(prerequisite_sha256) || Object.keys(receipt_fact).length === 0) {
      errors.push('execution_prerequisite_receipt_missing');
    } else {
      try {
        const normalized = validate_device_prerequisite_receipts([receipt_fact['receipt']], { expected_autoids: new Set([aid]), artifact_sha256: expected['artifact_sha256'], bed_host: expected['bed_host'] })[0];
        if (device_prerequisite_receipt_sha256(normalized) !== prerequisite_sha256 || String(receipt_fact['run_id'] || '') !== normalized['run_id']) {
          throw new Error('receipt digest or run binding mismatch');
        }
      } catch {
        errors.push('execution_prerequisite_receipt_invalid');
      }
    }
  } else if (prerequisite_sha256) {
    errors.push('execution_prerequisite_receipt_unexpected');
  }
  if (['blocked', 'ist_core_defect'].includes(outcome)) {
    if (terminal['reentrant'] !== true || terminal['terminal'] !== false) {
      errors.push('execution_reentry_contract_mismatch');
    }
  } else if (terminal['reentrant'] !== false || terminal['terminal'] !== true) {
    errors.push('execution_reentry_contract_mismatch');
  }
  return errors;
}

export function _validate_unattributed_stop(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const { BLOCKED, UNATTRIBUTED_LAYER, UNPROVEN_STOP_CAUSES, unproven_stop_position } = require("./terminal_outcomes");
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'blocked', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['unattributed_stop_terminal_receipt_missing'];
  }
  const source_sha256 = String(refs['source_fact_sha256'] || '');
  const source_event = String(refs['source_event'] || '');
  const source = facts.find((fact: Record<string, any>) =>
    String(fact['ev'] || '') === source_event && _fact_sha256(fact) === source_sha256 && [aid, ''].includes(String(fact['aid'] || ''))
  ) || {};
  const errors: string[] = [];
  const expected: Record<string, any> = {
    'reason_code': String(terminal['reason_code'] || ''),
    'stop_cause': String(terminal['stop_cause'] || ''),
    'round': terminal['round'],
    'source_event': String(terminal['source_event'] || ''),
    'source_fact_sha256': String(terminal['source_fact_sha256'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('unattributed_stop_binding_mismatch');
  }
  if (Object.keys(source).length === 0) {
    errors.push('unattributed_stop_source_receipt_missing');
  }
  if (terminal['reason_code'] === 'authoring_evidence_unclosed' && Object.keys(source).length > 0) {
    const { has_rejected_draft_context, validate_rejected_draft_terminal } = require("./authoring_evidence");
    if (has_rejected_draft_context(source)) {
      errors.push(...validate_rejected_draft_terminal(terminal, facts));
    }
  }
  if (String(terminal['terminal_layer'] || '') !== UNATTRIBUTED_LAYER || terminal['reentrant'] !== true || terminal['terminal'] !== false || !_is_nonempty_text(expected['reason_code']) || !_is_nonempty_text(expected['source_event']) || !_is_sha256(expected['source_fact_sha256']) || typeof expected['round'] !== 'number' || expected['round'] < 0) {
    errors.push('unattributed_stop_contract_mismatch');
  }
  if (!UNPROVEN_STOP_CAUSES.has(expected['stop_cause']) || unproven_stop_position(expected['stop_cause']) !== BLOCKED) {
    errors.push('unattributed_stop_cause_outside_closed_set');
  }
  if (Object.keys(source).length > 0 && expected['stop_cause']) {
    const { unproven_stop_cause } = require("./authoring_evidence");
    if (unproven_stop_cause(source, { facts }) !== expected['stop_cause']) {
      errors.push('unattributed_stop_cause_not_replayed');
    }
    const { CAUSE, pause_observations } = require("./contradiction_stop");
    if (expected['stop_cause'] === CAUSE) {
      if (terminal['reason_code'] !== CAUSE || terminal['pause_kind'] !== 'contra' || JSON.stringify(terminal['contra_observations']) !== JSON.stringify(pause_observations(source, facts))) {
        errors.push('contradiction_stop_observations_mismatch');
      }
    }
  }
  return errors;
}

export function _validate_engine_defect(aid: string, refs: Record<string, any>, facts: Record<string, any>[]): string[] {
  const terminal = _find_fact_by_sha(facts, { aid, ev: 'ist_core_defect', expected_sha256: String(refs['terminal_fact_sha256'] || '') });
  if (!terminal || Object.keys(terminal).length === 0) {
    return ['engine_defect_terminal_receipt_missing'];
  }
  let governance_errors: string[] = [];
  if (terminal['reason_code'] === 'governance_end_unclosed') {
    const { validate_governance_end } = require("./authoring_stops");
    governance_errors = validate_governance_end(terminal, facts);
  }
  const source_sha256 = String(refs['source_fact_sha256'] || '');
  const source_event = String(refs['source_event'] || '');
  const source = facts.find((fact: Record<string, any>) =>
    String(fact['aid'] || '') === aid && String(fact['ev'] || '') === source_event && _fact_sha256(fact) === source_sha256
  ) || {};
  const errors: string[] = [...governance_errors];
  const expected: Record<string, any> = {
    'reason_code': String(terminal['reason_code'] || ''),
    'round': terminal['round'],
    'source_event': String(terminal['source_event'] || ''),
    'source_fact_sha256': String(terminal['source_fact_sha256'] || ''),
  };
  if (Object.entries(expected).some(([key, value]) => JSON.stringify(refs[key]) !== JSON.stringify(value))) {
    errors.push('engine_defect_binding_mismatch');
  }
  if (Object.keys(source).length === 0) {
    errors.push('engine_defect_source_receipt_missing');
  }
  if (terminal['reason_code'] === 'authoring_evidence_unclosed' && Object.keys(source).length > 0) {
    const { has_rejected_draft_context, validate_rejected_draft_terminal } = require("./authoring_evidence");
    if (has_rejected_draft_context(source)) {
      errors.push(...validate_rejected_draft_terminal(terminal, facts));
    }
  }
  if (String(terminal['terminal_layer'] || '') !== 'engine' || terminal['reentrant'] !== true || terminal['terminal'] !== false || !_is_nonempty_text(expected['reason_code']) || !_is_nonempty_text(expected['source_event']) || !_is_sha256(expected['source_fact_sha256']) || typeof expected['round'] !== 'number' || expected['round'] < 0) {
    errors.push('engine_defect_contract_mismatch');
  }
  return errors;
}

export function validate_terminal_credential(terminal: Record<string, any>, opts: { facts: Iterable<Record<string, any>>; case_dir?: any }): [boolean, string[]] {
  const { facts, case_dir = null } = opts;
  const { CASE_TERMINAL_OUTCOMES } = require("./terminal_outcomes");
  const outcome = String(terminal['outcome'] || '');
  if (!CASE_TERMINAL_OUTCOMES.has(outcome)) {
    return [false, ['outcome_outside_closed_set']];
  }
  const refs = terminal['credential_refs'] && typeof terminal['credential_refs'] === 'object' && !Array.isArray(terminal['credential_refs']) ? terminal['credential_refs'] : {};
  if (refs['schema'] !== SCHEMA) {
    return [false, ['credential_schema_invalid']];
  }
  const kind = String(refs['kind'] || '');
  const aid = String(terminal['aid'] || '');
  const layer = String(terminal['layer'] || '');
  const rows = Array.from(facts).filter((fact: any) => typeof fact === 'object' && fact !== null && !Array.isArray(fact));
  const errors: string[] = [];
  if (kind === 'delivery') {
    if (outcome !== 'delivered' || layer !== 'delivery') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_delivery(aid, refs, rows, case_dir));
  } else if (kind === 'delivery_failure') {
    if (layer !== 'delivery') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_delivery_failure(aid, refs, rows, outcome));
  } else if (kind === 'authority_decision') {
    if (outcome !== 'blocked' || layer !== 'delivery') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_authority_decision(aid, refs, rows));
  } else if (kind === 'unsupported_feature') {
    if (outcome !== 'unable_to_compile' || layer !== 'unsupported_feature') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_unsupported_feature(aid, refs, rows));
  } else if (kind === 'not_compilable') {
    if (outcome !== 'abandoned' || layer !== 'not_compilable') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_not_compilable(aid, refs, rows));
  } else if (kind === 'source_conflict') {
    if (outcome !== 'abandoned' || layer !== 'source_conflict') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_source_conflict(aid, refs, rows));
  } else if (kind === 'source_conflict_blocked') {
    if (outcome !== 'blocked' || layer !== 'source_conflict_blocked') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_source_conflict_blocked(aid, refs, rows));
  } else if (kind === 'batch_user_abandon') {
    if (outcome !== 'abandoned' || layer !== 'batch_user_abandon') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_batch_user_abandon(aid, refs, rows, case_dir));
  } else if (kind === 'round_cap') {
    if (outcome !== 'abandoned' || layer !== 'round_cap') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_round_cap(aid, refs, rows));
  } else if (kind === 'authoring_failure') {
    if (outcome !== 'authoring_failure' || layer !== 'authoring') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_authoring_failure(aid, refs, rows));
  } else if (kind === 'author_definition_gap') {
    if (outcome !== 'abandoned' || layer !== 'author_definition_gap') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_author_definition_gap(aid, refs, rows));
  } else if (kind === 'xml_absence') {
    if (outcome !== 'unable_to_compile' || layer !== 'xml_absence') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_xml_absence(aid, refs, rows));
  } else if (kind === 'suspension') {
    if (outcome !== 'blocked' || layer !== 'suspension') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_suspension(aid, refs, rows));
  } else if (kind === 'execution_failure') {
    if (!_EXECUTION_TERMINAL_OUTCOMES.has(outcome) || layer !== 'execution') {
      errors.push('credential_kind_outcome_mismatch');
    } else {
      errors.push(..._validate_execution_failure(aid, outcome, refs, rows));
    }
  } else if (kind === 'engine_defect') {
    if (outcome !== 'ist_core_defect' || layer !== 'engine') {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_engine_defect(aid, refs, rows));
  } else if (kind === 'unattributed_stop') {
    if (outcome !== 'blocked' || layer !== _TO_UNATTRIBUTED_LAYER) {
      errors.push('credential_kind_outcome_mismatch');
    }
    errors.push(..._validate_unattributed_stop(aid, refs, rows));
  } else if (_NON_DELIVERY_LAYERS.has(kind)) {
    if (outcome === 'delivered' || layer !== kind) {
      errors.push('credential_kind_outcome_mismatch');
    }
    if (kind === 'ought' && outcome !== 'blocked') {
      errors.push('ought_outcome_mismatch');
    }
    if (kind === 'ought') {
      errors.push(..._validate_ought(aid, refs, rows, case_dir));
    } else if (kind === 'compile') {
      errors.push(..._validate_compile(aid, refs, rows));
    } else {
      errors.push(..._validate_device(aid, refs, rows, case_dir, { outcome }));
    }
  } else {
    errors.push('credential_kind_invalid');
  }
  return [errors.length === 0, Array.from(new Set(errors)).sort()];
}
