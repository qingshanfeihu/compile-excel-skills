import { Counter } from "../../_py";
import * as F from "./facts";
import { effective_authority_facts, is_authority_decision_terminal, is_authority_gap_disclosure, is_volume_identity_failure, unverified_authority_pending } from "./authority_delivery_policy";

export const S_PENDING = "pending";
export const S_AWAITING_USER = "awaiting_user";
export const S_COMPOSED = "composed";
export const S_AUTHORED = "authored";
export const S_FAILED = "failed";
export const S_BROKEN = "broken";
export const S_BROKEN_ERRORED = "broken_errored";
export const S_BROKEN_BLOCKED = "broken_blocked";
export const S_BROKEN_ABORTED = "broken_aborted";
export const S_BROKEN_VERDICT_UNRECOGNIZED = "broken_verdict_unrecognized";
export const S_SUBSET_VERIFIED = "subset_verified";
export const S_DELIVERABLE = "deliverable";
export const S_CONTRADICTED = "contradicted";
export const S_ESCALATED = "escalated";
export const S_QUARANTINED = "quarantined";
export const S_TERMINAL = "failed_terminal";
export const S_SUSPENDED = "suspended";
export const S_UNSUPPORTED_FEATURE = "unsupported_feature";
export const CASE_VIEW_STATES = new Set([
  S_PENDING,
  S_AWAITING_USER,
  S_COMPOSED,
  S_AUTHORED,
  S_FAILED,
  S_BROKEN,
  S_BROKEN_ERRORED,
  S_BROKEN_BLOCKED,
  S_BROKEN_ABORTED,
  S_BROKEN_VERDICT_UNRECOGNIZED,
  S_SUBSET_VERIFIED,
  S_DELIVERABLE,
  S_CONTRADICTED,
  S_ESCALATED,
  S_QUARANTINED,
  S_TERMINAL,
  S_SUSPENDED,
  S_UNSUPPORTED_FEATURE,
]);
export const SCENARIO2_REASON_CODE = "scenario2_incomplete_case";
const _REENTRANT_TERMINAL_EVENTS = new Set(["source_conflict_blocked", "authority_preflight_blocked", "blocked", "ist_core_defect", "intent_stamp_failed", "authoring_failure"]);
const _PERMANENT_TERMINAL_EVENTS = new Set(["xml_absence_terminal", "unable_to_compile"]);
const _V12_EXECUTION_TERMINAL_EVENTS = new Set(["blocked", "ist_core_defect", "unable_to_compile", "authoring_failure"]);

export function scenario2_abandon_active(mine: Record<string, any>[]): boolean {
  return mine.some((fact) => fact.ev === "policy_abandon" && fact.reason_code === SCENARIO2_REASON_CODE);
}

export function is_engineering_fault_terminal(fact: Record<string, any>): boolean {
  return Boolean(fact.ev === "attribution" && String(fact.disposition ?? "") === "engineering_fault" && fact.is_terminal && String(fact.run_id ?? "").trim());
}

export function case_abandoned(mine: Record<string, any>[]): boolean {
  return mine.some((fact) => fact.ev === "policy_abandon");
}

export function direct_abandon_terminal(mine: Record<string, any>[]): Record<string, any> {
  const { is_direct_abandon_decision } = require("./conflict_chain");
  if (!mine.some((fact) => is_direct_abandon_decision(fact))) {
    if (!_author_side_conflict_abandon(mine)) return {};
  }
  const abandons = mine.filter((f) => f.ev === "policy_abandon");
  return abandons.length ? abandons[abandons.length - 1] : {};
}

function _author_side_conflict_abandon(mine: Record<string, any>[]): boolean {
  const BT = require("./blocking_taxonomy");
  if (!mine.some((fact) => fact.ev === "consistency_verdict" && String(fact.verdict ?? "") === "conflict")) return false;
  if (mine.some((fact) => ["decision", "needs_decision"].includes(fact.ev))) return false;
  const latest = mine.slice().reverse().find((f) => f.ev === "policy_abandon") ?? {};
  return [BT.A_SPEC_CASE_CONFLICT, BT.A_SPEC_PRESENT_CASE_INCOMPLETE, BT.A_INCOMPLETE_CASE].includes(String(latest.blocking_class ?? ""));
}

