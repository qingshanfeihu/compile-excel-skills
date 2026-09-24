# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/mechanical_case_gate.py（sha256 67c35edc10da202a）。不在这里手改。
from __future__ import annotations
import ipaddress
import json
import logging
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler._sealed_io import sha256_bytes
from cex_core.engine.case_compiler.blocks import _CONFIG_STEP_FUNCTIONS
from cex_core.engine.case_compiler.consistency_contract import SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY
from cex_core.engine.case_compiler.mechanical_case import MECHANICAL_GATE_REPORT_SCHEMA, MECHANICAL_CASE_BODY_KEYS, EscapeHatchDefect, MechanicalCaseBinding, MechanicalCaseDescription, MechanicalCaseError, MechanicalCaseEscapeHatch, MechanicalCaseExpectationBinding, escape_hatch_accounting_defects, seal_mechanical_case, validate_mechanical_case
from cex_core.engine.case_compiler.mindmap_contract_projector import _canonical_sha256
from cex_core.engine.common.schema_identity import accepts_schema
logger = logging.getLogger(__name__)
GATE_REPORT_SCHEMA = MECHANICAL_GATE_REPORT_SCHEMA
GATE_ORDER: tuple[str, ...] = ('mechanical_case_body', 'contract_description', 'consistency_contract', 'blocks_expansion', 'structural_lint', 'command_contract', 'author_procedure_coverage', 'https_certificate_lifecycle', 'unreachable_ips', 'trigger_reachability', 'negative_probe_path', 'paired_teardown', 'provenance_receipts', 'expectation_bijection', 'criterion_type_binding', 'semantic_key_group_rank', 'answerer_statement', 'escape_hatch_accounting', 'document_consistency', 'step_graph')
NUMBERED_GATES: tuple[str, ...] = ('blocks_expansion', 'structural_lint', 'expectation_bijection', 'semantic_key_group_rank', 'escape_hatch_accounting', 'unreachable_ips', 'trigger_reachability', 'paired_teardown', 'command_contract', 'https_certificate_lifecycle')
AUDIENCE_WORKER = 'worker_directive'
AUDIENCE_VERIFICATION_CARD = 'verification_card'
_PROVISIONAL_GATE_REPORT_SHA256 = '0' * 64
_CHECK_POINT_OBJECT = 'check_point'
from cex_core.engine.case_compiler.gate_advisories import ADVISE_CODE_CONSUMERS
DYNAMIC_ADVISE_CODE_FAMILIES: dict[str, str] = {'_gate_structural_lint': 'gate_advisory', '_gate_step_graph': 'gate_advisory'}

class _Report:

    def __init__(self, autoid: str) -> None:
        self.autoid = autoid
        self.hard_rejects: list[dict[str, Any]] = []
        self.advisories: list[dict[str, Any]] = []
        self._ran: set[str] = set()
        self._named_by: dict[str, str] = {}

    def ran(self, gate: str) -> None:
        self._ran.add(gate)

    def reject(self, gate: str, code: str, locus: str, detail: str, *, expectation_ids: Sequence[str]=()) -> None:
        self._ran.add(gate)
        finding: dict[str, Any] = {'gate': gate, 'code': code, 'locus': locus, 'detail': detail, 'audience': AUDIENCE_WORKER}
        bound = sorted({str(value) for value in expectation_ids if str(value)})
        if bound:
            finding['expectation_ids'] = bound
        self.hard_rejects.append(finding)

    def advise(self, gate: str, code: str, locus: str, detail: str, **extra: Any) -> None:
        if code not in ADVISE_CODE_CONSUMERS:
            raise ValueError(f'unregistered gate advisory: {code}')
        self._ran.add(gate)
        self.advisories.append({'gate': gate, 'code': code, 'locus': locus, 'detail': detail, 'audience': AUDIENCE_VERIFICATION_CARD, **extra})

    def reject_named_by(self, gate: str, other: str) -> None:
        self._ran.add(gate)
        self._named_by[gate] = other

    def rejected(self, gate: str) -> bool:
        return any((item['gate'] == gate for item in self.hard_rejects))

    def status(self, gate: str) -> str:
        if gate not in self._ran:
            return 'skipped'
        if self.rejected(gate) or gate in self._named_by:
            return 'reject'
        if any((item['gate'] == gate for item in self.advisories)):
            return 'advisory'
        return 'pass'

    def render(self, measurements: dict[str, Any] | None, proof: Mapping[str, str]) -> dict[str, Any]:
        gates: list[dict[str, Any]] = []
        for gate in GATE_ORDER:
            findings = [item for item in (*self.hard_rejects, *self.advisories) if item.get('gate') == gate]
            entry = {'gate': gate, 'status': self.status(gate), 'reason_codes': sorted({str(item.get('code') or '') for item in findings if str(item.get('code') or '')}), 'evidence_loci': sorted({str(item.get('locus') or '') for item in findings if str(item.get('locus') or '')})}
            if gate in self._named_by:
                entry['named_by'] = self._named_by[gate]
            gates.append(entry)
        return {'schema': GATE_REPORT_SCHEMA, 'autoid': self.autoid, 'ok': not self.hard_rejects, 'gates': gates, 'hard_rejects': list(self.hard_rejects), 'advisories': list(self.advisories), 'measurements': measurements, 'proof': dict(proof)}

def gate_report_digest(report: Mapping[str, Any]) -> str:
    return _canonical_sha256(dict(report))

