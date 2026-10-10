import { accepts_schema } from "../common/schema_identity";

export const SCHEMA = "ist.ide.pass-audit";
export const COUNT_FIELDS = ["total_assertions", "flipped_assertions", "exempt_assertions", "pending_assertions"] as const;

function _sha(value: any): string {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value) ? value : "";
}

function _caseSha(aid: string, artifact: any): string {
  if (typeof artifact !== "string") {
    return "";
  }
  const idx = String(artifact || "").indexOf(":");
  const owner = idx < 0 ? String(artifact || "") : String(artifact || "").slice(0, idx);
  const digest = idx < 0 ? "" : String(artifact || "").slice(idx + 1);
  return idx >= 0 && owner === aid ? _sha(digest) : "";
}

export function latest_terminals(facts: Iterable<Record<string, any>>): Record<string, Record<string, any>> {
  const out: Record<string, Record<string, any>> = {};
  for (const fact of facts) {
    if (fact.ev === "case_terminal_outcome" && fact.aid) {
      out[String(fact.aid)] = fact;
    }
  }
  return out;
}

export function group_audits(facts: Iterable<Record<string, any>>): Record<string, Array<Record<string, any>>> {
  const groups: Record<string, Array<Record<string, any>>> = {};
  for (const fact of facts) {
    if (fact.ev === "pass_audit" && fact.aid) {
      (groups[String(fact.aid)] = groups[String(fact.aid)] || []).push(fact);
    }
  }
  return groups;
}

export function terminal_artifacts(terminal: Record<string, any>): [string, string] {
  if (terminal.outcome !== "delivered" || terminal.credential_valid === false) {
    return ["", ""];
  }
  const refs = terminal.credential_refs;
  if (typeof refs !== "object" || refs === null || Array.isArray(refs)) {
    return ["", ""];
  }
  return [_sha(refs.volume_artifact_sha256), _caseSha(String(terminal.aid || ""), refs.artifact)];
}

export function metric_delivery_artifacts(
  facts: Array<Record<string, any>>,
  final_sha: string | null
): Record<string, [string, string]> {
  const final = _sha(final_sha);
  if (!final) {
    return {};
  }
  const verdicts: Record<string, Record<string, any>> = {};
  for (const fact of facts) {
    if (fact.ev === "verdict" && fact.ctx === "delivery" && fact.volume_artifact_sha256 === final) {
      verdicts[String(fact.aid)] = fact;
    }
  }
  const identities: Record<string, [string, string]> = {};
  for (const aid of Object.keys(verdicts)) {
    const fact = verdicts[aid];
    identities[aid] = [final, fact.result === "pass" ? _caseSha(aid, fact.artifact) : ""];
  }
  const terminals = latest_terminals(facts);
  for (const aid of Object.keys(terminals)) {
    const [volume, caseSha] = terminal_artifacts(terminals[aid]);
    identities[aid] = volume === final ? [volume, caseSha] : ["", ""];
  }
  return identities;
}

export class PassAuditView {
  audit: Record<string, any> | null;
  status: string;
  reason: string;
  counts: [number, number, number, number] | null;

  constructor(audit: Record<string, any> | null, status: string, reason: string, counts: [number, number, number, number] | null = null) {
    this.audit = audit;
    this.status = status;
    this.reason = reason;
    this.counts = counts;
    Object.freeze(this);
  }

  get trusted(): boolean {
    return this.status === "complete" || this.status === "incomplete" || this.status === "unavailable";
  }

  get clean(): boolean {
    return this.status === "complete" && (this.audit || {}).outcome === "clean";
  }
}

export function select_pass_audit(
  facts: Array<Record<string, any>>,
  aid: string,
  final_sha: string,
  case_sha: string
): PassAuditView {
  const candidates = facts.filter((fact) => fact.ev === "pass_audit" && String(fact.aid) === aid);
  if (!candidates.length) {
    return new PassAuditView(null, "missing", "audit_missing");
  }
  const matching = candidates.filter((fact) => fact.artifact_sha256 === final_sha);
  const audit = (matching.length ? matching : candidates)[(matching.length ? matching : candidates).length - 1];
  if (!_sha(final_sha) || !_sha(case_sha)) {
    return new PassAuditView(audit, "unverified", "delivery_identity_missing");
  }
  if (!matching.length) {
    return new PassAuditView(audit, "unverified", "audit_artifact_mismatch");
  }
  if (audit.case_artifact_sha256 !== case_sha) {
    return new PassAuditView(audit, "unverified", "case_artifact_mismatch");
  }
  if (
    !(
      accepts_schema(audit.schema, "ist.ide.pass-audit") &&
      audit.artifact === "case.xlsx" &&
      audit.audit_basis === "mutation_flip" &&
      typeof audit.audit_revision === "string" &&
      audit.audit_revision.trim()
    )
  ) {
    return new PassAuditView(audit, "unverified", "audit_schema_invalid");
  }
  const status = audit.status;
  const outcome = audit.outcome;
  if (typeof status !== "string" || typeof outcome !== "string") {
    return new PassAuditView(audit, "unverified", "audit_state_invalid");
  }
  if (
    (status === "complete" && outcome !== "clean" && outcome !== "false_pass") ||
    ((status === "incomplete" || status === "unavailable") && outcome !== "unknown") ||
    (status !== "complete" && status !== "incomplete" && status !== "unavailable")
  ) {
    return new PassAuditView(audit, "unverified", "audit_state_invalid");
  }
  if (status === "unavailable") {
    return new PassAuditView(audit, status, String(audit.reason_code || "audit_unavailable"));
  }
  const counts = COUNT_FIELDS.map((key) => audit[key]) as [number, number, number, number];
  if (
    !(
      _sha(audit.mutation_receipt_sha256) &&
      counts.every((value) => typeof value === "number" && Number.isInteger(value) && value >= 0) &&
      counts[1] + counts[2] + counts[3] === counts[0] &&
      counts[0] > 0 &&
      (outcome !== "clean" || counts[1] === counts[0])
    )
  ) {
    return new PassAuditView(audit, "unverified", "audit_counts_invalid");
  }
  return new PassAuditView(audit, status, String(audit.reason_code || ""), counts);
}