export function active_execution_terminal(mine: Record<string, any>[], opts: { facts?: Record<string, any>[] | null } = {}): Record<string, any> {
  let filtered = mine;
  if (opts.facts !== undefined && opts.facts !== null) {
    const { _fact_sha256 } = require("./terminal_credentials");
    const aid = mine.find((row) => row.aid)?.aid ?? "";
    const facts = effective_authority_facts(opts.facts, aid);
    const live = new Set(facts.map((row) => _fact_sha256(row)));
    filtered = mine.filter((row) => live.has(_fact_sha256(row)));
  }
  if (case_abandoned(filtered)) return {};
  for (let index = filtered.length - 1; index >= 0; index--) {
    const fact = filtered[index];
    const event = String(fact.ev ?? "");
    if (!_V12_EXECUTION_TERMINAL_EVENTS.has(event)) continue;
    if (is_authority_decision_terminal(fact)) {
      const { reentry_matches } = require("./authority_decision_reentry");
      if (!filtered.slice(index + 1).some((later) => reentry_matches(fact, later, opts.facts ?? filtered))) {
        return fact;
      }
      continue;
    }
    if (["blocked", "ist_core_defect", "authoring_failure"].includes(event)) {
      const raw_round = fact.round ?? 0;
      if (typeof raw_round !== "number" || raw_round < 0) return fact;
      const released = filtered.slice(index + 1).some((later) => later.ev === "conflict_chain_reentered" && typeof later.round === "number" && later.round > raw_round);
      if (!released) return fact;
    } else {
      return fact;
    }
  }
  return {};
}

function _positive_round(fact: Record<string, any>): number | null {
  const value = fact.round;
  if (typeof value !== "number" || Number.isNaN(value) || value <= 0) return null;
  return value;
}

function _reentrant_terminal_round(fact: Record<string, any>): number | null {
  if (!("round" in fact)) return 0;
  const value = fact.round;
  if (typeof value !== "number" || Number.isNaN(value) || value < 0) return null;
  return value;
}

function _reentrant_terminal_active(mine: Record<string, any>[], terminal_event: string, opts: { facts?: Record<string, any>[] | null } = {}): boolean {
  if (terminal_event === "blocked") {
    const { reentry_matches } = require("./authority_decision_reentry");
    if (mine.some((fact, index) => is_authority_decision_terminal(fact) && !mine.slice(index + 1).some((later) => reentry_matches(fact, later, opts.facts ?? mine)))) {
      return true;
    }
  }
  const last_terminal_index = mine.reduce((max, fact, index) => (fact.ev === terminal_event && !is_authority_decision_terminal(fact) ? index : max), -1);
  if (last_terminal_index < 0) return false;
  const terminal_round = _reentrant_terminal_round(mine[last_terminal_index]);
  if (terminal_round === null) return true;
  return !mine.slice(last_terminal_index + 1).some((fact) => {
    if (fact.ev !== "conflict_chain_reentered") return false;
    const reentry_round = _positive_round(fact);
    return reentry_round !== null && reentry_round > terminal_round;
  });
}

export function _user_sourced(att: Record<string, any>): boolean {
  return F.attribution_is_terminal(att);
}

function _is_suspended(mine: Record<string, any>[]): boolean {
  let last_susp = -1;
  let last_resume = -1;
  for (let i = 0; i < mine.length; i++) {
    if (mine[i].ev === "suspended") last_susp = i;
    else if (mine[i].ev === "resumed") last_resume = i;
  }
  return last_susp >= 0 && last_resume < last_susp;
}

export function active_execution_pause(mine: Record<string, any>[]): Record<string, any> {
  if (!_is_suspended(mine)) return {};
  const latest = mine.slice().reverse().find((fact) => fact.ev === "suspended") ?? {};
  return latest.suspension_kind === "execution_pause" ? latest : {};
}

