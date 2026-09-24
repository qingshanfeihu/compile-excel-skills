# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/lang_query_tool.py（sha256 d86fce975b5deb49）。不在这里手改。
from __future__ import annotations
import re
from pathlib import Path
from typing import Callable, Literal, TypedDict
from langchain_core.tools import tool
from cex_core.engine.case_compiler.apv_lang import QueryUnavailable, capability_signature, capability_usage_of, confirmation_prompt_of, dispatch_domain_orientation, dispatch_kind_cross_check, dispatch_kind_of, host_observation, language_document_catalog, apv_full_fs, nearest_candidates, usage_index_corpus_meta, usage_index_empty_bucket_notes
from cex_core.engine.case_compiler.excel_contract import ExcelContractError, enabled_fs_by_e, load_excel_contract
_KINDS = ('contract', 'signature', 'dispatch', 'usage', 'nearest', 'prompt_pattern', 'docs', 'param', 'complete', 'heads', 'host')
COMMAND_HEADS_QUERY_SCHEMA = 'ist.command-heads-query'

class CommandHeadsQueryResult(TypedDict):
    """`kind=heads` 的 JSON-native 内部结果；只在工具文本边界渲染。"""
    schema: Literal['ist.command-heads-query']
    status: Literal['complete', 'worker_session_unavailable', 'capability_build_missing', 'command_tree_unavailable', 'capability_identity_mismatch', 'receipt_unavailable', 'result_too_large']
    module_prefix: str
    device_build: str
    capability_generation_id: str
    capability_manifest_sha256: str
    projection_version: str
    count: int
    heads: list[str]
    receipt_id: str
    result_sha256: str
_COMPLETE_SHOWN_K = 5
_MAX_HEADS_RESULT_BYTES = 256 * 1024
_ASSERTION_IDENTITY_NOTE = "assertion_identity: a check_point row redeems exactly one claim on this case's frozen contract card. When the card carries a claim with typed_assertion_status `pending author_claim`, the assertion you write must carry that claim's minted expectation_id and semantic_key verbatim — you never mint them yourself, and emit requires every contract expectation_id to be covered by at least one check_point row. Rows sharing one id must differ in observation, operator, or expected value; two assertions doing the same thing verify one thing. A composite combinator that fans out into N rows must also reproduce its complete generator ordinal set.\n  carrier position: the single assertion — an OBSERVE_ASSERT.asserts[] entry, or the one synthesized assertion of CAPTURE_COMPARE / EXPECT_FROM / OBSERVE_DIST / OBSERVE_MEMBER (there block-level IS assertion-level), or a STEP whose E is check_point. Anywhere else (block level of OBSERVE_ASSERT, a non-check_point STEP, a nested sub-container) the expansion refuses, because putting it there would be silently dropped.\n  accepted compiled forms for a pending claim: either source.kind=intent with source.ref equal to the expectation_id and a non-empty G (the expectation is a verbatim transcription of what the author declared), or one of the four relational/composite combinators above, whose observation_ref must close onto an explicit earlier observation step in the same case. Any other source (precedent / footprint / device_runtime …) on a pending claim is refused — that shape is rewriting an expectation from an observation."

def _render_contract_action(action: dict, *, e_value: str, contract_sha256: str, prefix: str='', include_contract_sha: bool=True) -> list[str]:
    source = action['source']
    lines = [f"{prefix}action: {action['name']}", f"{prefix}canonical: {action['canonical']}", f"{prefix}equivalent_originals: {action['equivalent_originals']}", f"{prefix}status: {action['status']}", f"{prefix}reason: {action['reason']}", f"{prefix}status_authority: {action['status_authority']}", f"{prefix}dispatcher: {action['dispatcher']}", f"{prefix}python_symbol: {action['python_symbol']}", f"{prefix}signature: {action['signature']['text']}", f"{prefix}G: {action['g_syntax']}", f"{prefix}H: {action['h_semantics']}", f"{prefix}I: {action['i_semantics']}", f"{prefix}payload_schema: {action['payload_schema']}", f"{prefix}python_call_chain: runner -> getattr({e_value}, execute) -> {action['dispatcher']} registry[{action['normalized']!r}] -> {action['python_symbol']}", f"{prefix}source: {source['path']}:{source['line']}", f"{prefix}minimum_runtime: {action['minimum_runtime']}"]
    if include_contract_sha:
        lines.append(f'{prefix}contract_sha256: {contract_sha256}')
    return lines

def _execute_enabled_es(contract) -> list[str]:
    return sorted((entry['e'] for entry in contract['entries'] if entry['f'] == 'execute' and entry['status'] == 'enabled'))

def _render_execute_surface_summary(contract, actions: list, *, e_value: str) -> list[str]:
    enabled = [action for action in actions if action['status'] == 'enabled']
    seats = _execute_enabled_es(contract)
    lines = [f'execute_actions ({len(actions)}): {len(enabled)} enabled, {len(actions) - len(enabled)} not enabled']
    if not enabled:
        lines.append('enabled_actions (0): no action on this dispatcher is authorable today — the full list below still shows every action with its status, reason and authority, so you can tell "not certified yet" from "does not exist"')
        return lines
    combinations = 0
    here = 0
    lines.append(f'enabled_actions ({len(enabled)}):')
    for action in enabled:
        allowed = sorted(set(action['allowed_es']) & set(seats))
        combinations += len(allowed)
        if e_value in allowed:
            here += 1
        lines.append(f"  - {action['name']} — authorable on {(', '.join(allowed) if allowed else '<no E seat with execute enabled>')} ({action['dispatcher']} registry -> {action['python_symbol']})")
    lines.append(f"authorable_on_{e_value}: {here} of these {len(enabled)} enabled action(s) can be written on {e_value} itself, whose execute row is {('enabled' if e_value in seats else 'not enabled')}.")
    lines.append(f"authorable_execute_surface: {combinations} (action, E) combination(s) — a contract-wide count over every E, not a count for {e_value}. An action is authorable only where its own status is enabled AND that E's execute row is enabled; E values whose execute row is enabled: {(', '.join(seats) if seats else '<none>')}. Everything else below is listed for diagnosis, not for authoring.")
    return lines