def load_frozen_contract(path: str | Path) -> tuple[dict[str, Any], str]:
    raw = Path(path).read_bytes()
    payload = json.loads(raw.decode('utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('contract card must be a JSON object')
    return (payload, sha256_bytes(raw))

def semantic_key_group_defects(assertions: Sequence[Any]) -> list[tuple[str, list[str], int, int]]:
    groups: dict[str, list[Any]] = {}
    for step in assertions:
        groups.setdefault(str(getattr(step, 'semantic_key', '') or ''), []).append(step)
    defects: list[tuple[str, list[str], int, int]] = []
    for key, group in sorted(groups.items()):
        signatures = {(str(getattr(step, 'observation_ref', '') or ''), step.F, step.G) for step in group}
        if len(signatures) != len(group):
            defects.append((key, [str(getattr(step, 'expectation_id', '') or '') for step in group], len(signatures), len(group)))
    return defects

def _gate_body(mc: Any, report: _Report) -> dict[str, Any] | None:
    gate = 'mechanical_case_body'
    report.ran(gate)
    if not isinstance(mc, Mapping):
        report.reject(gate, 'not_an_object', 'case', 'mechanical case body must be a JSON object')
        return None
    body = dict(mc)
    if 'seal' in body:
        report.reject(gate, 'seal_self_reported', 'seal', 'the seal is minted by these submission rules after its report is final; submit the eight body keys only')
        return None
    keys = set(body)
    if keys != MECHANICAL_CASE_BODY_KEYS:
        report.reject(gate, 'body_keys_mismatch', 'case', f'missing={sorted(MECHANICAL_CASE_BODY_KEYS - keys)}, unknown={sorted(keys - MECHANICAL_CASE_BODY_KEYS)}')
        return None
    segments: tuple[tuple[str, Any, Any], ...] = (('description', MechanicalCaseDescription, body.get('description')), ('binding', MechanicalCaseBinding, body.get('binding')))
    for name, model, value in segments:
        try:
            model.model_validate(value, strict=True)
        except Exception as exc:
            report.reject(gate, 'segment_invalid', name, _first_error(exc))
    for name, model in (('expectation_binding', MechanicalCaseExpectationBinding), ('escape_hatches', MechanicalCaseEscapeHatch)):
        entries = body.get(name)
        if not isinstance(entries, list):
            report.reject(gate, 'segment_invalid', name, f'{name} must be an array')
            continue
        for index, entry in enumerate(entries):
            try:
                model.model_validate(entry, strict=True)
            except Exception as exc:
                report.reject(gate, 'segment_invalid', f'{name}[{index}]', _first_error(exc))
    if not isinstance(body.get('blocks'), list) or not body['blocks']:
        report.reject(gate, 'segment_invalid', 'blocks', 'blocks must be a non-empty array of combinators')
    if not isinstance(body.get('init_commands'), list):
        report.reject(gate, 'segment_invalid', 'init_commands', 'init_commands must be an array of command strings')
    return None if report.rejected(gate) else body

def _gate_contract_description(body: Mapping[str, Any], contract: Mapping[str, Any], report: _Report) -> None:
    gate = 'contract_description'
    report.ran(gate)
    description = body.get('description')
    mindmap_group = contract.get('mindmap_group')
    expected_path = mindmap_group.get('group_path') if isinstance(mindmap_group, Mapping) else None
    if not isinstance(description, Mapping):
        return
    actual_intent = str(description.get('intent_verbatim') or '')
    expected_intent = str(contract.get('intent_verbatim') or '')
    if actual_intent != expected_intent:
        report.reject(gate, 'intent_verbatim_mismatch', 'description.intent_verbatim', f'description.intent_verbatim must be copied byte-for-byte from the frozen contract card. Do not replace the author title with a procedure summary. expected={expected_intent!r}; actual={actual_intent!r}')
    actual_path = description.get('group_path')
    if not isinstance(expected_path, list) or actual_path != expected_path:
        report.reject(gate, 'group_path_mismatch', 'description.group_path', f'description.group_path must be copied byte-for-byte and in order from contract.mindmap_group.group_path; expected={expected_path!r}; actual={actual_path!r}')
_AUTHOR_STEP_ENUMERATOR_RE = re.compile('^\\s*\\d+\\s*[.)、:：]\\s*')

def _procedure_command_signature(vendor: Any, command: str, verdict: Mapping[str, Any]) -> str:
    head = str(verdict.get('head') or '').strip()
    tokens = list(vendor.norm_command_tokens(command))
    head_tokens = list(vendor.norm_command_tokens(head))
    remainder = tokens[len(head_tokens):] if tokens[:len(head_tokens)] == head_tokens else []
    first = remainder[0] if remainder else ''
    if first and _first_argument_is_descriptive(first):
        first = _DESCRIPTIVE_FIRST_ARGUMENT
    elif first:
        try:
            ipaddress.ip_address(first)
        except ValueError:
            first = '<number>' if re.fullmatch('\\d+', first) else first.casefold()
        else:
            first = '<ip>'
    return f'{head}␟{first}'
_DESCRIPTIVE_FIRST_ARGUMENT = '<descriptive>'

def _first_argument_is_descriptive(token: str) -> bool:
    return not str(token).isascii()

def _gate_author_procedure_coverage(contract: Mapping[str, Any], steps: Sequence[Any], init: str, report: _Report, *, device_build: str) -> None:
    gate = 'author_procedure_coverage'
    report.ran(gate)
    from cex_core.engine.case_compiler.step_structure import ADAPTED_STEPS_KEY
    adapted_rows = [row for row in contract.get(ADAPTED_STEPS_KEY) or [] if isinstance(row, Mapping) and str(row.get('n') or '') and str(row.get('text') or '')]
    authored_rows = contract.get('author_steps')
    author_steps = adapted_rows or authored_rows
    if not isinstance(author_steps, list) or not author_steps:
        return
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import _ordered_apv_command_refs, build_command_tree_resolver
    vendor, _inventory, resolve = build_command_tree_resolver(device_build=device_build)

    def _obligations(rows: Any, label: str) -> tuple[Counter[str], dict[str, list[str]], Counter[str]]:
        req: Counter[str] = Counter()
        ev: dict[str, list[str]] = {}
        heads: Counter[str] = Counter()
        for step in rows or ():
            if not isinstance(step, Mapping):
                continue
            step_id = str(step.get('n') or '')
            for raw_line in str(step.get('text') or '').splitlines():
                candidate = _AUTHOR_STEP_ENUMERATOR_RE.sub('', raw_line.strip())
                if not candidate:
                    continue
                verdict = resolve(candidate)
                if verdict.get('kind') != 'hit':
                    continue
                signature = _procedure_command_signature(vendor, candidate, verdict)
                req[signature] += 1
                heads[signature.partition('␟')[0]] += 1
                ev.setdefault(signature, []).append(f'{label}[{step_id}]={candidate!r}')
        return (req, ev, heads)
    required, evidence, required_heads = _obligations(author_steps, 'author_steps')
    if adapted_rows and isinstance(authored_rows, list):
        authored_required, authored_evidence, authored_heads = _obligations(authored_rows, 'author_steps')
        dropped = {head: count - required_heads.get(head, 0) for head, count in authored_heads.items() if count > required_heads.get(head, 0)}
        for head, missing in sorted(dropped.items()):
            restored = 0
            for signature, count in authored_required.items():
                if signature.partition('␟')[0] != head or restored >= missing:
                    continue
                take = min(count, missing - restored)
                required[signature] += take
                restored += take
                evidence.setdefault(signature, []).extend(authored_evidence.get(signature, [])[:take])
            report.advise(gate, 'adaptation_dropped_authored_command', f'adapted_steps:{head}', f"the authored procedure resolves command head={head!r} {authored_heads[head]} time(s) but the adapted steps resolve it {required_heads.get(head, 0)} time(s); the {missing} missing occurrence(s) stay obligations as the author wrote them — adaptation may rewrite a command's arguments, never remove the command. Sources: " + '; '.join((line for signature, lines in authored_evidence.items() if signature.partition('␟')[0] == head for line in lines)), head=head, authored=authored_heads[head], adapted=required_heads.get(head, 0), restored=restored)
    actual: Counter[str] = Counter()
    for ref in _ordered_apv_command_refs(list(steps), init):
        command = str(ref.get('command') or '')
        verdict = resolve(command)
        if verdict.get('kind') != 'hit':
            continue
        actual[_procedure_command_signature(vendor, command, verdict)] += 1
    for signature, needed in sorted(required.items()):
        head, _, object_id = signature.partition('␟')
        if object_id == _DESCRIPTIVE_FIRST_ARGUMENT:
            head_total = sum((count for key, count in actual.items() if key.partition('␟')[0] == head))
            others_required = sum((count for key, count in required.items() if key != signature and key.partition('␟')[0] == head))
            landed = head_total - others_required
            if landed >= needed:
                report.advise(gate, 'authored_argument_descriptive', f'author_steps:{head}:{_DESCRIPTIVE_FIRST_ARGUMENT}', f"the author wrote command head={head!r} followed by a descriptive condition instead of a CLI literal; the occurrence count was checked on the head only ({landed}/{needed}, after {others_required} same-head literal obligation(s)) and the object identity behind that condition was not mechanically compared. Sources: {'; '.join(evidence.get(signature, []))}", head=head, landed=landed, needed=needed, same_head_literal_obligations=others_required, sources=list(evidence.get(signature, [])))
                continue
            report.reject(gate, 'authored_command_occurrence_missing', f'author_steps:{head}:{_DESCRIPTIVE_FIRST_ARGUMENT}', f"the sealed author procedure contains {needed} occurrence(s) of build-valid command head={head!r} whose first argument is a descriptive condition (not a CLI literal), but the final APV action stream leaves only {landed} occurrence(s) of that head once the {others_required} same-head literal obligation(s) are served. Realize the described condition with concrete arguments and land every authored occurrence before observing its result. Sources: {'; '.join(evidence.get(signature, []))}")
            continue
        landed = actual.get(signature, 0)
        if landed >= needed:
            continue
        report.reject(gate, 'authored_command_occurrence_missing', f"author_steps:{head}:{object_id or '<no-first-arg>'}", f"the sealed author procedure contains {needed} occurrence(s) of build-valid command head={head!r} for first object={object_id!r}, but the final APV action stream contains only {landed}. A description saying the action happened is not execution evidence; land every authored occurrence before observing its result. Sources: {'; '.join(evidence.get(signature, []))}")

def _command_remainder_tokens(command: str, head: str) -> list[str]:
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    tokens = list(norm_command_tokens(command))
    head_tokens = list(norm_command_tokens(head))
    if tokens[:len(head_tokens)] != head_tokens:
        return []
    return [str(value).strip().casefold() for value in tokens[len(head_tokens):]]

def _gate_https_certificate_lifecycle(steps: Sequence[Any], init: str, report: _Report, *, device_build: str) -> None:
    gate = 'https_certificate_lifecycle'
    report.ran(gate)
    from cex_core.engine.case_compiler.excel_contract import parse_g_arguments
    from cex_core.engine.case_compiler.excel_capability_samples import certified_ssl_release_fixture
    from cex_core.engine.case_compiler.ssl_lifecycle_contract import SSLLifecycleContractError, load_ssl_lifecycle_contract
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import _SSL_ACTIVATE_FUNCTION, _SSL_IMPORT_FUNCTIONS, _ordered_apv_command_refs, _ssl_import_embeds_activation
    https_observations = [index for index, step in enumerate(steps) if isinstance(step, Mapping) and (not str(step.get('E') or '').strip().startswith('APV')) and ('https://' in str(step.get('G') or '').casefold())]
    if not https_observations:
        return
    try:
        lifecycle = load_ssl_lifecycle_contract(str(device_build or ''))
    except SSLLifecycleContractError as exc:
        report.reject(gate, 'https_lifecycle_contract_unavailable', 'engine_context.ssl_lifecycle_contract', f'this case carries a TLS client observation, but the engine-owned build-bound SSL lifecycle role map is unavailable or stale: {exc}. This is not repairable by changing case commands; refresh and certify the engine-only lifecycle evidence for the current build.')
        return
    required_virtual_heads = frozenset(lifecycle['required_virtual_heads'])
    ssl_host_create_head = str(lifecycle['ssl_host_create_head'])
    ssl_host_start_head = str(lifecycle['ssl_host_start_head'])
    ssl_host_cleanup_head = str(lifecycle['ssl_host_cleanup_head'])
    lifecycle_heads = tuple(sorted((*required_virtual_heads, ssl_host_create_head, ssl_host_start_head, ssl_host_cleanup_head), key=lambda value: (-len(value.split()), value)))
    refs: list[dict[str, Any]] = []
    for ref in _ordered_apv_command_refs(list(steps), init):
        command = str(ref.get('command') or '')
        head = next((candidate for candidate in lifecycle_heads if _command_remainder_tokens(command, candidate)), '')
        if not head:
            continue
        step_index = int(ref.get('step_index', -1))
        host = 'APV_0'
        if 0 <= step_index < len(steps) and isinstance(steps[step_index], Mapping):
            host = str(steps[step_index].get('E') or '').strip()
        refs.append({'command': command, 'head': head, 'args': _command_remainder_tokens(command, head), 'step_index': step_index, 'host': host})
    services = [ref for ref in refs if ref['head'] in required_virtual_heads and ref['args']]
    if not services:
        return
    key_functions = {name for (role, _variant), name in _SSL_IMPORT_FUNCTIONS.items() if role == 'key'}
    cert_functions = {name for (role, _variant), name in _SSL_IMPORT_FUNCTIONS.items() if role == 'cert'}

    def _method_vhost(step: Mapping[str, Any]) -> str:
        method = str(step.get('F') or '').strip()
        try:
            args, kwargs = parse_g_arguments(str(step.get('G') or ''), method)
        except Exception:
            return ''
        value = kwargs.get('vhost')
        if value is None and args:
            value = args[0]
        return str(value or '').strip().casefold()

    def _method_file(step: Mapping[str, Any], names: set[str]) -> str:
        method = str(step.get('F') or '').strip()
        try:
            args, kwargs = parse_g_arguments(str(step.get('G') or ''), method)
        except Exception:
            return ''
        for name in sorted(names):
            if kwargs.get(name) is not None:
                return str(kwargs[name]).strip()
        return str(args[1]).strip() if len(args) > 1 else ''
    for service in services:
        virtual_service = str(service['args'][0]).casefold()
        host = str(service['host'])
        service_index = int(service['step_index'])
        next_service_index = min((int(other['step_index']) for other in services if str(other['host']) == host and str(other['args'][0]).casefold() == virtual_service and (int(other['step_index']) > service_index)), default=len(steps))
        service_observations = [index for index in https_observations if service_index < index < next_service_index]
        if not service_observations:
            continue
        first_observation = min(service_observations)
        last_observation = max(service_observations)
        ssl_hosts = [ref for ref in refs if ref['head'] == ssl_host_create_head and ref['host'] == host and (len(ref['args']) >= 2) and (str(ref['args'][1]).casefold() == virtual_service) and (service_index < int(ref['step_index']) < first_observation)]
        if not ssl_hosts:
            report.reject(gate, 'https_certificate_setup_missing', f'steps:{host}:{virtual_service}', 'a build-valid HTTPS-list virtual service is exercised by an HTTPS observation, but no SSL_CERT_LOAD setup is bound to that exact virtual service after its creation and before the observation. Insert the engine-owned SSL_CERT_LOAD block in that lifecycle position and read its current fields from blocks_schema.json; do not hand-author or guess certificate-import commands.')
            continue
        ssl_host = max(ssl_hosts, key=lambda item: int(item['step_index']))
        vhost = str(ssl_host['args'][0]).casefold()
        ssl_host_index = int(ssl_host['step_index'])
        method_steps = [(index, step) for index, step in enumerate(steps) if ssl_host_index < index < first_observation and isinstance(step, Mapping) and (str(step.get('E') or '').strip() == host) and (_method_vhost(step) == vhost)]
        key_indices = [index for index, step in method_steps if str(step.get('F') or '').strip() in key_functions]
        cert_indices = [index for index, step in method_steps if str(step.get('F') or '').strip() in cert_functions]
        active_indices = [index for index, step in method_steps if str(step.get('F') or '').strip() == _SSL_ACTIVATE_FUNCTION]
        cert_methods = [str(step.get('F') or '').strip() for _index, step in method_steps if str(step.get('F') or '').strip() in cert_functions]
        try:
            embedded_activation = bool(cert_methods) and all((_ssl_import_embeds_activation(method) for method in cert_methods))
        except ValueError as exc:
            report.reject(gate, 'https_certificate_activation_contract_unavailable', f'steps:{host}:{virtual_service}', f'the engine cannot derive whether the selected certificate-import helper activates from the current framework source: {exc}. This is an engine projection fault, not a case command to guess around.')
            continue
        activation_closed = embedded_activation or bool(cert_indices and active_indices and (max(cert_indices) < max(active_indices)))
        ordered_setup = bool(key_indices and cert_indices and (min(key_indices) < max(cert_indices)) and activation_closed)
        if not ordered_setup:
            report.reject(gate, 'https_certificate_setup_incomplete', f'steps:{host}:{virtual_service}', 'the SSL host bound to the exercised HTTPS-list service does not carry a same-host, same-vhost key import -> certificate import -> activation sequence before the HTTPS observation. Activation may be embedded in the framework certificate-import helper or emitted as activeCert when the helper lacks it. Use SSL_CERT_LOAD so the engine derives that choice from the current mirror; prose and nearby unrelated imports are not setup evidence.')
            continue
        if embedded_activation and active_indices:
            report.reject(gate, 'https_certificate_redundant_activation', f'steps:{host}:{virtual_service}', 'the selected certificate-import helper already activates according to the current mirror, but the case invokes activeCert again. The second call can return an already-active prompt shape and turn its confirmation into a standalone invalid command. Re-lower SSL_CERT_LOAD; do not append another activation step.')
            continue
        activation_anchor = max(cert_indices) if embedded_activation else max(active_indices)
        start_ok = any((ref['head'] == ssl_host_start_head and ref['host'] == host and ref['args'] and (str(ref['args'][0]).casefold() == vhost) and (activation_anchor < int(ref['step_index']) < first_observation) for ref in refs))
        if not start_ok:
            report.reject(gate, 'https_certificate_start_missing', f'steps:{host}:{virtual_service}', 'the certificate is activated, but the same SSL host is not started before the HTTPS business observation. Re-lower SSL_CERT_LOAD so the engine inserts the build-bound lifecycle transition from its sealed role map; do not guess a product command in free text.')
            continue
        fixture_paths = certified_ssl_release_fixture()['resolved_paths']
        resolved_keys = [_method_file(step, {'keyfile', 'keyFile'}) for _index, step in method_steps if str(step.get('F') or '').strip() in key_functions]
        resolved_certs = [_method_file(step, {'certfile', 'certFile'}) for _index, step in method_steps if str(step.get('F') or '').strip() in cert_functions]
        if resolved_keys != list(fixture_paths['keys']) or resolved_certs != list(fixture_paths['certs']):
            report.reject(gate, 'https_certificate_material_unverified', f'steps:{host}:{virtual_service}', 'the key/certificate paths used by the HTTPS-list lifecycle are not the material signed by the current same-source release replay. Repository-looking paths and filenames selected by the model are not device facts. Submit SSL_CERT_LOAD with all material fields omitted so the engine binds the certified default projected in blocks_schema.json.')
            continue
        cleanup_ok = False
        for ref in refs:
            if not (ref['head'] == ssl_host_cleanup_head and ref['host'] == host and ref['args'] and (str(ref['args'][0]).casefold() == vhost) and (int(ref['step_index']) > last_observation)):
                continue
            index = int(ref['step_index'])
            if index + 1 >= len(steps) or not isinstance(steps[index + 1], Mapping):
                continue
            confirmation = steps[index + 1]
            if str(confirmation.get('E') or '').strip() == host and str(confirmation.get('F') or '').strip() == 'cmd_config' and (str(confirmation.get('G') or '').strip().upper() == 'YES'):
                cleanup_ok = True
                break
        if not cleanup_ok:
            report.reject(gate, 'https_certificate_teardown_missing', f'steps:{host}:{virtual_service}', 'the certified SSL host remains unpaired, or its teardown occurs before the last HTTPS observation. Keep SSL_CERT_LOAD as a standard-library block: the engine defers its certified object-scoped teardown pair until after the final signed business assertion and before trailing dependent-object teardown.')

def _base_claim_kinds(contract: Mapping[str, Any]) -> dict[str, str]:
    """基线契约每条期望的权威组（六源闭集名），供一致性叠加层对账。

    权威组从 `provenance_ir._CLAIM_ORIGIN` 派生，不在本文件另抄一份表。此前这里
    手抄了那张表的一个子集：缺 `config_derived` / `captured_relation` /
    `membership_derived` / `status_derived` 四种、多一个全仓不存在的
    `relation_derived`，而未命中的来源被 `.get(..., "")` 静默跳过。这是潜在漂移面，
    不是活缺陷：那四种来源目前到不了基线契约卡（`contract_entry` 把
    `assertion.source.kind` 限在 `{intent, spec, defect_spec, manual}`，唯一生产者
    也只产 `{spec, defect_spec, intent}`）；把手抄换成恒等式，防的是闭集将来放开时
    的静默少判——改写拦不住（`consistency_endorsement_claim_kind_upgrade` 看不到
    基线取值）、期望作用域的基数少数一条（`spec_endorsement_expectation_not_bound`）。
    两张表的一致性现在是恒等式，不是人工对齐；漂移由
    tests/ist_core/compile_engine/test_claim_origin_orthogonality.py 的对账守门当场翻红。
    """
    from cex_core.engine.case_compiler.provenance_ir import claim_authority_source
    out: dict[str, str] = {}
    for item in contract.get('expectations') or []:
        if not isinstance(item, Mapping):
            continue
        author = item.get('author_claim')
        defect = item.get('defect_spec_claim')
        assertion = item.get('assertion')
        if isinstance(author, Mapping):
            expectation_id = str(author.get('expectation_id') or '')
            kind = claim_authority_source('author')
        elif isinstance(defect, Mapping):
            expectation_id = str(defect.get('expectation_id') or '')
            kind = claim_authority_source('defect_spec')
        elif isinstance(assertion, Mapping):
            expectation_id = str(assertion.get('expectation_id') or '')
            source = assertion.get('source')
            kind = claim_authority_source(str((source or {}).get('kind') or '') if isinstance(source, Mapping) else '')
        else:
            continue
        if expectation_id and kind:
            out[expectation_id] = kind
    return out

def _gate_consistency_contract(body: Mapping[str, Any], contract: Mapping[str, Any], contract_sha256: str, consistency_contract: Mapping[str, Any] | None, consistency_contract_sha256: str, consistency_required: bool, report: _Report) -> None:
    gate = 'consistency_contract'
    report.ran(gate)
    binding = body.get('binding')
    declared = (binding or {}).get('consistency_contract_sha256') if isinstance(binding, Mapping) else None
    if not consistency_required:
        if declared is not None or consistency_contract is not None or consistency_contract_sha256:
            report.reject(gate, 'consistency_not_applicable_binding_present', 'binding.consistency_contract_sha256', 'the engine stamped consistency as not applicable; the mechanical body must carry null and cannot self-issue an overlay')
        return
    if not isinstance(consistency_contract, Mapping):
        report.reject(gate, 'consistency_contract_absent', 'binding.consistency_contract_sha256', 'the engine-required linked consistency contract is unavailable')
        return
    if str(declared or '') != consistency_contract_sha256 or not re.fullmatch('[0-9a-f]{64}', consistency_contract_sha256):
        report.reject(gate, 'consistency_contract_identity_drift', 'binding.consistency_contract_sha256', 'the mechanical binding does not equal the verified linked overlay SHA')
        return
    if not accepts_schema(consistency_contract.get('schema'), 'ist.consistency-contract') or consistency_contract.get('autoid') != body.get('autoid') or consistency_contract.get('base_contract_sha256') != contract_sha256:
        report.reject(gate, 'consistency_contract_base_drift', 'binding.consistency_contract_sha256', 'the linked overlay does not bind this case and frozen U1 contract')
        return
    expected_kinds = _base_claim_kinds(contract)
    bindings = [item for item in body.get('expectation_binding') or [] if isinstance(item, Mapping)]
    for index, item in enumerate(bindings):
        expectation_id = str(item.get('expectation_id') or '')
        expected_kind = expected_kinds.get(expectation_id)
        if expected_kind and str(item.get('claim_kind') or '') != expected_kind:
            report.reject(gate, 'consistency_endorsement_claim_kind_upgrade', f'expectation_binding[{index}].claim_kind', f'a linked Spec+Author endorsement is additive; it cannot rewrite the base contract claim kind {expected_kind}')
    endorsement = consistency_contract.get('spec_endorsement')
    scope = endorsement.get('scope') if isinstance(endorsement, Mapping) else None
    if isinstance(scope, Mapping) and scope.get('kind') == 'expectation':
        expectation_id = str(scope.get('expectation_id') or '')
        if list(expected_kinds).count(expectation_id) != SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY or sum((1 for item in bindings if str(item.get('expectation_id') or '') == expectation_id)) != SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY:
            report.reject(gate, 'spec_endorsement_expectation_not_bound', 'spec_endorsement.scope.expectation_id', 'expectation-scoped endorsement must name one unique base expectation and one unique mechanical assertion binding')

def _first_error(exc: Exception) -> str:
    errors = getattr(exc, 'errors', None)
    if not callable(errors):
        return f'{type(exc).__name__}: {exc}'
    items = list(errors())
    rendered = '; '.join((f"{'.'.join((str(part) for part in item.get('loc', ())))}: {item.get('msg', '')}" for item in items[:32]))
    if len(items) > 32:
        rendered += f'; (+{len(items) - 32} more validation errors)'
    return rendered or f'{type(exc).__name__}: {exc}'

def _init_g(init_commands: Sequence[str]) -> str:
    joined = '\n'.join((str(item) for item in init_commands)).strip()
    if joined:
        return joined
    from cex_core.engine.case_compiler.config import get_config
    return get_config().default_init_g()

def _gate_blocks_expansion(body: Mapping[str, Any], report: _Report) -> tuple[list[dict], list[dict]] | None:
    gate = 'blocks_expansion'
    report.ran(gate)
    from cex_core.engine.case_compiler.blocks import expand_blocks
    blocks = json.loads(json.dumps(body['blocks']))
    steps, provenance_steps, error = expand_blocks(blocks)
    if error or steps is None or provenance_steps is None:
        report.reject(gate, 'blocks_invalid', 'blocks', str(error))
        return None
    return (steps, provenance_steps)

def _gate_derived_assertion_expansion(steps: list[dict], provenance_steps: list[dict], report: _Report) -> tuple[list[dict], list[dict]] | None:
    from cex_core.engine.case_compiler.blocks import lower_derived_assertions
    expanded, expanded_provenance, error = lower_derived_assertions(steps, provenance_steps)
    if error or expanded is None or expanded_provenance is None:
        report.reject('blocks_expansion', 'blocks_invalid', 'blocks', str(error or 'derived assertion expansion returned no steps'))
        return None
    return (expanded, expanded_provenance)

def _expectation_ids_consuming_step(steps: Sequence[dict], provenance_steps: Sequence[dict], step_index: int) -> list[str]:
    if step_index < 0 or step_index >= len(steps):
        return []
    identities: set[str] = set()
    for index in range(step_index + 1, len(steps)):
        if str(steps[index].get('E') or '').strip() != _CHECK_POINT_OBJECT:
            break
        if index >= len(provenance_steps):
            continue
        expectation_id = str(provenance_steps[index].get('expectation_id') or '').strip()
        if expectation_id:
            identities.add(expectation_id)
    return sorted(identities)

def _gate_structural_lint(steps: Sequence[dict], provenance_steps: Sequence[dict], init: str, report: _Report, *, device_build: str, author_ip_literals: Sequence[str] | None=None) -> None:
    gate = 'structural_lint'
    report.ran(gate)
    report.ran('command_contract')
    bound_build = str(device_build or '').strip()
    if not bound_build:
        report.reject(gate, 'capability_build_unbound', 'engine_context.capability_build', 'the engine-owned capability build is missing; the submission rules refuse to fall back to the process-wide active command-tree generation')
        report.reject_named_by('command_contract', gate)
        return
    from cex_core.engine.ist_core.tools.device.structural_gate import lint_draft
    linted = list(steps)
    if init.strip():
        linted = [{'D': '初始化配置', 'E': 'APV_0', 'F': 'cmds_config', 'G': init}] + linted
    author_driver_hits: list[dict] = []
    result = lint_draft(linted, init='', final=True, device_build=bound_build, author_ip_literals=author_ip_literals, author_driver_hits=author_driver_hits)
    offset = 1 if init.strip() else 0
    if author_driver_hits:
        targets = sorted({str(item.get('target') or '') for item in author_driver_hits})
        report.advise(gate, 'author_sourced_driver_target', 'source_case_slice', 'The sealed Author case text names a query target that no test-driver on this bed has a declared path to. This is an execution-environment disclosure, not a case rejection: authoring continues, the limitation is reported with the delivery, and no device actual signs expected.', author_sourced_targets=[value for value in targets if value], author_sourced_driver_hits=[{**item, 'locus': _step_locus(int(item.get('step_index', -1)), offset)} for item in author_driver_hits])
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import COMMAND_NOT_IN_TREE_CODE, COMMAND_PARAMETER_CONTRACT_CODE
    command_codes = {COMMAND_NOT_IN_TREE_CODE, COMMAND_PARAMETER_CONTRACT_CODE}
    for violation in result.violations:
        finding_gate = 'command_contract' if violation.code in command_codes else gate
        expanded_index = violation.step_index - offset
        expectation_ids = _expectation_ids_consuming_step(steps, provenance_steps, expanded_index) if violation.code == COMMAND_NOT_IN_TREE_CODE else []
        report.reject(finding_gate, violation.code, _step_locus(violation.step_index, offset), violation.detail, expectation_ids=expectation_ids)
    for advisory in result.advisories:
        report.advise(gate, advisory.code, _step_locus(advisory.step_index, offset), advisory.detail)
    for disabled in result.disabled:
        report.advise(gate, f'gate_disabled:{disabled.code}', _step_locus(disabled.step_index, offset), disabled.detail)

def _step_locus(step_index: int, offset: int) -> str:
    if step_index < 0:
        return 'case'
    if offset and step_index == 0:
        return 'init_commands'
    return f'steps[{step_index - offset}]'

def _gate_unreachable_ips(autoid: str, steps: Sequence[dict], init: str, report: _Report, *, source_case_slice: Mapping[str, Any] | None=None, source_case_slice_sha256: str='') -> None:
    gate = 'unreachable_ips'
    report.ran(gate)
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import _gate_unreachable_ips as unreachable, _unreachable_ip_admission
    admission = _unreachable_ip_admission(autoid, list(steps), init=init, source_case_slice=dict(source_case_slice) if isinstance(source_case_slice, Mapping) else None, source_case_slice_sha256=source_case_slice_sha256)
    message = unreachable(autoid, list(steps), init=init, source_case_slice=dict(source_case_slice) if isinstance(source_case_slice, Mapping) else None, source_case_slice_sha256=source_case_slice_sha256)
    if message:
        report.reject(gate, 'environment_unreachable_ip', 'steps', message)
    author_values = list(admission.get('author_unreachable_values') or [])
    if author_values:
        report.advise(gate, 'author_sourced_unreachable_setup', 'source_case_slice', 'The sealed Author case text contains environment-unreachable setup value(s). This is an execution-environment disclosure, not a case rejection: authoring continues and setup binding follows the contract value_grounding channel; no device actual signs expected.', author_unreachable_values=author_values, compiled_unreachable_values=list(admission.get('compiled_unreachable_values') or []))

def _negative_probe_destinations(command: str) -> list[str]:
    import ipaddress as _ip
    import shlex as _shlex
    from cex_core.engine.ist_core.tools.device.structural_gate import _extract_query_destinations
    out = list(_extract_query_destinations(command))
    try:
        tokens = _shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        candidate = token.strip().strip('[]')
        if candidate.count(':') == 1 and '.' in candidate:
            host, port = candidate.rsplit(':', 1)
            if port.isdecimal():
                candidate = host
        try:
            _ip.ip_address(candidate.split('%')[0])
        except ValueError:
            continue
        if candidate not in out:
            out.append(candidate)
    return out

def _gate_negative_probe_path(blocks: Sequence[dict], report: _Report) -> None:
    gate = 'negative_probe_path'
    report.ran(gate)
    negatives = [(index, block) for index, block in enumerate(blocks) if isinstance(block, Mapping) and str(block.get('kind') or '').strip().upper() == 'OBSERVE_EXIT' and (str(block.get('expect') or '').strip().lower() == 'failure')]
    if not negatives:
        return
    from cex_core.engine.ist_core.tools._shared.env_facts import require_env_facts
    facts = require_env_facts()
    for index, block in negatives:
        command = str(block.get('cmd') or '')
        host = str(block.get('host') or '')
        destinations = _negative_probe_destinations(command)
        if not destinations:
            report.reject(gate, 'negative_probe_target_not_ip_literal', f'blocks[{index}]', 'expect=failure asserts that the target did not answer, so the probe target must be an IP literal; a host name would let a name-resolution failure satisfy the assertion without the device being involved')
            continue
        for dest in destinations:
            verdict = facts.executor_path_verdict(host, dest)
            if verdict is None:
                continue
            report.reject(gate, 'negative_probe_path_undeclared', f'blocks[{index}]', f"expect=failure from {host!r} to {dest} cannot be attributed to the device: the testbed topology declares no path from this executor to that address, so a transport failure could come from the executor's own routing. Probe from an executor with a declared path (reachable drivers: {verdict.get('reachable_drivers') or []}).")

def _author_ip_literals_for_submission(autoid: str, steps: Sequence[dict], init: str, *, source_case_slice: Mapping[str, Any] | None, source_case_slice_sha256: str) -> list[str]:
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import _unreachable_ip_admission
    admission = _unreachable_ip_admission(autoid, list(steps), init=init, source_case_slice=dict(source_case_slice) if isinstance(source_case_slice, Mapping) else None, source_case_slice_sha256=source_case_slice_sha256)
    return list(admission.get('author_ip_literals') or [])

def _gate_trigger_reachability(autoid: str, steps: Sequence[dict], init: str, blocks: Sequence[dict], report: _Report, *, author_ip_literals: Sequence[str] | None=None) -> None:
    gate = 'trigger_reachability'
    report.ran(gate)
    from cex_core.engine.ist_core.tools._shared.env_facts import require_env_facts
    require_env_facts()
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import _trigger_reachability_findings
    findings = _trigger_reachability_findings(autoid, list(steps), init=init, blocks=list(blocks), author_ip_literals=author_ip_literals)
    message = findings.get('message')
    if message:
        report.reject(gate, 'trigger_reachability_invalid', 'steps', message)
    author_targets = list(findings.get('author_sourced_targets') or [])
    if author_targets:
        report.advise(gate, 'author_sourced_trigger_target', 'source_case_slice', 'The sealed Author case text names a listener/trigger target that sits in an APV interface segment no trigger host on this bed can reach, or that is not a registered listener/backend of this bed. This is an execution-environment disclosure, not a case rejection: authoring continues, the limitation is reported with the delivery, and no device actual signs expected.', author_sourced_targets=author_targets, author_blind_hits=list(findings.get('author_blind_hits') or []), author_bad_targets=list(findings.get('author_bad_targets') or []))

def _interaction_block_expectation_ids(block: Mapping[str, Any], kind: str) -> list[str]:
    if kind == 'OBSERVE_ASSERT':
        return sorted({str(item.get('expectation_id') or '') for item in block.get('asserts') or [] if isinstance(item, Mapping) and str(item.get('expectation_id') or '')})
    single = str(block.get('expectation_id') or '')
    return [single] if single else []

def _block_kind_label(block: Any) -> str:
    if not isinstance(block, Mapping):
        return 'no block'
    return str(block.get('kind') or '').strip().upper() or 'no block'

def _is_config_establishing_block(block: Any, dut_hosts: Sequence[str]) -> bool:
    if not isinstance(block, Mapping):
        return False
    kind = str(block.get('kind') or '').strip().upper()
    if kind == 'CONFIG':
        return True
    if kind != 'STEP':
        return False
    return str(block.get('E') or '').strip() in tuple(dut_hosts) and str(block.get('F') or '').strip() in _CONFIG_STEP_FUNCTIONS

def _gate_answerer_statement(body: Mapping[str, Any], report: _Report) -> None:
    gate = 'answerer_statement'
    report.ran(gate)
    from cex_core.engine.case_compiler.blocks import _ANSWERER_KINDS, _DUT_HOSTS, _answerer_shape_error
    blocks = body.get('blocks')
    if not isinstance(blocks, list):
        return
    from cex_core.engine.ist_core.tools._shared.env_facts import require_env_facts
    facts = require_env_facts()
    topology_names = {str(dev.get('name') or '').strip().lower() for dev in facts.devices if str(dev.get('name') or '').strip()}
    for index, block in enumerate(blocks):
        if not isinstance(block, Mapping):
            continue
        kind = str(block.get('kind') or '').strip().upper()
        if kind not in ('OBSERVE_ASSERT', 'OBSERVE_EXIT'):
            continue
        host = str(block.get('host') or '').strip()
        if host in _DUT_HOSTS:
            continue
        locus = f'blocks[{index}].answerer'
        expectation_ids = _interaction_block_expectation_ids(block, kind)
        answerer = block.get('answerer')
        if answerer is None:
            report.reject(gate, 'answerer_statement_missing', locus, f'this observation runs on host {host!r}, which is outside the two devices under test, so it drives traffic at a peer instead of reading device state — and the block names no answerer. A request sent with nothing behind it times out on device and burns a device round (real open-chain cases failed four times this way). Declare who answers: answerer {{kind: "device"|"fixture", ref: <blocks[] index of the block that establishes the answerer>}} or {{kind: "bed_service", ref: <device name in the bed topology>}}. When no source says who answers, write {{kind: "undetermined", note: <one user-facing Chinese line>}} and the submit boundary routes a typed user-decision claim instead of rejecting or sealing.', expectation_ids=expectation_ids)
            continue
        if _answerer_shape_error(index, kind, block) is not None:
            report.reject_named_by(gate, 'blocks_expansion')
            continue
        a_kind = str(answerer.get('kind') or '').strip()
        if a_kind not in _ANSWERER_KINDS:
            report.reject_named_by(gate, 'blocks_expansion')
            continue
        ref = answerer.get('ref')
        if a_kind == 'undetermined':
            report.reject(gate, 'answerer_undetermined_unrouted', locus, 'answerer.kind=undetermined is routed by submit_mechanical_case into a typed answerer_undetermined user-decision claim before the submission rules run; a sealed mechanical case can never carry an undetermined answerer. Route it through the submit boundary instead of sealing.', expectation_ids=expectation_ids)
        elif a_kind == 'device':
            target = blocks[ref] if 0 <= ref < len(blocks) else None
            if not _is_config_establishing_block(target, _DUT_HOSTS):
                report.reject(gate, 'answerer_ref_unresolved', locus, f'answerer.ref={ref} must be the blocks[] index of the block that establishes the answering configuration on a device under test (a CONFIG combinator, or an accounted generic STEP writing device configuration); it resolves to {_block_kind_label(target)}.', expectation_ids=expectation_ids)
        elif a_kind == 'fixture':
            if not 0 <= ref < len(blocks) or not isinstance(blocks[ref], Mapping):
                report.reject(gate, 'answerer_ref_unresolved', locus, f'answerer.ref={ref} must be the blocks[] index of the block that establishes the in-case fixture answering this observation; no such block exists in this submission.', expectation_ids=expectation_ids)
        else:
            name = str(ref or '').strip().lower()
            if name not in topology_names:
                report.reject(gate, 'answerer_ref_unresolved', locus, f'answerer.ref {ref!r} is not a device name in the bed topology; kind=bed_service names a service the testbed itself provides, so the name must come from the topology fact source.', expectation_ids=expectation_ids)

def _gate_paired_teardown(steps: Sequence[dict], init: str, report: _Report, *, device_build: str) -> None:
    gate = 'paired_teardown'
    report.ran(gate)
    from cex_core.engine.case_compiler.tau_coverage import TauAtlasUnavailableError, check_tau_coverage, inverse_line
    try:
        result = check_tau_coverage(list(steps), init, device_build=str(device_build or ''))
    except TauAtlasUnavailableError as exc:
        report.reject(gate, 'tau_atlas_unavailable', 'engine_context.device_build', f'the engine-owned build-bound teardown atlas is unavailable: {exc}. This is an engine projection fault, not a command to weaken or rewrite the case; finish with that stable error code instead of retrying.')
        return
    except Exception as exc:
        report.reject(gate, 'paired_teardown_uncomputable', 'case', f'the deterministic teardown coverage rule could not produce a verdict ({type(exc).__name__}); sealing is blocked as an engine fault')
        return
    if result.residual_config:
        report.advise(gate, 'residual_config_disclosed', 'blocks', f'{len(result.residual_config)} configuration write(s) are classified as residual-only by the bound atlas; emit will persist the disclosure')
    if result.ok:
        return
    missing_lines = [f"- {item.get('cmd')!r}: {inverse_line(item)}" for item in result.missing]
    report.reject(gate, 'missing_teardown', 'blocks', 'the build-bound teardown atlas proves that this draft creates configuration outside framework C1 cleanup but carries no matching object-scoped restore after its assertions:\n' + '\n'.join(missing_lines) + '\nAdd the atlas-backed object-scoped inverse steps in reverse order after the assertions. Where the atlas exposes only a module-wide reset or no inverse, do not guess or use a wider clear: choose an equivalent construction with a representable object-scoped teardown, or report the mechanical-language gap explicitly.')

def _gate_provenance_receipts(autoid: str, steps: Sequence[dict], provenance_steps: Sequence[dict], report: _Report, outputs_root: Path | None) -> Any | None:
    gate = 'provenance_receipts'
    report.ran(gate)
    from cex_core.engine.case_compiler.provenance_ir import CaseProvenance, backfill_efg, check_runtime_consistency, check_source_locators, compile_expect_authority, known_provenance_facts
    case = CaseProvenance.from_dict({'autoid': autoid, 'steps': json.loads(json.dumps(list(provenance_steps)))})
    if not backfill_efg(case, list(steps)):
        report.reject(gate, 'provenance_step_count_mismatch', 'provenance', f'provenance carries {len(case.steps)} entries for {len(steps)} expanded steps; the expansion pairs them positionally')
        return None
    problems = check_source_locators(case, outputs_root=outputs_root) + check_runtime_consistency(case) + compile_expect_authority(case)
    guidance = ''
    if problems:
        root = Path(outputs_root) if outputs_root is not None else Path('workspace/outputs')
        guidance = '\n'.join(known_provenance_facts(autoid, outputs_root=root))
    for index, problem in enumerate(problems):
        detail = problem + ('\n' + guidance if index == 0 and guidance else '')
        report.reject(gate, 'provenance_source_unresolved', 'provenance', detail)
    return None if problems else case

def _contract_claim_maps(contract: Mapping[str, Any], report: _Report) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]] | None:
    gate = 'expectation_bijection'
    from cex_core.engine.case_compiler.contract_entry import normalize_contract
    from cex_core.engine.ist_core.compile_engine.authority_reconcile import author_fixture_policies_from_contract
    try:
        normalized = normalize_contract(dict(contract), str(contract.get('autoid') or ''))
        fixture_policies = author_fixture_policies_from_contract(normalized)
    except Exception as exc:
        report.reject(gate, 'contract_unreadable', 'contract', f'{type(exc).__name__}: {exc}')
        return None
    maps: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] = ({}, {}, {})
    fields = ('assertion', 'author_claim', 'defect_spec_claim')
    for index, item in enumerate(normalized.get('expectations') or []):
        for bucket, field in zip(maps, fields):
            claim = item.get(field) if isinstance(item, Mapping) else None
            if not isinstance(claim, Mapping):
                continue
            expectation_id = str(claim.get('expectation_id') or '').strip()
            if not expectation_id:
                report.reject(gate, 'contract_identity_incomplete', f'contract.expectations[{index}].{field}', 'the contract card minted no expectation_id for this entry')
                continue
            if any((expectation_id in other for other in maps)):
                report.reject(gate, 'contract_identity_duplicated', f'contract.expectations[{index}].{field}', f'expectation_id {expectation_id!r} occurs more than once')
                continue
            bucket[expectation_id] = dict(claim)
    return None if report.rejected(gate) else (*maps, fixture_policies)

