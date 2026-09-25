# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/membership_assertion.py（sha256 99d6f353462cdde9）。不在这里手改。
from __future__ import annotations
import re
_IPV4_STRICT_RE = re.compile('^(?:(?:25[0-5]|2[0-4]\\d|[01]?\\d?\\d)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d?\\d)$')
_IPV6_LOOSE_RE = re.compile('^[0-9a-fA-F:]*:[0-9a-fA-F:]*$')

def _looks_like_ip(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    if _IPV4_STRICT_RE.match(s):
        return True
    return bool(_IPV6_LOOSE_RE.match(s))

def _escape_ip_for_regex(ip: str) -> str:
    return ip.strip().replace('.', '\\.')

def member_regex_for_ips(ips: list[str]) -> str:
    escaped = [_escape_ip_for_regex(ip) for ip in ips]
    return '\\b(?:' + '|'.join(escaped) + ')\\b'

def validate_membership(ips, present) -> str | None:
    if not isinstance(ips, list) or not ips:
        return f'Membership assertion ips (member IP set) must be a non-empty list, got {ips!r}'
    for i, ip in enumerate(ips):
        if not isinstance(ip, str) or not _looks_like_ip(ip):
            return f"ips[{i}]={ip!r} does not look like an IP address literal (should be a member IP from that pool's configuration, not a pool name/variable name)"
    if not isinstance(present, bool):
        return f'Membership assertion present (whether this observation should hit the member set) must be a bool, got {present!r}'
    return None

def expand_membership_step(step: dict) -> tuple[dict | None, str | None]:
    member = step.get('member') or {}
    ips = member.get('ips')
    present = member.get('present')
    err = validate_membership(ips, present)
    if err:
        return (None, err)
    g = member_regex_for_ips([str(ip) for ip in ips])
    mode = 'found' if present else 'not_found'
    desc = str(member.get('desc') or (f'输出命中成员集合{ips}（命中归属锚点）' if present else f'输出不落在成员集合{ips}（命中归属锚点）'))
    expanded = {'E': 'check_point', 'F': mode, 'G': g, 'desc': desc}
    if step.get('exempt') is True:
        expanded['exempt'] = True
        expanded['reason_code'] = str(step.get('reason_code') or '').strip()
    return (expanded, None)

def _is_member_step(step) -> bool:
    return isinstance(step, dict) and str(step.get('F', '')).strip() == 'member' and bool(step.get('member'))

def expand_membership_steps(steps: list) -> tuple[list | None, str | None]:
    new_steps: list = []
    for s in steps:
        if _is_member_step(s):
            expanded, err = expand_membership_step(s)
            if err:
                return (None, err)
            new_steps.append(expanded)
        else:
            new_steps.append(s)
    return (new_steps, None)

def attach_membership_derivation_receipts(provenance_steps, source_steps, expanded_steps):
    if not (isinstance(provenance_steps, list) and isinstance(source_steps, list) and isinstance(expanded_steps, list) and (len(provenance_steps) == len(source_steps) == len(expanded_steps))):
        return provenance_steps
    out = []
    for provenance, source_step, output_step in zip(provenance_steps, source_steps, expanded_steps):
        if not _is_member_step(source_step):
            out.append(provenance)
            continue
        if not isinstance(provenance, dict):
            raise ValueError('membership provenance entry is not an object')
        from cex_core.engine.case_compiler.provenance_ir import build_config_binding_derivation_receipt
        source = provenance.get('source')
        source = source if isinstance(source, dict) else {}
        receipt, error = build_config_binding_derivation_receipt(source_kind='membership_derived', recipe_id=str(source.get('ref') or ''), rule_id='membership.literal-set', source_input=source_step.get('member'), output_step=output_step)
        if receipt is None:
            raise ValueError(error)
        item = dict(provenance)
        item['source'] = {'kind': 'membership_derived', 'ref': receipt['recipe_id'], 'receipt': receipt}
        out.append(item)
    return out