def _render_contract_index() -> str:
    header = '=== lang_query(kind=contract) ==='
    try:
        contract = load_excel_contract()
    except ExcelContractError as exc:
        return f'error: contract query unavailable — {exc}'
    enabled_map = enabled_fs_by_e(contract)
    counts: dict[str, dict[str, int]] = {}
    reasons: dict[str, dict[str, int]] = {}
    for entry in contract['entries']:
        bucket = counts.setdefault(entry['e'], {})
        bucket[entry['status']] = bucket.get(entry['status'], 0) + 1
        if entry['status'] == 'disabled':
            tally = reasons.setdefault(entry['e'], {})
            tally[entry['reason']] = tally.get(entry['reason'], 0) + 1
    objects = {item['e']: item for item in contract['objects']}
    usable = sorted((e for e, fs in enabled_map.items() if fs))
    unusable = sorted((e for e, fs in enabled_map.items() if not fs))
    lines = [header, f"runtime: {contract['runtime']['minimum_version']}", f"contract_sha256: {contract['contract_sha256']}", f'E values ({len(enabled_map)}): {len(usable)} with an enabled function surface, {len(unusable)} with none', f'', f'with an enabled surface ({len(usable)}):']
    for e_value in usable:
        names = sorted(enabled_map[e_value])
        lines.append(f"  - {e_value} ({len(names)} enabled F): {', '.join(names)}")
    lines.append('')
    lines.append(f'with no enabled surface ({len(unusable)}) — stated positively so you do not have to discover them by being rejected at emit:')
    for e_value in unusable:
        bucket = counts.get(e_value, {})
        shape = ', '.join((f'{count} {status}' for status, count in sorted(bucket.items()))) or 'no F rows'
        obj = objects.get(e_value, {})
        lines.append(f"  - {e_value} ({shape}; object_status={obj.get('status', '<unknown>')})")
        tally = sorted(reasons.get(e_value, {}).items(), key=lambda pair: (-pair[1], pair[0]))
        for reason, count in tally[:3]:
            lines.append(f'      disabled reason ({count} F): {reason}')
        if len(tally) > 3:
            lines.append(f'      (+{len(tally) - 3} further distinct reason(s); query this E directly for the full surface)')
    lines.append('')
    lines.append("next: query kind=contract with domain=<one E> for that object's full enabled/disabled/internal F surface, then domain+name=<one F> for its signature, G/H/I semantics, dispatch and provenance.")
    return '\n'.join(lines)

def _render_contract(e_value: str, f_value: str='') -> str:
    header = f'=== lang_query(kind=contract, domain={e_value!r}, name={f_value!r}) ==='
    try:
        contract = load_excel_contract()
    except ExcelContractError as exc:
        return f'error: contract query unavailable — {exc}'
    entries = [entry for entry in contract['entries'] if entry['e'] == e_value]
    if not entries:
        known = ', '.join((item['e'] for item in contract['objects']))
        f_rows = sorted(((str(entry['e']), str(entry['status'])) for entry in contract['entries'] if entry['f'] == e_value))
        if f_rows:
            orientation = '\n'.join((f'  - E={owner} (status={status})' for owner, status in f_rows))
            return f'{header}\nnot found — unknown E value {e_value!r}; known E values: {known}\norientation: {e_value!r} is an exact F value, not an E value. It occurs under:\n{orientation}\nnext: query one exact pair with domain=<the E shown above>, name=<this F>. This is contract navigation only; it does not decide whether the current case has enough evidence.'
        return f'{header}\nnot found — unknown E value {e_value!r}; known E values: {known}'
    if f_value:
        entry = next((entry for entry in entries if entry['f'] == f_value), None)
        if entry is None:
            normalized = re.sub('\\s+', '', f_value.lower())
            action_matches = [action for action in contract['execute_actions'] if e_value in action['allowed_es'] and action['normalized'] == normalized]
            if len(action_matches) == 1:
                return '\n'.join([header, *_render_contract_action(action_matches[0], e_value=e_value, contract_sha256=contract['contract_sha256'])])
            return f'{header}\nnot found — {e_value!r} has no F or exact execute action named {f_value!r}; query the same E without name to list its function surface'
        signature = entry['signature']
        source = entry['source']
        lines = [header, f"status: {entry['status']}", f"reason: {entry['reason']}", f"status_authority: {entry['status_authority']}", f"python_symbol: {entry['python_symbol']}", f"signature: {signature['text']}", f"G: {entry['g_syntax']}", f"H: {entry['h_semantics']}", f"I: {entry['i_semantics']}", f"dispatch: {entry['dispatch']}", f"source: {source['path']}:{source['line']}", f"minimum_runtime: {entry['minimum_runtime']}", f"contract_sha256: {contract['contract_sha256']}"]
        if entry['dispatch'] == 'execute_registry':
            actions = [action for action in contract['execute_actions'] if e_value in action['allowed_es']]
            lines.extend(_render_execute_surface_summary(contract, actions, e_value=e_value))
            for action in actions:
                lines.extend(_render_contract_action(action, e_value=e_value, contract_sha256=contract['contract_sha256'], prefix='  ', include_contract_sha=False))
                lines.append('  ---')
            lines.append('next: query name=<exact action name> for one action; disabled actions remain visible with their reason and authority. The contract_sha256 printed once above covers every action listed here.')
        if e_value == 'check_point':
            lines.append('')
            lines.append(_ASSERTION_IDENTITY_NOTE)
        return '\n'.join(lines)
    object_info = next((item for item in contract['objects'] if item['e'] == e_value))
    lines = [header, f"object_status: {object_info['status']}", f"object_reason: {object_info['reason']}", f"object_status_authority: {object_info['status_authority']}", f"runtime: {contract['runtime']['minimum_version']}", f"contract_sha256: {contract['contract_sha256']}"]
    for status in ('enabled', 'disabled', 'internal'):
        names = sorted((entry['f'] for entry in entries if entry['status'] == status))
        lines.append(f"{status} ({len(names)}): {(', '.join(names) if names else '<none>')}")
    lines.append('next: query this E with name=<one F> for signature, G/H/I semantics and provenance')
    if e_value == 'check_point':
        lines.append('')
        lines.append(_ASSERTION_IDENTITY_NOTE)
    return '\n'.join(lines)

def _render_signature(name: str) -> str:
    try:
        sig = capability_signature(name)
    except QueryUnavailable as exc:
        return f'error: signature query unavailable — {exc}'
    header = f'=== lang_query(kind=signature, name={name!r}) ==='
    if sig is None:
        return f"{header}\nnot found — {name!r} is not a member of any apv_full mixin family (ssl_comm/seg_comm/ha_comm/preparation). This covers method-style F values only, not execute action names or cmd_config/cmds_config primitives — if {name!r} is an execute action name, it is not in this atlas at all: query lang_query(kind='contract', domain=<the E value you are writing>, name='execute') for that E's whole execute action surface (each action's status, payload schema and G/H/I grammar, enabled ones summarised first), or lang_query(kind='contract', domain=<E>, name=<exact action name>) for one action."
    return f"{header}\nrequired: {sig['required']}\noptional: {sig['optional']}\nsource: {sig['source']} (family: {sig['_family']})"