def _product_assertions(case: Any) -> list[Any]:
    from cex_core.engine.ist_core.compile_engine.authority_reconcile import product_assertion_steps
    return product_assertion_steps(case.steps, mutation_receipt=None)

def _gate_expectation_bijection(body: Mapping[str, Any], contract: Mapping[str, Any], contract_sha256: str, final_steps: Sequence[Any], all_steps: Sequence[Any], report: _Report) -> None:
    gate = 'expectation_bijection'
    report.ran(gate)
    autoid = str(body.get('autoid') or '')
    declared = str((body.get('binding') or {}).get('contract_sha256') or '')
    if declared != contract_sha256:
        report.reject(gate, 'contract_identity_drift', 'binding.contract_sha256', f'declares {declared}, the frozen contract card hashes to {contract_sha256}')
        return
    if str(contract.get('autoid') or '') != autoid:
        report.reject(gate, 'contract_autoid_mismatch', 'binding.contract_sha256', f"contract card is for autoid {contract.get('autoid')!r}, this case is {autoid!r}")
        return
    maps = _contract_claim_maps(contract, report)
    if maps is None:
        return
    expectations, author_claims, defect_claims, fixture_policies = maps
    from cex_core.engine.ist_core.compile_engine.authority_reconcile import check_expectation_assertion_bijection
    error = check_expectation_assertion_bijection(autoid=autoid, final_steps=list(final_steps), all_steps=list(all_steps), stamped_expectations=expectations, stamped_author_claims=author_claims, stamped_defect_spec_claims=defect_claims, stamped_author_fixture_policies=fixture_policies)
    if error:
        report.reject(gate, 'expectation_bijection_failed', 'blocks', error)