export function execution_pause_resume_pending(mine: Record<string, any>[]): boolean {
  let pause: Record<string, any> = {};
  let pending = false;
  for (const fact of mine) {
    const event = fact.ev;
    if (event === "suspended") {
      pause = fact.suspension_kind === "execution_pause" ? fact : {};
      pending = false;
    } else if (event === "resumed") {
      pending = Object.keys(pause).length > 0;
    } else if (["verdict", "authored", "composed"].includes(event)) {
      pending = false;
    }
  }
  return pending;
}

export function _is_escalated(mine: Record<string, any>[]): boolean {
  let last_esc = -1;
  let last_release = -1;
  for (let i = 0; i < mine.length; i++) {
    if (mine[i].ev === "escalated") last_esc = i;
    else if (["authored", "de_escalated"].includes(mine[i].ev)) last_release = i;
  }
  return last_esc >= 0 && last_release < last_esc;
}

export function case_status(fs: Record<string, any>[], aid: string, current_artifact: string, current_volume: string, current_volume_artifact_sha256: string = ""): string {
  const EQ = require("./engine_quarantine");
  if (EQ.quarantined_aids(fs).has(aid)) return S_QUARANTINED;
  const mine = EQ.effective_case_facts(fs, aid);
  const fs_authority = effective_authority_facts(fs, aid);
  if (mine.some((f: any) => f.ev === "unsupported_feature")) return S_UNSUPPORTED_FEATURE;
  if (case_abandoned(mine)) return S_TERMINAL;
  if (mine.some((f: any) => _PERMANENT_TERMINAL_EVENTS.has(f.ev))) return S_TERMINAL;
  if ([..._REENTRANT_TERMINAL_EVENTS].some((terminal_event) => _reentrant_terminal_active(mine, terminal_event, { facts: fs_authority }))) return S_TERMINAL;
  if (_is_escalated(mine)) return S_ESCALATED;
  if (_is_suspended(mine)) return S_SUSPENDED;
  if (
    mine.some(
      (f: any) =>
        f.ev === "attribution" &&
        _user_sourced(f) &&
        ["env_blocked", "defect_candidate", "user_stop", "engineering_fault"].includes(f.disposition) &&
        (!F.scenario5_device_defect(f.layer, f.disposition) || F.scenario5_attribution_has_evidence(f, mine))
    )
  ) {
    return S_TERMINAL;
  }
  const { _decision_resolves_needs_decision } = require("./_shared");
  const current_needs: Record<string, any>[] = [];
  for (let index = 0; index < mine.length; index++) {
    const fact = mine[index];
    if (fact.ev !== "needs_decision") continue;
    if (mine.slice(index + 1).some((later: any) => later.ev === "conflict_chain_reentered" && later.invalidate_decisions === true)) continue;
    current_needs.push(fact);
  }
  const decisions = mine.filter((fact: any) => fact.ev === "decision");
  if (current_needs.some((need: any) => !decisions.some((decision: any) => _decision_resolves_needs_decision(need, decision, mine)))) {
    return S_AWAITING_USER;
  }
  if (unverified_authority_pending(fs_authority, { aid, current_volume_sha256: current_volume_artifact_sha256 })) return S_BROKEN;
  const last_auth_i = mine.reduce((max: any, f: any, i: any) => (f.ev === "authored" ? i : max), -1);
  const last_execution_reuse_i =
    last_auth_i >= 0
      ? mine.reduce(
          (max: any, fact: any, i: any) => (fact.ev === "execution_reentry_artifact_reused" && String(fact.artifact ?? "") === String(mine[last_auth_i]?.artifact ?? "") ? i : max),
          -1
        )
      : -1;
  if (last_auth_i >= 0 && mine.slice(Math.max(last_auth_i, last_execution_reuse_i) + 1).some((f: any) => f.ev === "emit_invalid")) {
    return S_PENDING;
  }
  const last_db_i = mine.reduce((max: any, f: any, i: any) => (f.ev === "delivery_blocked" ? i : max), -1);
  if (last_db_i >= 0) {
    const last_dpass_i = mine.reduce((max: any, f: any, i: any) => (f.ev === "verdict" && f.ctx === F.CTX_DELIVERY && f.result === "pass" ? i : max), -1);
    if (last_db_i > last_dpass_i && last_db_i > last_auth_i) return S_PENDING;
  }
  const last_volume_identity_failure = mine.reduce((max: any, f: any, i: any) => (is_volume_identity_failure(f) ? i : max), -1);
  const last_delivery_pass = mine.reduce((max: any, f: any, i: any) => (f.ev === "verdict" && f.ctx === F.CTX_DELIVERY && f.result === "pass" ? i : max), -1);
  if (last_volume_identity_failure > last_delivery_pass && last_volume_identity_failure > last_auth_i) return S_BROKEN;
  if (F.deliverable(mine, aid, current_artifact, current_volume, current_volume_artifact_sha256)) return S_DELIVERABLE;
  const last = current_artifact ? F.latest_verdict(mine, aid, null, current_artifact) : null;
  if (last) {
    if (last.result === "pass") return S_SUBSET_VERIFIED;
    if (["broken", "not_run"].includes(last.result)) {
      const sub = String(last.broken_subtype ?? "");
      if (sub === "errored") return S_BROKEN_ERRORED;
      if (sub === "blocked") return S_BROKEN_BLOCKED;
      if (sub === "aborted") return S_BROKEN_ABORTED;
      if (sub === "verdict_unrecognized") return S_BROKEN_VERDICT_UNRECOGNIZED;
      return S_BROKEN;
    }
    if (last.ctx === F.CTX_DELIVERY && F.contradictions(mine, aid, current_artifact) > 0) return S_CONTRADICTED;
    return S_FAILED;
  }
  if (F.pending_emit_aids(fs_authority).has(aid)) return S_COMPOSED;
  if (F.rounds_used(mine, aid) > 0) return S_AUTHORED;
  return S_PENDING;
}