def _render_dispatch_point(name: str) -> str:
    header = f'=== lang_query(kind=dispatch, name={name!r}) ==='
    try:
        kind = dispatch_kind_of(name)
    except QueryUnavailable as exc:
        return f'error: dispatch query unavailable — {exc}'
    if kind is None:
        return f"{header}\nnot found — {name!r} is not in the APV_0/1/2 apv_full dispatch surface (ssl_comm/seg_comm/ha_comm/preparation mixins, execute, or the cmd/cmds primitives). This kind only covers those E's; test_env/check_point/host-slot F names have no dispatch-kind ambiguity to query."
    lines = [header, f'dispatch_kind: {kind}']
    check = dispatch_kind_cross_check(name)
    if check['stale']:
        lines.append(f"note: the curated atlas snapshot disagrees (atlas says {check['atlas']!r}, live reflection says {kind!r}) — this means the atlas needs regenerating (scripts/gen_capability_atlas.py), it does NOT mean you filled anything wrong. The value above (live) is authoritative regardless.")
    return '\n'.join(lines)

def _render_dispatch_domain(domain: str) -> str:
    header = f'=== lang_query(kind=dispatch, domain={domain!r}) ==='
    try:
        o = dispatch_domain_orientation(domain)
    except ValueError as exc:
        return f'error: {exc}'
    except QueryUnavailable as exc:
        return f'error: dispatch query unavailable — {exc}'
    lines = [header, f"dispatch_kind: {o['dispatch_kind']} (constant across this domain's {o['n']} methods, stated once)", f"names ({o['n']}): {', '.join(o['names'])}"]
    if o['disabled']:
        lines.append(f"\n<disabled n={len(o['disabled'])}>")
        for n, reason in o['disabled'].items():
            lines.append(f'  - {n}: {reason}')
        lines.append('</disabled>')
    lines.append(f"\ndisambiguation: {o['disambiguation']}")
    lines.append("\nsignatures_omitted: true — this domain listing does not include per-method parameter signatures (they don't discriminate between similarly-named methods here any better than the names alone do). next: before writing the F column, query lang_query(kind='signature', name=<the method you picked>) to get its required/optional parameters — this step is not optional, guessing the parameter shape from the name is how silent-wrong F rows happen.")
    return '\n'.join(lines)

def _host_slot_pointer(name: str) -> str:
    try:
        obs = host_observation(name)
    except QueryUnavailable:
        return ''
    if not obs['is_known_host']:
        return ''
    return f"\nnote: {name!r} is also a host slot this build declares. The corpus queried above holds only our own device-verified cases; what the vendor smoke-test suite ran on that machine is a separate record — query lang_query(kind='host', name={name!r}) for it."

def _render_usage(name: str) -> str:
    header = f'=== lang_query(kind=usage, name={name!r}) ==='
    try:
        u = capability_usage_of(name)
    except QueryUnavailable as exc:
        return f'error: usage query unavailable — {exc}'
    if u is None:
        corpus_count = int(usage_index_corpus_meta().get('corpus_file_count') or 0)
        corpus_label = f'the current {corpus_count}-case device-verified mirror corpus' if corpus_count else 'the current device-verified mirror corpus'
        lines = [header, f"""0 hits across {corpus_label} — this does NOT mean the framework doesn't support {name!r}, only that no case in the corpus has used it yet. Treat this as "unproven by precedent", not "unsupported"."""]
        for reason in usage_index_empty_bucket_notes().values():
            lines.append(f'\n(corpus-wide note: {reason})')
        pointer = _host_slot_pointer(name)
        if pointer:
            lines.append(pointer)
        return '\n'.join(lines)
    lines = [header, f"{u['count']} real occurrence(s) in the corpus (bucket: {u['bucket']}), showing {len(u['samples'])} representative sample(s) from {int(u.get('corpus_file_count') or 0)} device-verified case(s):"]
    for s in u['samples']:
        lines.append(f'''\n<usage autoid="{s.get('autoid', '')}" desc="{s.get('desc', '')}">''')
        lines.append(str(s.get('g', '')))
        lines.append('</usage>')
    if u['count'] > len(u['samples']):
        lines.append(f"\n({u['count'] - len(u['samples'])} more not shown)")
    pointer = _host_slot_pointer(name)
    if pointer:
        lines.append(pointer)
    return '\n'.join(lines)
_HOST_TOKENS_SHOWN = 40
_HOST_COMMANDS_SHOWN = 15
_HOST_COMMAND_RENDER_MAX = 300
_HOST_READING_NOTE = 'reading: every line above is a record of something that was run in the past, on a bed addressed by this host slot. None of it states what that machine offers now — a service that answered then may be gone, and something never attempted may still work. Zero rows, for a host or for a first token, means no precedent was recorded, not that the action is unsupported. First tokens are taken mechanically as the first whitespace-separated word of the command cell; this tool does not classify them into services, ports or roles, and hands you no table that does.'

def _host_first_token_lines(tokens: list, label: str) -> list[str]:
    shown = tokens[:_HOST_TOKENS_SHOWN]
    lines = [f'{label} ({len(tokens)} distinct first token(s), token — rows / distinct case files):']
    for item in shown:
        token = str(item.get('token') or '')
        lines.append(f"  {token or '<empty command cell>'} — {item.get('rows')} / {item.get('distinct_files')}")
    if len(tokens) > len(shown):
        lines.append(f"  ({len(tokens) - len(shown)} further first token(s) not printed here; this list is truncated, so a token's absence from these lines is not evidence it was never run)")
    return lines

def _host_command_block(entry: dict) -> list[str]:
    command = str(entry.get('command') or '')
    stored_cut = int(entry.get('command_truncated_chars') or 0)
    render_cut = max(0, len(command) - _HOST_COMMAND_RENDER_MAX)
    body = command[:_HOST_COMMAND_RENDER_MAX]
    cut = stored_cut + render_cut
    desc = str(entry.get('first_seen_desc') or '').replace('\n', ' ')[:120]
    lines = [f'''\n<observed first_token="{entry.get('first_token', '')}" f="{entry.get('f', '')}" rows="{entry.get('rows')}" distinct_files="{entry.get('distinct_files')}" file="{entry.get('first_seen_file', '')}" autoid="{entry.get('first_seen_autoid', '')}" desc="{desc}">''', body]
    if cut:
        lines.append(f'[{cut} further character(s) of this command cut from the text above]')
    lines.append('</observed>')
    return lines