def _fixture_backref_error(body: Mapping[str, Any], *, block_index: int, assert_index: int | None, policy: Mapping[str, Any]) -> str:
    required_policy = {'value_prefix', 'domain_suffix', 'allowed_kinds', 'expected_binding_rule', 'disclosure_required'}
    if set(policy) != required_policy or not str(policy.get('value_prefix') or '') or (not str(policy.get('domain_suffix') or '')) or (set(policy.get('allowed_kinds') or []) != {'domain_name', 'text_value'}) or (policy.get('expected_binding_rule') != 'config.fixture-literal-backref') or (policy.get('disclosure_required') is not True):
        return 'the frozen fixture policy is incomplete or outside its closed contract'
    blocks = body.get('blocks') or []
    if not isinstance(block_index, int) or isinstance(block_index, bool) or block_index < 0 or (block_index >= len(blocks)) or (not isinstance(assert_index, int)) or isinstance(assert_index, bool) or (not isinstance(blocks[block_index], Mapping)) or (str(blocks[block_index].get('kind') or '').strip().upper() != 'OBSERVE_ASSERT'):
        return 'a fixture assertion must use an OBSERVE_ASSERT assertion slot'
    assertions = blocks[block_index].get('asserts')
    if not isinstance(assertions, list) or assert_index < 0 or assert_index >= len(assertions) or (not isinstance(assertions[assert_index], Mapping)):
        return 'the fixture assertion slot is unavailable'
    assertion = assertions[assert_index]
    ref = str(assertion.get('ref') or '')
    binding = assertion.get('binding_input')
    if not ref.startswith('config_derived:') or not isinstance(binding, Mapping) or set(binding) != {'rule_id', 'source_input'} or (binding.get('rule_id') != policy.get('expected_binding_rule')) or (not isinstance(binding.get('source_input'), Mapping)):
        return 'fixture expected must use config.fixture-literal-backref; an LLM or free-text expected source cannot sign the value'
    source_input = binding['source_input']
    required_input = {'operator', 'value', 'fixture_kind', 'config_block_index', 'config_command_index'}
    if set(source_input) != required_input:
        return 'fixture back-reference source_input fields are not closed'
    operator = str(source_input.get('operator') or '')
    value = source_input.get('value')
    fixture_kind = str(source_input.get('fixture_kind') or '')
    config_block_index = source_input.get('config_block_index')
    config_command_index = source_input.get('config_command_index')
    if operator != str(assertion.get('op') or '') or not isinstance(value, str) or value != str(assertion.get('pattern') or '') or (fixture_kind not in set(policy.get('allowed_kinds') or [])) or (not isinstance(config_block_index, int)) or isinstance(config_block_index, bool) or (config_block_index < 0) or (config_block_index >= block_index) or (not isinstance(config_command_index, int)) or isinstance(config_command_index, bool) or (config_command_index < 0):
        return 'fixture expected tuple does not identify an earlier configuration literal'
    prefix = str(policy['value_prefix'])
    suffix = str(policy['domain_suffix'])
    if fixture_kind == 'domain_name':
        safe_name = bool(value.startswith(prefix) and value.endswith(suffix) and re.fullmatch('[A-Za-z0-9.-]+', value))
    else:
        safe_name = bool(value.startswith(prefix) and re.fullmatch('[A-Za-z0-9._-]+', value))
    if not safe_name:
        return 'fixture value violates the isolated autotest naming policy'
    config_block = blocks[config_block_index]
    commands = config_block.get('cmds') if isinstance(config_block, Mapping) else None
    if not isinstance(config_block, Mapping) or str(config_block.get('kind') or '').strip().upper() != 'CONFIG' or (not isinstance(commands, list)) or (config_command_index >= len(commands)) or (not isinstance(commands[config_command_index], str)):
        return 'fixture back-reference does not resolve to a CONFIG command'
    command = commands[config_command_index]
    literal = re.compile('(?<![A-Za-z0-9_.-])' + re.escape(value) + '(?![A-Za-z0-9_.-])')
    if literal.search(command) is None:
        return 'fixture expected value is not a literal in the referenced CONFIG command'
    return ''
