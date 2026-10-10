import crypto from "node:crypto";

export const AUTHORITY_DELIVERY_SCHEMA = 'ist.authority-delivery';
export const DELIVERY_SPEC_IDENTITY_FIELDS = ['spec_id', 'spec_sha256', 'version_anchor'];

function _sha256(value: any): string {
  return crypto.createHash('sha256').update(String(value)).digest('hex');
}

export function _canonicalize(value: any): any {
  if (Array.isArray(value)) {
    return value.map(_canonicalize);
  }
  if (typeof value === 'object' && value !== null) {
    const out: Record<string, any> = {};
    for (const k of Object.keys(value).sort()) {
      out[k] = _canonicalize(value[k]);
    }
    return out;
  }
  return value;
}

export function _canonical_json(value: any): string {
  return JSON.stringify(_canonicalize(value));
}

export function canonical_sha256(value: any): string {
  return _sha256(_canonical_json(value));
}

export function delivery_identity_volume_spec_sha256(volume_spec: Record<string, any>): string {
  const identity: Record<string, any> = {};
  for (const field of DELIVERY_SPEC_IDENTITY_FIELDS) {
    if (field in volume_spec) {
      identity[field] = volume_spec[field];
    }
  }
  return canonical_sha256(identity);
}

export function delivery_match_facts(facts: Iterable<Record<string, any>>, aid: string): any[] {
  const out: any[] = [];
  for (const f of facts) {
    if (String(f.aid ?? '') === aid && f.ev === 'delivery_match') {
      out.push(f);
    }
  }
  return out;
}

export function latest_delivery_match(facts: Iterable<Record<string, any>>, aid: string): any {
  const matches = delivery_match_facts(facts, aid);
  return matches.length ? matches[matches.length - 1] : null;
}

export function delivery_match_covers_terminal(facts: Iterable<Record<string, any>>, aid: string): boolean {
  const matches = delivery_match_facts(facts, aid);
  if (!matches.length) return false;
  const match = matches[matches.length - 1];
  const covered = match.covered_terminal;
  if (typeof covered === 'string' || covered === null) {
    return covered === null;
  }
  return Boolean(covered);
}

export function delivery_volume_id_from_facts(facts: Iterable<Record<string, any>>): string {
  const ordered = Array.from(facts);
  const volumes = new Set<string>();
  for (const f of ordered) {
    if (f.ev === 'volume_bound') volumes.add(String(f.volume_id ?? ''));
  }
  if (volumes.size !== 1) return '';
  return [...volumes][0];
}

export function is_volume_identity_failure(fact: Record<string, any>): boolean {
  return Boolean(fact.ev === 'volume_identity_failed');
}

export function is_authority_gap_disclosure(fact: Record<string, any>): boolean {
  return Boolean(fact.ev === 'authority_gap_disclosed');
}

export function effective_authority_facts(facts: Iterable<Record<string, any>>, aid: string): any[] {
  const out: any[] = [];
  for (const f of facts) {
    if (f.ev === 'volume_identity_failed') continue;
    if (String(f.aid ?? '') === aid) out.push(f);
  }
  return out;
}

export function is_authority_block_terminal(fact: Record<string, any> | null | undefined): boolean {
  return Boolean(fact && fact.ev === 'authority_blocked');
}

export function is_authority_unverified_block(fact: Record<string, any> | null | undefined): boolean {
  return Boolean(fact && fact.ev === 'authority_blocked' && String(fact.reason_code ?? '') === 'authority_chain_unverified');
}

export function is_authority_decision_terminal(fact: Record<string, any> | null | undefined): boolean {
  return Boolean(fact && fact.ev === 'authority_blocked');
}

export function unverified_authority_pending(facts: Iterable<Record<string, any>>, opts: { aid?: string; current_volume_sha256?: string } = {}): boolean {
  const aid = opts.aid ?? '';
  const rows = effective_authority_facts(facts, aid);
  const blockers = rows.filter(is_authority_block_terminal);
  if (!blockers.length) return false;
  const sha = String(opts.current_volume_sha256 ?? '');
  if (!sha) return true;
  const bound = rows.filter((f) => f.ev === 'volume_bound' && String(f.volume_sha256 ?? '') === sha);
  return bound.length < blockers.length;
}