export function current_delivery_volume_sha256(fs: Record<string, any>[]): string {
  const d_merges = fs.filter((f) => f.ev === "merged" && f.ctx !== F.CTX_SUBSET);
  return d_merges.length ? String(d_merges[d_merges.length - 1].artifact_sha256 ?? "") : "";
}

export function batch_view(fs: Record<string, any>[], manifest: Record<string, any>): Record<string, any> {
  const aids = (manifest.cases ?? []).map((c: any) => String(c.autoid));
  const d_merges = fs.filter((f) => f.ev === "merged" && f.ctx !== F.CTX_SUBSET);
  const current_volume = d_merges.length ? String(d_merges[d_merges.length - 1].volume ?? "") : "";
  const current_volume_sha = current_delivery_volume_sha256(fs);
  const out: Record<string, any> = { cases: {}, volume: current_volume, volume_artifact_sha256: current_volume_sha };
  for (const aid of aids) {
    const mine = fs.filter((f) => String(f.aid ?? "") === aid);
    const authored = mine.filter((f) => f.ev === "authored");
    const artifact = authored.length ? String(authored[authored.length - 1].artifact ?? "") : "";
    const st = case_status(fs, aid, artifact, current_volume, current_volume_sha);
    const authored_rounds = F.rounds_used(mine, aid);
    const dispatch_attempts = F.dispatch_rounds_used(mine, aid);
    out.cases[aid] = {
      status: st,
      artifact,
      rounds: authored_rounds,
      authored_rounds,
      dispatch_attempts,
      effective_budget: F.effective_rounds_used(mine, aid),
      contradictions: F.contradictions(mine, aid, artifact || null),
      recovered: F.recovered(mine, aid, artifact || null),
      frozen: F.frozen(mine, aid, artifact || null),
      transient_recur: F.transient_recur(mine, aid),
    };
  }
  out.counts = Counter(Object.values(out.cases).map((v: any) => v.status));
  return out;
}

export function is_settled(status: string): boolean {
  return [S_DELIVERABLE, S_ESCALATED, S_QUARANTINED, S_TERMINAL, S_SUSPENDED, S_UNSUPPORTED_FEATURE].includes(status);
}

export function all_settled(view: Record<string, any>): boolean {
  return Object.values(view.cases).every((v: any) => is_settled(v.status)) && Object.keys(view.cases).length > 0;
}