from cex_core.engine.case_compiler.criterion_carriers import CRITERION_TYPE_ALLOWED_SLOTS

def criterion_satisfiability_gaps(contract: Mapping[str, Any]) -> list[dict]:
    gaps: list[dict] = []
    for index, item in enumerate(contract.get('expectations') or []):
        if not isinstance(item, Mapping):
            continue
        claim = item.get('normalized_claim')
        if not isinstance(claim, Mapping):
            continue
        criterion_type = str(claim.get('criterion_type') or '')
        if str(claim.get('status') or '') != 'matched' or criterion_type not in CRITERION_TYPE_ALLOWED_SLOTS:
            gaps.append({'expectation_id': str(claim.get('expectation_id') or ''), 'criterion_type': criterion_type, 'claim_status': str(claim.get('status') or ''), 'check_scope': 'claim_status_and_registered_type', 'locus': f'contract.expectations[{index}].normalized_claim'})
    return gaps

def _gate_criterion_type_binding(body: Mapping[str, Any], contract: Mapping[str, Any], report: _Report, *, device_build: str='') -> None:
    gate = 'criterion_type_binding'
    report.ran(gate)
    normalized: dict[str, dict[str, Any]] = {}
    claim_texts: dict[str, str] = {}
    for index, item in enumerate(contract.get('expectations') or []):
        if not isinstance(item, Mapping):
            continue
        claim = item.get('normalized_claim')
        if not isinstance(claim, Mapping):
            continue
        expectation_id = str(claim.get('expectation_id') or '')
        if not expectation_id or expectation_id in normalized:
            report.reject(gate, 'criterion_claim_identity_invalid', f'contract.expectations[{index}].normalized_claim', 'normalized criterion claim has an empty or duplicate expectation_id')
            continue
        normalized[expectation_id] = dict(claim)
        author_claim = item.get('author_claim')
        claim_texts[expectation_id] = str(claim.get('original_text') or (author_claim.get('source_text') if isinstance(author_claim, Mapping) else '') or item.get('text') or '')
    if not normalized:
        return
    bindings: dict[str, list[tuple[str, str]]] = {}
    binding_loci: dict[str, list[tuple[int, int | None]]] = {}
    declared_state_change: dict[str, list[tuple[int, str]]] = {}
    reversal_index = dict(_teardown_reversal_index(str(device_build or '')))
    blocks = body.get('blocks') or []
    for index, binding in enumerate(body.get('expectation_binding') or []):
        if not isinstance(binding, Mapping):
            continue
        expectation_id = str(binding.get('expectation_id') or '')
        block_index = binding.get('block_index')
        if expectation_id not in normalized or not isinstance(block_index, int) or isinstance(block_index, bool) or (block_index < 0) or (block_index >= len(blocks)) or (not isinstance(blocks[block_index], Mapping)):
            continue
        block = blocks[block_index]
        kind = str(block.get('kind') or '').strip().upper()
        operator = ''
        if kind == 'OBSERVE_ASSERT':
            assert_index = binding.get('assert_index')
            assertions = block.get('asserts')
            if isinstance(assert_index, int) and (not isinstance(assert_index, bool)) and isinstance(assertions, list) and (0 <= assert_index < len(assertions)) and isinstance(assertions[assert_index], Mapping):
                operator = str(assertions[assert_index].get('op') or '').strip()
        elif kind == 'STEP':
            operator = str(block.get('F') or '').strip()
        bindings.setdefault(expectation_id, []).append((kind, operator))
        binding_loci.setdefault(expectation_id, []).append((block_index, binding.get('assert_index') if isinstance(binding.get('assert_index'), int) and (not isinstance(binding.get('assert_index'), bool)) else None))
        _declared_step = binding.get('state_change_step')
        _declared_text = str(binding.get('binding_disclosure') or '').strip()
        if isinstance(_declared_step, int) and (not isinstance(_declared_step, bool)) and (_declared_step >= 0) and _declared_text:
            declared_state_change.setdefault(expectation_id, []).append((_declared_step, _declared_text))
    allowed = CRITERION_TYPE_ALLOWED_SLOTS
    for expectation_id, claim in normalized.items():
        status = str(claim.get('status') or '')
        criterion_type = str(claim.get('criterion_type') or '')
        if status != 'matched' or criterion_type not in allowed:
            report.reject(gate, 'criterion_type_unresolved', f'expectation_id={expectation_id}', 'the frozen contract has no identity-bound matched criterion type; return to the batch author-confirmation stage')
            continue
        slots = bindings.get(expectation_id) or []
        if not slots:
            report.reject(gate, 'criterion_binding_missing', f'expectation_id={expectation_id}', 'no mechanical assertion slot redeems this normalized criterion')
            continue
        invalid = [slot for slot in slots if slot not in allowed[criterion_type]]
        if invalid:
            permitted = ', '.join((f"({block}, {operator or 'no operator'})" for block, operator in sorted(allowed[criterion_type])))
            report.reject(gate, 'criterion_lowering_mismatch', f'expectation_id={expectation_id}', f'criterion_type={criterion_type} cannot lower through {invalid!r}. It may only lower through: {permitted}. Rebind this expectation to one of those slots, or, if none can express the authored assertion, report an engine-side criterion gap instead of forcing the nearest operator.')
        elif criterion_type == 'status_value':
            for block_index, assert_index in binding_loci.get(expectation_id) or []:
                literal_error = _status_value_claim_literalization_error(body, block_index=block_index, assert_index=assert_index, claim_text=claim_texts.get(expectation_id, ''))
                if literal_error:
                    report.reject(gate, 'criterion_status_claim_literalized', f'expectation_id={expectation_id}', literal_error)
                    continue
                error = _status_value_target_error(body, block_index=block_index, assert_index=assert_index)
                if not error:
                    continue
                declared = declared_state_change.get(expectation_id) or []
                if declared and (not reversal_index):
                    declared = []
                if declared:
                    fake_pass = _declared_state_change_fake_pass_error(body, block_index=block_index, assert_index=assert_index, declared_steps=[step for step, _ in declared], reversal_index=reversal_index)
                    if fake_pass:
                        report.reject(gate, 'criterion_state_change_step_self_satisfying', f'expectation_id={expectation_id}', fake_pass)
                        continue
                    invalid = _declared_state_change_step_error(body, observe_block_index=block_index, declared_steps=[step for step, _ in declared])
                    if invalid:
                        report.reject(gate, 'criterion_state_change_step_invalid', f'expectation_id={expectation_id}', invalid)
                        continue
                    for step, disclosure in declared:
                        report.advise(gate, 'criterion_binding_declared', f'expectation_id={expectation_id}', disclosure, expectation_id=expectation_id, state_change_step=int(step), disclosure=disclosure)
                    continue
                report.reject(gate, 'criterion_status_target_unbound', f'expectation_id={expectation_id}', error)
        fixture_policy = claim.get('fixture_policy')
        if isinstance(fixture_policy, Mapping):
            for block_index, assert_index in binding_loci.get(expectation_id) or []:
                error = _fixture_backref_error(body, block_index=block_index, assert_index=assert_index, policy=fixture_policy)
                if error:
                    report.reject(gate, 'fixture_expected_not_config_backref', f'expectation_id={expectation_id}', error)

