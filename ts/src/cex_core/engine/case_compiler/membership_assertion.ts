const _IPV4_STRICT_RE = /^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)$/;
const _IPV6_LOOSE_RE = /^[0-9a-fA-F:]*:[0-9a-fA-F:]*$/;

function _looksLikeIp(s: string): boolean {
  s = s.trim();
  if (!s) {
    return false;
  }
  if (_IPV4_STRICT_RE.test(s)) {
    return true;
  }
  return _IPV6_LOOSE_RE.test(s);
}

function _escapeIpForRegex(ip: string): string {
  return ip.trim().replace(/\./g, "\\.");
}

export function member_regex_for_ips(ips: string[]): string {
  const escaped = ips.map(_escapeIpForRegex);
  return "\\b(?:" + escaped.join("|") + ")\\b";
}

export function validate_membership(ips: any, present: any): string | null {
  if (!Array.isArray(ips) || !ips.length) {
    return `Membership assertion ips (member IP set) must be a non-empty list, got ${JSON.stringify(ips)}`;
  }
  for (let i = 0; i < ips.length; i++) {
    const ip = ips[i];
    if (typeof ip !== "string" || !_looksLikeIp(ip)) {
      return `ips[${i}]=${JSON.stringify(ip)} does not look like an IP address literal (should be a member IP from that pool's configuration, not a pool name/variable name)`;
    }
  }
  if (typeof present !== "boolean") {
    return `Membership assertion present (whether this observation should hit the member set) must be a bool, got ${JSON.stringify(present)}`;
  }
  return null;
}

export function expand_membership_step(step: Record<string, any>): [Record<string, any> | null, string | null] {
  const member = step.member || {};
  const ips = member.ips;
  const present = member.present;
  const err = validate_membership(ips, present);
  if (err) {
    return [null, err];
  }
  const g = member_regex_for_ips(ips.map((ip: any) => String(ip)));
  const mode = present ? "found" : "not_found";
  const desc = String(
    member.desc ||
      (present
        ? `输出命中成员集合${JSON.stringify(ips)}（命中归属锚点）`
        : `输出不落在成员集合${JSON.stringify(ips)}（命中归属锚点）`)
  );
  const expanded: Record<string, any> = { E: "check_point", F: mode, G: g, desc };
  if (step.exempt === true) {
    expanded.exempt = true;
    expanded.reason_code = String(step.reason_code || "").trim();
  }
  return [expanded, null];
}

function _isMemberStep(step: any): boolean {
  return (
    typeof step === "object" && step !== null && !Array.isArray(step) &&
    String(step.F || "").trim() === "member" && Boolean(step.member)
  );
}

export function expand_membership_steps(steps: any[]): [any[] | null, string | null] {
  const newSteps: any[] = [];
  for (const s of steps) {
    if (_isMemberStep(s)) {
      const [expanded, err] = expand_membership_step(s);
      if (err) {
        return [null, err];
      }
      newSteps.push(expanded);
    } else {
      newSteps.push(s);
    }
  }
  return [newSteps, null];
}

export function attach_membership_derivation_receipts(
  provenance_steps: any,
  source_steps: any,
  expanded_steps: any
): any {
  if (
    !(
      Array.isArray(provenance_steps) &&
      Array.isArray(source_steps) &&
      Array.isArray(expanded_steps) &&
      provenance_steps.length === source_steps.length &&
      source_steps.length === expanded_steps.length
    )
  ) {
    return provenance_steps;
  }
  const out: any[] = [];
  for (let i = 0; i < provenance_steps.length; i++) {
    const provenance = provenance_steps[i];
    const sourceStep = source_steps[i];
    const outputStep = expanded_steps[i];
    if (!_isMemberStep(sourceStep)) {
      out.push(provenance);
      continue;
    }
    if (typeof provenance !== "object" || provenance === null || Array.isArray(provenance)) {
      throw new Error("membership provenance entry is not an object");
    }
    const { build_config_binding_derivation_receipt } = require("./provenance_ir");
    const source = typeof provenance.source === "object" && provenance.source !== null ? provenance.source : {};
    const [receipt, error] = build_config_binding_derivation_receipt({
      source_kind: "membership_derived",
      recipe_id: String(source.ref || ""),
      rule_id: "membership.literal-set",
      source_input: sourceStep.member,
      output_step: outputStep,
    });
    if (receipt === null) {
      throw new Error(error);
    }
    const item = { ...provenance };
    item.source = { kind: "membership_derived", ref: receipt.recipe_id, receipt };
    out.push(item);
  }
  return out;
}