def _render_host(name: str, query: str='') -> str:
    header = f'=== lang_query(kind=host, name={name!r}, query={query!r}) ==='
    try:
        obs = host_observation(name)
    except QueryUnavailable as exc:
        return f'{header}\nerror: the usage projection could not be read — {exc}. That is a missing projection on our side, NOT a statement about this machine.'
    corpus = obs['corpus']
    key_space = obs['host_key_space']
    skipped = list(corpus.get('vendor_unreadable_files') or [])
    lines = [header, f"projection: capability_usage_index.json — vendor corpus {corpus.get('vendor_scanned_file_count')} of {corpus.get('vendor_corpus_file_count')} case file(s) scanned ({len(skipped)} skipped, named one by one in the projection's _meta.vendor_unreadable_files); authored corpus {corpus.get('corpus_file_count')} device-verified case(s).", f"host slots this build declares ({len(key_space)}, parsed from mirror {', '.join(corpus.get('host_key_space_sources') or [])}): {(', '.join(key_space) if key_space else '<none recorded>')}"]
    if not obs['is_known_host']:
        lines.append(f"\n{name!r} is not one of those host slots, so nothing was looked up for it. Two readings stay open and this tool picks neither: the name may be misspelled, or this bed may address that machine some other way. Pick a slot from the list above, or query kind='docs' for the bed's topology assets.")
        return '\n'.join(lines)
    vendor = obs['vendor']
    q = (query or '').strip().casefold()
    lines.append('')
    lines.append(f'--- vendor corpus: what the vendor smoke-test suite ran on {name!r} ---')
    if not vendor:
        lines.append(f'0 row(s) recorded — no case in that corpus wrote a step against this host slot. Treat this as "unproven by precedent", not "unsupported": it does NOT mean {name!r} cannot run commands, only that the vendor corpus carries no example of anyone doing so.')
    else:
        redacted = int(vendor.get('redacted_rows') or 0)
        lines.append(f"{vendor.get('rows')} step row(s) across {vendor.get('distinct_files')} case file(s); {vendor.get('distinct_commands')} distinct command text(s)" + (f'; {redacted} row(s) redacted because their text carried a plaintext credential literal from the framework mirror (the rows are still counted, only their text is withheld)' if redacted else '') + '.')
        lines.extend(_host_first_token_lines(list(vendor.get('first_tokens') or []), 'first tokens'))
        commands = list(vendor.get('commands') or [])
        omitted = int(vendor.get('commands_omitted') or 0)
        if q:
            matched = [entry for entry in commands if q in str(entry.get('first_token') or '').casefold() or q in str(entry.get('command') or '').casefold()]
            shown = matched[:_HOST_COMMANDS_SHOWN]
            lines.append(f"\nverbatim commands whose first token or text contains {query!r}: {len(matched)} of the {len(commands)} command text(s) this projection records for {name!r}, showing {len(shown)}. The search covers only those {len(commands)} recorded texts, not all {vendor.get('distinct_commands')} distinct ones ({omitted} were left out by the projection's per-token storage cap) — so zero matches here is not proof the string never appeared on this machine.")
            for entry in shown:
                lines.extend(_host_command_block(entry))
            if len(matched) > len(shown):
                lines.append(f'\n({len(matched) - len(shown)} further match(es) not printed)')
        else:
            by_token: dict[str, dict] = {}
            for entry in commands:
                by_token.setdefault(str(entry.get('first_token') or ''), entry)
            reps = list(by_token.values())[:_HOST_COMMANDS_SHOWN]
            lines.append(f"\nverbatim commands — the highest-count example per first token, {len(reps)} of {len(by_token)} token(s) with a recorded text. The projection stores {len(commands)} of this host's {vendor.get('distinct_commands')} distinct command texts ({omitted} left out by the per-token storage cap); pass query=<substring> to search the recorded ones.")
            for entry in reps:
                lines.extend(_host_command_block(entry))
    authored = obs['authored']
    lines.append('')
    lines.append(f'--- authored corpus: what our own device-verified cases did on {name!r} (counts only) ---')
    lines.append("No command text is carried for this column, by construction: these cases were written by this engine and have not been through the vendor suite's long-running use of this bed, so they are not precedent for what the machine tolerates. Counting them beside the vendor rows would blur who verified what.")
    if not authored:
        lines.append(f'0 row(s) — none of our device-verified cases addressed {name!r}. Again: no precedent, not a limit.')
    else:
        lines.append(f"{authored.get('rows')} step row(s) across {authored.get('distinct_files')} case file(s).")
        lines.extend(_host_first_token_lines(list(authored.get('first_tokens') or []), 'first tokens'))
    lines.append('')
    lines.append(_HOST_READING_NOTE)
    return '\n'.join(lines)

def _render_prompt_pattern(name: str) -> str:
    header = f'=== lang_query(kind=prompt_pattern, name={name!r}) ==='
    try:
        entry = confirmation_prompt_of(name)
    except QueryUnavailable as exc:
        return f'error: prompt_pattern query unavailable — {exc}'
    if entry is None:
        return f"{header}\nnot found — {name!r} is not among the recorded confirmation-prompt sequences projected from 框架镜像源（出处已脱敏）(the ssl_comm.py CSR/CA methods and apv.py::reboot). This does NOT mean this method has no confirmation prompt — it means no precedent sequence for it is in this projection yet (the projection's scope is currently lib/ only). If you suspect it does trigger one, the framework-wide pattern is: the triggering command must be sent with an anchor (`,prompt=<expected-text>`, not the default prompt), then each response step waits for its own anchor in turn — retrieve the actual anchor values from the version manual, not by guessing a generic ':'."
    steps = entry['steps']
    steps_repr = '; '.join((f"{s['send']!r} -> wait_for {s['wait_for']!r}" for s in steps))
    lines = [header, f"trigger_command: {entry['trigger_command']}", f'steps ({len(steps)}): {steps_repr}', f"anchor_values_used: {entry['anchor_values_used']}"]
    fsna = entry['final_step_no_anchor']
    if fsna == 'no_anchor':
        lines.append(f"final_step_no_anchor: no_anchor — after the steps above, send {entry['final_step_value']!r} with NO anchor (returns to the default prompt)")
    elif fsna == 'has_anchor':
        lines.append(f"final_step_no_anchor: has_anchor — {entry['final_step_note']}")
    else:
        lines.append(f"final_step_no_anchor: not_observed — {entry['final_step_note']}")
    p = entry['provenance']
    lines.append(f"source: {p['file']}:{p['def_line']} ({p['function']})")
    return '\n'.join(lines)