def _status_value_claim_literalization_error(body: Mapping[str, Any], *, block_index: int, assert_index: int | None, claim_text: str) -> str:
    blocks = body.get('blocks') or []
    if not isinstance(blocks, list) or not isinstance(block_index, int) or isinstance(block_index, bool) or (not 0 <= block_index < len(blocks)) or (not isinstance(blocks[block_index], Mapping)) or (str(blocks[block_index].get('kind') or '').strip().upper() != 'OBSERVE_ASSERT') or (not isinstance(assert_index, int)) or isinstance(assert_index, bool):
        return ''
    assertions = blocks[block_index].get('asserts')
    if not isinstance(assertions, list) or not 0 <= assert_index < len(assertions) or (not isinstance(assertions[assert_index], Mapping)):
        return ''
    assertion = assertions[assert_index]
    if not str(assertion.get('ref') or '').strip().startswith('intent:'):
        return ''
    claim = str(claim_text or '').strip()
    pattern = str(assertion.get('pattern') or '').strip()
    if not claim or not pattern:
        return ''
    candidate = re.sub('^\\(\\?[aiLmsux-]+\\)', '', pattern)
    for prefix, suffix in (('^', '$'), ('\\A', '\\Z')):
        if candidate.startswith(prefix) and candidate.endswith(suffix):
            candidate = candidate[len(prefix):len(candidate) - len(suffix)]
            break
    if candidate.endswith('\\r?'):
        candidate = candidate[:-3]
    if candidate not in {claim, re.escape(claim)}:
        return ''
    return f"status-value assertion at blocks[{block_index}].asserts[{assert_index}] uses the Author's semantic claim sentence itself as a device-output pattern. An intent claim signs the expected state or polarity, not the language or exact bytes emitted by this device build. Observe a structural consequence, use the engine-derived exit-status form, or cite an independent identity-bound source that explicitly declares the output bytes."

def _status_value_target_error(body: Mapping[str, Any], *, block_index: int, assert_index: int | None) -> str:
    blocks = body.get('blocks') or []
    if not isinstance(blocks, list) or not isinstance(block_index, int) or isinstance(block_index, bool) or (not 0 <= block_index < len(blocks)):
        return 'status-value binding does not identify one block'
    block = blocks[block_index]
    if not isinstance(block, Mapping) or str(block.get('kind') or '').strip().upper() != 'OBSERVE_ASSERT':
        return ''
    if not isinstance(assert_index, int) or isinstance(assert_index, bool):
        return 'status-value OBSERVE_ASSERT binding does not identify one assertion slot'
    assertions = block.get('asserts')
    if not isinstance(assertions, list) or not 0 <= assert_index < len(assertions) or (not isinstance(assertions[assert_index], Mapping)):
        return 'status-value binding points outside the assertion array'
    command = str(block.get('cmd') or '').strip()
    from cex_core.engine.case_compiler.observe_ops import observe_kind
    if not observe_kind(command):
        return ''
    assertion = assertions[assert_index]
    operator = str(assertion.get('op') or '').strip()
    pattern = str(assertion.get('pattern') or '')

    def _matches(text: str) -> bool:
        if not text:
            return False
        if operator == 'abs_found':
            return pattern in text
        try:
            return re.search(pattern, text, re.MULTILINE) is not None
        except re.error:
            return False
    nearest_config_index = -1
    nearest_commands: list[str] = []
    for index in range(block_index - 1, -1, -1):
        candidate = blocks[index]
        if isinstance(candidate, Mapping) and str(candidate.get('kind') or '').strip().upper() == 'CONFIG':
            nearest_config_index = index
            commands = candidate.get('cmds')
            nearest_commands = [str(value) for value in commands if isinstance(value, str)] if isinstance(commands, list) else []
            break
    if nearest_config_index < 0 or any((_matches(value) for value in nearest_commands)):
        return ''
    return f"status-value assertion at blocks[{block_index}].asserts[{assert_index}] uses a pattern that is not grounded by the nearest causal CONFIG block[{nearest_config_index}]. The signed claim text describes state semantics, not device-output bytes. It can therefore pass while that latest state change has a different outcome. Bind the assertion to the value changed by that CONFIG step, observe the action response directly, or use an independently signed derived expectation; do not prove progress by re-checking an older baseline. When the asserted value is a runtime outcome that no configuration command line can carry, the declared path is the fourth repair and not an engine gap: on this expectation's expectation_binding entry set state_change_step to {nearest_config_index} and write binding_disclosure, one user-facing Chinese sentence saying why that command line cannot carry the value and how this step causes the change. The engine then records that binding instead of refusing it, so resubmitting the same shape without the declaration is not the only move left."

def _declared_causal_block_command_lines(block: Mapping[str, Any]) -> list[str]:
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import APV_CONFIG_METHODS, is_apv_command_step
    if str(block.get('kind') or '').strip().upper() == 'CONFIG':
        commands = block.get('cmds')
        return [value.strip() for value in commands if isinstance(value, str) and value.strip()] if isinstance(commands, list) else []
    if is_apv_command_step(dict(block), methods=APV_CONFIG_METHODS):
        return [line.strip() for line in str(block.get('G') or '').splitlines() if line.strip()]
    return []

def _declared_state_change_step_error(body: Mapping[str, Any], *, observe_block_index: int, declared_steps: Sequence[int]) -> str:
    blocks = body.get('blocks') or []
    if not isinstance(blocks, list):
        return 'blocks is not an array, so a declared causal step cannot be located'
    for step in declared_steps:
        if not 0 <= step < len(blocks) or not isinstance(blocks[step], Mapping):
            return f"state_change_step {step} does not name a block in this case's procedure ({len(blocks)} blocks)"
        if not _declared_causal_block_command_lines(blocks[step]):
            return f'state_change_step {step} names a block that carries no product configuration command line; only a step that reaches the device under test can be declared as the cause of a state change'
        if step >= observe_block_index:
            return f'state_change_step {step} runs at or after the observation at blocks[{observe_block_index}]; a step that has not run yet cannot have caused the state this assertion reads'
    return ''