def _render_nearest(name: str, domain: str) -> str:
    header = f'=== lang_query(kind=nearest, name={name!r}) ==='
    if domain:
        try:
            pool = dispatch_domain_orientation(domain)['names']
        except (ValueError, QueryUnavailable) as exc:
            return f'error: {exc}'
    else:
        pool = apv_full_fs()
        if not pool:
            return 'error: nearest query unavailable — mirror unreachable, apv_full_fs() is empty'
    ranked = nearest_candidates(name, pool, top_n=5)
    return f"{header}\nnearest candidates (ranked by similarity, for reference only — confirm deliberately, this never auto-rewrites): {', '.join(ranked)}"

def _value_domain_lines(argument: object, *, manual_version: str='') -> list[str]:
    if not isinstance(argument, dict):
        return []
    if str(argument.get('type') or '') == 'REDACTED_SENSITIVE' and argument.get('executable') is False:
        return ['    value domain: not applicable — this position holds a credential-class literal, so the projection redacts it and the rule rejects any value here with `sensitive_parameter_unexecutable`, whatever you write']
    domain = argument.get('value_domain')
    if not isinstance(domain, dict) or not domain:
        return ['    value domain: not recorded for this position — the rule checks it on type/arity only; that is a gap in our projection, NOT a statement that the device accepts anything here']
    from cex_core.engine.kms.manual_locator import display_manual_locator, parse_adoc_style_src
    lines = ['    value domain (claims listed side by side; no source wins):']
    rejecting = False
    for kind in ('enum', 'union', 'range', 'length', 'default'):
        for claim in domain.get(kind) or []:
            if not isinstance(claim, dict):
                continue
            source = str(claim.get('source') or '')
            if kind == 'enum':
                body = 'one of ' + ', '.join((repr(str(item)) for item in claim.get('values') or []))
            elif kind == 'union':
                separator = str(claim.get('separator') or '')
                body = f'two or more of the listed members joined by {separator!r} are also accepted here'
            elif kind == 'default':
                body = f"documented default {str(claim.get('value'))!r}"
            else:
                body = f"{kind} {claim.get('min')}..{claim.get('max')}"
            if kind == 'union':
                note = ' (composition syntax stated verbatim in the XML help; the rule splits on it before rejecting)'
            elif kind in {'length', 'default'}:
                note = ' (supply only, not a rejection rule)'
            elif kind == 'enum' and source == 'xml_help':
                note = ' (accept-only: XML help lists these as legal, which does not prove the set is closed, so the rule never rejects on it)'
            else:
                note = ''
                rejecting = True
            raw_locator = str(claim.get('locator') or '')
            if source == 'manual_table' and manual_version and parse_adoc_style_src(raw_locator):
                shown_locator = display_manual_locator(raw_locator, version=manual_version)
            else:
                shown_locator = raw_locator
            lines.append(f'      {body}{note} — source: {source}, locator: {shown_locator}')
    if not rejecting:
        lines.append('      no claim on this position can carry a rejection — the rule still checks it on type/arity only')
    return lines

def _token_permutation_fact_lines(name: str) -> list[str]:
    """同词异序是投影事实，不是推荐；子弹用 ``  * `` 以免打乱 complete 的 ``  - `` 列表。"""
    from cex_core.engine.case_compiler.vendor_stdlib import recorded_heads_with_token_permutation
    hits = recorded_heads_with_token_permutation(name)
    if not hits:
        return []
    return [f"{len(hits)} recorded head(s) use the same words as {name!r} in a different order (or with at most one extra token). Verbatim from this build's tree, never auto-applied. This list is not a recommendation:", *(f'  * {head}' for head in hits)]
_PERMUTATION_NEXT_PARAM = "next: lang_query(kind='param', name=<one of these heads>) for that head's argument contract."
_PERMUTATION_NEXT_COMPLETE = "next: lang_query(kind='param', name=<one of these heads>) for that head's per-argument XML contract side by side with the manual's explanation."

def _permutation_fact_block(name: str, next_line: str) -> list[str]:
    """同词异序的已记载头 + 它那句 `next:`；没有这样的头就整块不出。

    param 两条未命中支与 complete 零命中支从前各写一遍同一个 `extend` + `if 非空
    再 append` 的形状（前两份逐字符相同），只有 `next:` 那句在 complete 面不同。
    """
    permutation = _token_permutation_fact_lines(name)
    return [*permutation, next_line] if permutation else []

def _next_token_fact_lines(name: str, *, truncated: bool) -> list[str]:
    """前缀族被 complete 截断、或查询多出未命中词时，交出共享前缀后的下一词闭集。

    Bug77137_4 s5：``sdns pool`` 191 头截成 disable/enable/failover/fallback/mx，
    定义头 ``sdns pool name`` 不在前 5；模型改猜 create/add 直到预算耗尽。
    下一词是库存事实，不是推荐；子弹用 ``  * ``。
    """
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens, recorded_next_tokens_after_shared_prefix
    fact = recorded_next_tokens_after_shared_prefix(name)
    if not fact:
        return []
    query = norm_command_tokens(name)
    extra_unmatched = fact['shared_tokens'] < len(query)
    if not truncated and (not extra_unmatched):
        return []
    shown = list(fact['tokens'])
    total = int(fact['total'])
    lines = [f"next-token fact from the same projection: {total} recorded token(s) appear at word {fact['position']} after {fact['prefix']!r}. Verbatim inventory of this build's tree, never auto-applied, not a ranking:", *(f'  * {tok}' for tok in shown)]
    if total > len(shown):
        lines.append(f'{total - len(shown)} further recorded token(s) at that position are NOT listed.')
    return lines