def _declared_state_change_fake_pass_error(body: Mapping[str, Any], *, block_index: int, assert_index: int | None, declared_steps: Sequence[int], reversal_index: Mapping[str, tuple[str, ...]]) -> str:
    blocks = body.get('blocks') or []
    if not isinstance(blocks, list) or not isinstance(block_index, int) or isinstance(block_index, bool) or (not 0 <= block_index < len(blocks)) or (not isinstance(blocks[block_index], Mapping)) or (not isinstance(assert_index, int)) or isinstance(assert_index, bool):
        return ''
    assertions = blocks[block_index].get('asserts')
    if not isinstance(assertions, list) or not 0 <= assert_index < len(assertions) or (not isinstance(assertions[assert_index], Mapping)):
        return ''
    assertion = assertions[assert_index]
    if str(assertion.get('op') or '').strip() != 'not_found':
        return ''
    pattern = str(assertion.get('pattern') or '')
    if not pattern:
        return ''

    def _matches(text: str) -> bool:
        try:
            return re.search(pattern, text, re.MULTILINE) is not None
        except re.error:
            return False
    for step in declared_steps:
        if not 0 <= step < len(blocks) or not isinstance(blocks[step], Mapping):
            continue
        for line in _declared_causal_block_command_lines(blocks[step]):
            undone = _reversed_states_of(line, reversal_index)
            if not undone:
                continue
            hit = next((state for state in undone if _matches(state)), '')
            if not hit and _matches(line):
                hit = line
            if hit:
                return f"the not_found assertion at blocks[{block_index}].asserts[{assert_index}] declares blocks[{step}] as its causal step, and that step's command line {line!r} is the build-bound inverse of {hit!r} — it removes the very state the assertion then reports as absent. The assertion is satisfied by that removal, so it verifies nothing about the behaviour under test. A declared causal step does not lift this refusal."
    return ''

def _reversed_states_of(line: str, reversal_index: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    words = str(line or '').lower().split()
    for count in range(len(words), 0, -1):
        candidate = ' '.join(words[:count])
        if candidate in reversal_index:
            return reversal_index[candidate]
    return ()

@lru_cache(maxsize=8)
def _teardown_reversal_index(device_build: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    build = str(device_build or '').strip()
    if not build:
        return ()
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import device_os_build_suffix
        from cex_core.engine.scripts.gen_command_teardown_atlas import load_command_teardown_atlas, verify_atlas_source_identity
        build = device_os_build_suffix(build) or build
        atlas = load_command_teardown_atlas(expected_build=build)
        verify_atlas_source_identity(atlas)
    except Exception:
        logger.warning('teardown atlas 不可用——绑定声明不给豁免', exc_info=True)
        return ()
    index: dict[str, set[str]] = {}
    for head, entry in (atlas.get('commands') or {}).items():
        if not isinstance(entry, Mapping):
            continue
        teardown = entry.get('teardown')
        if not isinstance(teardown, Mapping):
            continue
        inverses = [str(value).strip().lower() for value in teardown.get('suggested_inverses') or [] if str(value).strip()]
        if not inverses:
            continue
        forward = str(head or '').strip().lower()
        if not forward:
            continue
        if str(teardown.get('matched_form') or '') == 'switch_sibling':
            index.setdefault(forward, set()).update(inverses)
            continue
        for inverse in inverses:
            index.setdefault(inverse, set()).add(forward)
    return tuple(((key, tuple(sorted(values))) for key, values in sorted(index.items())))

def _gate_semantic_key_group_rank(body: Mapping[str, Any], final_steps: Sequence[Any], report: _Report) -> None:
    gate = 'semantic_key_group_rank'
    report.ran(gate)
    for key, ids, rank, size in semantic_key_group_defects(final_steps):
        report.reject(gate, 'semantic_key_group_rank_deficient', f'semantic_key={key}', f"{size} assertions share this semantic_key but only {rank} distinct (observation_ref, F, G) triples: {', '.join(ids)}. Two assertions doing the same thing verify one thing; give each claim its own observation or its own operator/expected value.")
    scoped: dict[str, list[str]] = {}
    missing: dict[str, list[str]] = {}
    for index, item in enumerate(body.get('expectation_binding') or []):
        if not isinstance(item, Mapping):
            continue
        key = str(item.get('semantic_key') or '')
        scoped.setdefault(key, []).append(str(item.get('expectation_id') or ''))
        if not str(item.get('scope_ref') or '').strip():
            missing.setdefault(key, []).append(f'expectation_binding[{index}]')
    for key, loci in sorted(missing.items()):
        if len(scoped.get(key, ())) < 2:
            continue
        report.advise(gate, 'scope_ref_absent', f'semantic_key={key}', f"{len(scoped[key])} claims share this semantic_key and {', '.join(loci)} carry no scope_ref; without it the verification card cannot tell the sibling claims apart.")

def _gate_escape_hatch_accounting(body: Mapping[str, Any], report: _Report) -> list[EscapeHatchDefect]:
    gate = 'escape_hatch_accounting'
    report.ran(gate)
    positions: list[int] = []
    indices: list[int] = []
    for index, hatch in enumerate(body.get('escape_hatches') or []):
        if not isinstance(hatch, Mapping):
            continue
        block_index = hatch.get('block_index')
        if not isinstance(block_index, int) or isinstance(block_index, bool):
            continue
        positions.append(index)
        indices.append(block_index)
    defects = escape_hatch_accounting_defects(body.get('blocks') or [], indices)
    for defect in defects:
        locus = 'escape_hatches' if defect.entry_index < 0 else f'escape_hatches[{positions[defect.entry_index]}]'
        report.reject(gate, defect.code, locus, defect.detail)
    return defects

def _gate_document_consistency(body: Mapping[str, Any], measurements: Mapping[str, Any], escape_defects: Sequence[EscapeHatchDefect], report: _Report) -> None:
    gate = 'document_consistency'
    report.ran(gate)
    try:
        seal = seal_mechanical_case(dict(body), capabilities_used=list(measurements['capabilities_used']), expanded_step_count=int(measurements['expanded_step_count']), check_point_count=int(measurements['check_point_count']), gate_report_sha256=_PROVISIONAL_GATE_REPORT_SHA256)
    except MechanicalCaseError as exc:
        report.reject(gate, 'seal_uncastable', 'seal', str(exc))
        return
    case, error = validate_mechanical_case({**dict(body), 'seal': seal})
    if case is None:
        if any((defect.detail in error for defect in escape_defects)):
            report.reject_named_by(gate, 'escape_hatch_accounting')
            return
        report.reject(gate, 'document_inconsistent', 'case', error)

def run_mechanical_case_gate(mc: Any, contract: Mapping[str, Any], *, contract_sha256: str, device_build: str, outputs_root: Path | None=None, consistency_contract: Mapping[str, Any] | None=None, consistency_contract_sha256: str='', consistency_required: bool=False, source_case_slice: Mapping[str, Any] | None=None, source_case_slice_sha256: str='') -> tuple[bool, dict[str, Any]]:
    report = _Report(str(mc.get('autoid') or '') if isinstance(mc, Mapping) else '')
    measurements: dict[str, Any] | None = None
    body = _gate_body(mc, report)
    if body is not None:
        _gate_contract_description(body, contract, report)
        _gate_consistency_contract(body, contract, contract_sha256, consistency_contract, consistency_contract_sha256, consistency_required, report)
        _gate_criterion_type_binding(body, contract, report, device_build=device_build)
        expanded = _gate_blocks_expansion(body, report)
        if expanded is not None:
            intermediate_steps, intermediate_provenance = expanded
            measurements = _measurements(intermediate_steps)
            lowered = _gate_derived_assertion_expansion(intermediate_steps, intermediate_provenance, report)
            if lowered is not None:
                steps, provenance_steps = lowered
                init = _init_g(body['init_commands'])
                author_ip_literals = _author_ip_literals_for_submission(report.autoid, steps, init, source_case_slice=source_case_slice, source_case_slice_sha256=source_case_slice_sha256)
                _gate_structural_lint(steps, provenance_steps, init, report, device_build=device_build, author_ip_literals=author_ip_literals)
                _gate_author_procedure_coverage(contract, steps, init, report, device_build=device_build)
                _gate_https_certificate_lifecycle(steps, init, report, device_build=device_build)
                _gate_unreachable_ips(report.autoid, steps, init, report, source_case_slice=source_case_slice, source_case_slice_sha256=source_case_slice_sha256)
                _gate_trigger_reachability(report.autoid, steps, init, body['blocks'], report, author_ip_literals=author_ip_literals)
                _gate_negative_probe_path(body['blocks'], report)
                _gate_paired_teardown(steps, init, report, device_build=device_build)
                case = _gate_provenance_receipts(report.autoid, steps, provenance_steps, report, outputs_root)
                if case is not None:
                    final_steps = _product_assertions(case)
                    _gate_expectation_bijection(body, contract, contract_sha256, final_steps, case.steps, report)
                    _gate_semantic_key_group_rank(body, final_steps, report)
        _gate_answerer_statement(body, report)
        escape_defects = _gate_escape_hatch_accounting(body, report)
        if measurements is not None:
            _gate_document_consistency(body, measurements, escape_defects, report)
        _gate_step_graph(body, report)
    try:
        body_sha256 = _canonical_sha256(body) if body is not None else ''
    except (TypeError, ValueError, RecursionError):
        body_sha256 = ''
    rendered = report.render(measurements, {'mechanical_case_body_sha256': body_sha256, 'contract_sha256': str(contract_sha256 or ''), 'device_build': str(device_build or ''), 'consistency_contract_sha256': str(consistency_contract_sha256 or '')})
    return (bool(rendered['ok']), rendered)

def _gate_step_graph(mc: Any, report: _Report) -> None:
    from cex_core.engine.case_compiler.step_graph import check_step_graph
    report.ran('step_graph')
    blocks = mc.get('blocks') if isinstance(mc, Mapping) else None
    graph = check_step_graph(blocks if isinstance(blocks, list) else [])
    for issue in graph.issues:
        report.advise('step_graph', issue.code, issue.path, f'{issue.message} | evidence={issue.evidence}')

def _measurements(steps: Sequence[dict]) -> dict[str, Any]:
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import _raw_capabilities_touched
    return {'capabilities_used': _raw_capabilities_touched(list(steps)), 'expanded_step_count': len(steps), 'check_point_count': sum((1 for step in steps if str(step.get('E') or '').strip() == _CHECK_POINT_OBJECT))}
__all__ = ['AUDIENCE_VERIFICATION_CARD', 'AUDIENCE_WORKER', 'GATE_ORDER', 'GATE_REPORT_SCHEMA', 'NUMBERED_GATES', 'gate_report_digest', 'load_frozen_contract', 'run_mechanical_case_gate', 'semantic_key_group_defects']