def _render_param(name: str, position: int | None=None) -> str:
    from cex_core.engine.case_compiler.apv_lang import MANUAL_SOURCE_UNAVAILABLE, NOT_DIRECTLY_HIT, PARAM_CONTRACT_UNAVAILABLE, manual_param_excerpt, param_contract_of
    from cex_core.engine.case_compiler.vendor_stdlib import manual_source_dir
    lines = [f'=== lang_query(kind=param, name={name!r}) ===']
    contract = param_contract_of(name, position=position)
    manual_root = manual_source_dir()
    manual_version = manual_root.name if manual_root is not None else ''
    if contract is None:
        lines.append('XML: loaded command tree has no matching head for this name — capability unknown for this lookup, not a device rejection')
        lines.extend(_permutation_fact_block(name, _PERMUTATION_NEXT_PARAM))
    elif contract.get('status') == PARAM_CONTRACT_UNAVAILABLE:
        reason = str(contract.get('reason') or 'command-tree projection could not be loaded')
        lines.append(f'XML: {reason} — this is a missing projection on our side, not a statement that the command is absent and not a statement that it is present')
        lines.extend(_permutation_fact_block(name, _PERMUTATION_NEXT_PARAM))
    else:
        lines.append(f"XML (version {contract['version']}, build {contract['device_os_build']}, head: {contract['head']}):")
        if not contract['args']:
            lines.append('  (no parameters declared)')
        for item in contract['args']:
            mark = '  <-- selected' if contract['selected'] is item else ''
            lines.append(f"  position {item.get('position')}: {item.get('type')}{(', optional' if item.get('optional') else '')} — help: {item.get('help')!r}{mark}")
            lines.extend(_value_domain_lines(item, manual_version=manual_version))
        if position is not None and contract['selected'] is None:
            lines.append(f'  position {position}: no entry at this position')
    excerpt = manual_param_excerpt(name)
    if excerpt['hit']:
        for section in excerpt['sections']:
            note = '' if section['has_parameter_table'] else ' (section has no parameter table)'
            filename = Path(str(section['file'])).name
            if manual_version and filename:
                locator = f"{manual_version}/{filename}:{section['line']}"
            else:
                locator = f"{section['file']}:{section['line']}"
            lines.append(f'manual:{locator}{note}')
            lines.append(section['text'])
    elif excerpt['note'] == MANUAL_SOURCE_UNAVAILABLE:
        lines.append(f'manual: {MANUAL_SOURCE_UNAVAILABLE} — the manual root comes from the command tree projection and the projection is not loadable; this is a supply failure, not evidence that the manual lacks this command')
    else:
        lines.append(f'manual: {NOT_DIRECTLY_HIT}')
    return '\n'.join(lines)
COMPLETE_PROJECTION_UNAVAILABLE_MARK = 'could not be loaded, so no completion can be offered'

def _render_complete(name: str) -> str:
    from cex_core.engine.case_compiler.vendor_stdlib import load_vendor_stdlib, norm_command_tokens, rank_vendor_command_completions
    header = f'=== lang_query(kind=complete, name={name!r}) ==='
    inventory = load_vendor_stdlib()
    if inventory is None:
        return f'{header}\ncapability unknown — the vendor command-tree projection for this device build {COMPLETE_PROJECTION_UNAVAILABLE_MARK}. That is a missing projection on our side, NOT a statement about whether the command exists on the device.'
    identity = f"projection: version {inventory.get('version', '')}, build {inventory.get('device_os_build', '')}, {len(inventory.get('heads') or {})} recorded command heads"
    ranked = rank_vendor_command_completions(name)
    if not ranked:
        lines = [header, identity, f"0 recorded heads share a leading token with {name!r}. Two readings stay open and this tool does not pick one: the first word may be misspelled, or this command family may genuinely not be in this build's tree. Nothing is rewritten for you."]
        lines.extend(_permutation_fact_block(name, _PERMUTATION_NEXT_COMPLETE))
        return '\n'.join(lines)
    shown = ranked[:_COMPLETE_SHOWN_K]
    continuing = sum((1 for candidate in ranked if candidate['prefix_continuation']))
    lines = [header, identity, f'{len(ranked)} recorded head(s) line up with {name!r} — each shares at least one whole leading token with it, or continues one of your tokens as a prefix. In {continuing} of them the recorded token at the first position that did not match as a whole word starts with your token there; when the word you left half-typed is your last one, that is the completion you are after. Showing the {len(shown)} highest-ranked, verbatim from the projection, never auto-applied. Ranking: most whole leading tokens shared first, then heads whose next recorded token starts with your token at that position, then the shortest head:', *(f"  - {candidate['head']}" for candidate in shown)]
    if len(ranked) > len(shown):
        lines.append(f'{len(ranked) - len(shown)} further recorded candidate(s) exist and are NOT listed above — this list is truncated, so its absence from these lines is not evidence that a head is missing from the build. Type more of the head into name= to narrow the ranking.')
    query_tokens = norm_command_tokens(name)
    if query_tokens and continuing == 0:
        top_shared = max((candidate['shared_tokens'] for candidate in ranked))
        tied_at_top = sum((1 for candidate in ranked if candidate['shared_tokens'] == top_shared))
        headers = inventory.get('headers') or {}
        longest_prefix_is_recorded_head = any((' '.join(query_tokens[:k]) in headers for k in range(len(query_tokens) - 1, 0, -1)))
        if top_shared < len(query_tokens) and tied_at_top > _COMPLETE_SHOWN_K and (not longest_prefix_is_recorded_head):
            from cex_core.engine.ist_core.worker_device_context import recorded_command_heads
            for k in range(len(query_tokens) - 1, 0, -1):
                parent_heads = recorded_command_heads(inventory, ' '.join(query_tokens[:k]))
                if parent_heads:
                    position = k + 1
                    lines.append(f"heads fact from the same projection: {len(parent_heads)} recorded head(s) begin with {' '.join(query_tokens[:k])!r}, and 0 begin with {' '.join(query_tokens[:position])!r} — query word {position}, {query_tokens[k]!r}, has no recorded head at that position in this build's vendor XML command tree.")
                    break
    lines.extend(_next_token_fact_lines(name, truncated=len(ranked) > len(shown)))
    lines.extend(_token_permutation_fact_lines(name))
    lines.append(_PERMUTATION_NEXT_COMPLETE)
    return '\n'.join(lines)

def command_heads_result(module_prefix: str) -> CommandHeadsQueryResult:
    prefix = ' '.join(str(module_prefix or '').split()).casefold()
    base: CommandHeadsQueryResult = {'schema': COMMAND_HEADS_QUERY_SCHEMA, 'status': 'worker_session_unavailable', 'module_prefix': prefix, 'device_build': '', 'capability_generation_id': '', 'capability_manifest_sha256': '', 'projection_version': '', 'count': 0, 'heads': [], 'receipt_id': '', 'result_sha256': ''}
    try:
        from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
        session = current_worker_device_session()
    except Exception:
        session = None
    if session is None:
        return base
    device_build = str(session.capability_build or '').strip()
    base['device_build'] = device_build
    base['capability_generation_id'] = str(session.capability_generation_id or '').strip()
    base['capability_manifest_sha256'] = str(session.capability_manifest_sha256 or '').strip().lower()
    if not device_build:
        base['status'] = 'capability_build_missing'
        return base
    from cex_core.engine.case_compiler.vendor_stdlib import load_vendor_stdlib
    inventory = load_vendor_stdlib(device_build=device_build)
    if inventory is None:
        base['status'] = 'command_tree_unavailable'
        return base
    inventory_build = str(inventory.get('device_os_build') or '').strip()
    if inventory_build and inventory_build != device_build:
        base['status'] = 'capability_identity_mismatch'
        return base
    from cex_core.engine.ist_core.worker_device_context import recorded_command_heads
    heads = recorded_command_heads(inventory, prefix)
    result: CommandHeadsQueryResult = {**base, 'status': 'complete', 'device_build': device_build, 'projection_version': str(inventory.get('version') or ''), 'count': len(heads), 'heads': heads}
    import json
    budget_candidate = {**result, 'receipt_id': 'r' * 256, 'result_sha256': '0' * 64}
    if len(json.dumps(budget_candidate, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')) > _MAX_HEADS_RESULT_BYTES:
        return {**base, 'status': 'result_too_large', 'projection_version': str(inventory.get('version') or ''), 'count': len(heads)}
    receipt, receipt_error = session.record_command_heads_query(result)
    if receipt_error:
        result['status'] = 'receipt_unavailable'
        return result
    return {**result, 'receipt_id': str(receipt.get('receipt_id') or ''), 'result_sha256': str(receipt.get('result_sha256') or '')}

def _render_heads(module_prefix: str) -> str:
    result = command_heads_result(module_prefix)
    header = f'=== lang_query(kind=heads, name={module_prefix!r}) ==='
    if result['status'] != 'complete':
        if result['status'] == 'result_too_large':
            return '\n'.join([header, f"schema: {result['schema']}", f"status: {result['status']}", f"module: {result['module_prefix']}", f"device_build: {result['device_build']}", f"recorded_heads: {result['count']}", f"[{result['count']} truncated]", "error: the complete inventory exceeds the tool-result byte limit; zero heads are shown and no completeness receipt was minted. name= accepts a multi-token prefix: tokens are matched as whole words from the left, so a longer prefix narrows the listing to only the heads that begin with it. Use kind='complete' with a longer command prefix to inspect a bounded candidate list, but do not treat that list as proof that the module has no equivalent command."])
        return f"error: {result['status']} — schema={result['schema']} module={result['module_prefix']!r} device_build={result['device_build']!r}"
    lines = [header, f"schema: {result['schema']}", f"module: {result['module_prefix']}", f"projection_version: {result['projection_version']}", f"device_build: {result['device_build']}", f"capability_generation_id: {result['capability_generation_id']}", f"capability_manifest_sha256: {result['capability_manifest_sha256']}", f"receipt_id: {result['receipt_id']}", f"result_sha256: {result['result_sha256']}", f"recorded_heads: {result['count']}", *(f'  - {head}' for head in result['heads'])]
    if result['count'] == 0:
        lines.append("note: zero recorded heads begin with this prefix in this build's vendor XML command tree. name= accepts a multi-token prefix — tokens are matched as whole words from the left, so a longer prefix narrows the list and a shorter one widens it.")
    return '\n'.join(lines)

def _render_docs(query: str) -> str:
    header = f'=== lang_query(kind=docs, query={query!r}) ==='
    try:
        catalog = language_document_catalog(query)
    except QueryUnavailable as exc:
        return f'error: language docs query unavailable — {exc}'
    matches = catalog['matches']
    if not matches:
        return f'{header}\n0 indexed language assets matched'
    lines = [header, f'matches: {len(matches)}']
    for entry in matches:
        details = []
        for key in ('status', 'record_count', 'device_os_build'):
            if entry.get(key) not in (None, ''):
                details.append(f'{key}={entry[key]}')
        suffix = f" ({', '.join(details)})" if details else ''
        lines.append(f"- {entry.get('id', '')}: {entry.get('path', '')}{suffix}")
        if entry.get('symbols'):
            lines.append(f"  symbols: {', '.join(entry['symbols'])}")
        if entry.get('sections'):
            lines.append(f"  sections: {', '.join(entry['sections'])}")
    return '\n'.join(lines)

def _with_recompose_grounding(render: Callable[[], str], *, kind: str, name: str, domain: str, query: str, position: int, scope_refusal_reason: str='') -> str:
    from cex_core.engine.ist_core.tools.device.recompose_submission import resolve_recompose_command_grounding
    result, receipt = resolve_recompose_command_grounding(render, kind=kind, name=name, domain=domain, query=query, position=position, scope_refusal_reason=scope_refusal_reason)
    if receipt is None:
        return result
    return f'{result}\ngrounding_receipt: {receipt}'

@tool(parse_docstring=True)
def lang_query(kind: str, name: str='', domain: str='', query: str='', position: int=0) -> str:
    """Look up what you can fill before you write it — APV symbols, dispatch, precedent usage, confirmation prompts, near-miss names, and the unified language-document catalog.

    **When to use**: before writing a value into the F column (or deciding between two
    similarly-named methods), especially for domains where a wrong F is a silent semantic
    error rather than a device rejection (device syntax checks catch typos in commands;
    they do not catch "called the wrong-but-valid method"). Query first, write second.
    **When not to use**: after you've already written steps and want to check them for
    structural mistakes — that's compile_lint, not this tool (this tool is context-free
    symbol lookup; compile_lint is context-bound draft validation).
    A successful result completes only the requested lookup. This tool has no case
    context and never decides whether the current case has enough evidence to draft;
    that semantic decision remains with the authoring model.

    Args:
        kind: one of contract / signature / dispatch / usage / host / nearest / prompt_pattern / docs / param / complete / heads.
            contract — with no domain, list every E-column value the contract knows,
            split into "has an enabled function surface" and "has none" (with each
            unusable one's shape and dominant reason), so you never have to discover an
            E by being rejected. With domain=<exact E value>, list that object's
            enabled/disabled/internal F surface. With domain+name, return the exact E/F
            contract including Python symbol, full signature, G/H/I semantics, dispatch,
            status, source and minimum runtime; name='execute' additionally dumps that
            E's whole execute action registry, led by a summary of which actions are
            enabled and on which E seats they can actually be written. The generated
            function contract is the authority for workbook choices.
            signature — name required. Parameter schema (required/optional) for one F
            method, from the frozen capability atlas.
            dispatch — give name for a point lookup (how does this one F name get
            dispatched — direct method call / execute registry / cmd primitive), or give
            domain instead for a domain-level orientation (all methods in one of
            ssl_comm/seg_comm/ha_comm/preparation, plus curated disambiguation notes
            where they exist — use this when you know roughly what area you're working
            in but not which exact method to call). Give exactly one of name/domain for
            this kind.
            usage — name required. Real usage from the current device-verified mirror
            corpus — has anyone actually used this, and what did it look like.
            host — name required (one host slot, e.g. the machine an E=test_env row
            addresses); query optional (a substring to search the recorded command
            texts). Answers "what have other people already run on this machine": the
            complete first-token histogram of every step row written against that slot,
            plus verbatim command texts with their case file, autoid and description.
            Two columns are kept apart and never summed — the vendor smoke-test corpus
            (what the vendor suite ran on that bed) carries the verbatim text; our own
            device-verified cases are reported as counts only, because they have not
            been through that bed's long-running vendor use and are not precedent for
            what the machine tolerates. Everything is past tense: this kind reports what
            was run, never what the machine offers today, and it hands you no mapping
            from a command to a service, port or role — read the tokens yourself.
            prompt_pattern — name required. Does calling this method trigger a
            confirmation prompt (a `[y/n]`-style dialogue), and if so, the real
            trigger command + ordered response steps + each step's expected-text anchor,
            projected from the real sequences recorded in the framework mirror. Query this before
            writing a `,prompt=<anchor>` kwarg from a guess —
            a command that can hit a confirmation and is sent without the right anchor
            waits out the full timeout and returns a truncated echo silently (no error).
            nearest — name required (the name you're unsure is spelled right); domain
            optional to narrow the candidate pool to one family, otherwise searches the
            full apv_full dispatch surface.
            docs — query optional. Search the unified catalog of checkers, skill library,
            method reference, domain grammar, footprint, behavior ledger, and the
            probe-to-ConfigBinding evidence pipeline. An empty query lists all entries.
            param — name required (the device CLI command head, e.g. "sdns host
            persistence"); position optional (1-based argument index). Returns the
            vendor command-tree XML per-argument contract (position/type/optional/
            help) side by side with the CLI/APP manual's parameter explanation —
            both verbatim, no recommendation. Use this when you are unsure what a
            command argument means or which written form it accepts; the judgment
            is yours, this kind only hands you the two source texts.
            complete — name required (a command head, or the prefix you have so far;
            an unfinished last word is fine and is ranked as a prefix, so "slb virtual
            httpl" surfaces "slb virtual httplist"). Returns the nearest command heads
            actually recorded in this device build's command tree, verbatim and never
            applied for you. Use it before concluding "this build doesn't have the
            command": a head that shares three leading tokens with yours usually means
            a typo, zero shared heads means the family may genuinely be absent. The
            printed list is truncated and says by how much — a head missing from those
            lines is not evidence it is missing from the build; narrow name= instead.
            This kind hands you the evidence and leaves the reading to you.
            heads — name required (a command module prefix; multiple tokens are
            accepted and matched as whole words from the left, so a longer prefix
            narrows the listing). Lists every command head under that prefix in
            the vendor XML command tree of the current compile-worker session's
            engine-sealed capability build. The result is the projection's lexical
            inventory only: no use-case matching, recommendation, or preferred order.
        name: the bare F value, execute action name, host slot, command head, or command
            module to query (required for signature/usage/host/nearest/prompt_pattern/
            param/complete/heads; one of name/domain required for dispatch).
        domain: for kind=contract, an exact E-column value such as APV_0 or check_point;
            omit it to list the whole E surface.
            For kind=dispatch, one of ssl_comm/seg_comm/ha_comm/preparation (the
            framework's own mixin class names — the same names atlas/mirror use, not a
            shorthand). Also accepted as an optional narrowing filter for kind=nearest.
        query: free-text filter for kind=docs (all whitespace-separated terms must match
            the same catalog entry), or for kind=host a single substring matched
            case-insensitively against each recorded command's first token and text.
        position: for kind=param, the 1-based argument index to mark as selected;
            0 (default) lists the full argument surface.

    Returns:
        A found/not-found/query-failed rendering specific to the kind queried. A "not
        found" result is never worded as a rejection — for usage it explicitly states
        that zero corpus hits does not mean the framework lacks support, only that no
        precedent exists yet; for prompt_pattern it explicitly states that not being
        among the recorded sequences does not mean the method has no confirmation
        prompt, only that this projection's current scope doesn't cover it. A dispatch
        point-lookup additionally cross-checks the curated atlas snapshot against live
        reflection and, on a mismatch, states plainly that the atlas needs regenerating
        — not that you filled anything incorrectly.
    """
    k = (kind or '').strip().lower()
    if k not in _KINDS:
        return f"error: kind must be one of {'/'.join(_KINDS)}, got {kind!r}"
    name = (name or '').strip()
    domain_raw = (domain or '').strip()
    domain = domain_raw.lower()
    if k == 'contract':
        if not domain_raw:
            return _render_contract_index()
        return _render_contract(domain_raw, name)
    if k == 'signature':
        if not name:
            return "error: kind='signature' requires name"
        return _render_signature(name)
    if k == 'dispatch':
        if bool(name) == bool(domain):
            return "error: kind='dispatch' requires exactly one of name or domain, not both/neither"
        return _render_dispatch_domain(domain) if domain else _render_dispatch_point(name)
    if k == 'usage':
        if not name:
            return "error: kind='usage' requires name"
        return _render_usage(name)
    if k == 'host':
        if not name:
            return "error: kind='host' requires name (one host slot)"
        return _render_host(name, query)
    if k == 'prompt_pattern':
        if not name:
            return "error: kind='prompt_pattern' requires name"
        return _render_prompt_pattern(name)
    if k == 'docs':
        return _render_docs(query or name)
    if k == 'param':
        if not name:
            return "error: kind='param' requires name (the device CLI command head)"
        return _with_recompose_grounding(lambda: _render_param(name, position or None), kind=k, name=name, domain=domain_raw, query=query, position=position)
    if k == 'complete':
        if not name:
            return "error: kind='complete' requires name (a command head or its prefix)"
        return _with_recompose_grounding(lambda: _render_complete(name), kind=k, name=name, domain=domain_raw, query=query, position=position)
    if k == 'heads':
        if not name:
            return "error: kind='heads' requires name (a command module prefix)"
        from cex_core.engine.ist_core.tools.device.recompose_submission import RECOMPOSE_HEADS_SCOPE_REFUSAL, RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT, in_recompose_dispatch_scope
        if in_recompose_dispatch_scope():
            return _with_recompose_grounding(lambda: RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT, kind=k, name=name, domain=domain_raw, query=query, position=position, scope_refusal_reason=RECOMPOSE_HEADS_SCOPE_REFUSAL)
        return _with_recompose_grounding(lambda: _render_heads(name), kind=k, name=name, domain=domain_raw, query=query, position=position)
    if not name:
        return "error: kind='nearest' requires name"
    return _render_nearest(name, domain)
compile_query = lang_query
