# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/mechanical_case_submit_tool.py（sha256 93dfff20079996d6）。不在这里手改。
from __future__ import annotations
import copy
import json
import re
import threading
from pathlib import Path
from typing import Any, Literal
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field
from cex_core.engine.case_compiler.mechanical_case import MechanicalCaseDescription, MechanicalCaseEscapeHatch, MechanicalCaseExpectationBinding
from cex_core.engine.engine_managed_outputs import MECHANICAL_CASE_SIDECAR_NAME
SUBMISSION_SCHEMA = 'ist.mechanical-case-submission'
_BLOCK_EDIT_REPAIR_CODES = frozenset({'all_assertions_exempt', 'blocks_invalid', 'criterion_binding_missing', 'criterion_lowering_mismatch', 'criterion_status_claim_literalized', 'criterion_status_target_unbound', 'environment_unreachable_ip', 'expectation_bijection_failed', 'fixture_expected_not_config_backref', 'missing_teardown', 'no_assertion_in_case', 'provenance_source_unresolved', 'seal_uncastable', 'trigger_reachability_invalid'})
_LEGAL_FORM_BY_CODE: dict[str, str] = {'expectation_bijection_failed': "Put expectation_id and semantic_key on the assertion slot itself, then point one expectation_binding entry at that exact block/assert index. A normal Author assertion uses ref='intent:<expectation_id>'; a contract-authorized fixture uses ref='config_derived:<recipe>' and the sealed fixture binding_input.", 'seal_uncastable': 'Include at least one assertion-producing block and bind every contract expectation to one of its assertion slots; the engine mints the seal.', 'no_assertion_in_case': "Add an assertion-producing block whose final expansion contains E='check_point'; an execution-only block is not an assertion.", 'provenance_source_unresolved': 'Use one resolvable kind:locator on each command carrier and one authorized expected ref on each assertion; split commands that use different locators.', 'fixture_expected_not_config_backref': "Use ref='config_derived:<recipe>' and binding_input={rule_id: 'config.fixture-literal-backref', source_input: {operator, value, fixture_kind, config_block_index, config_command_index}}; the indices name an earlier CONFIG literal and operator/value equal the assertion tuple.", 'criterion_binding_missing': 'Place the contract expectation_id and semantic_key on a legal assertion carrier, then add expectation_binding with its block_index and assert_index.', 'criterion_status_target_unbound': "Either bind the assertion to the value the nearest causal CONFIG step changes, or, when the causing step's own command line cannot contain that value, declare it: set state_change_step to that step's blocks[] index and write binding_disclosure — one user-facing Chinese sentence saying why the value is absent from that command line and how the step causes the change. The declaration is disclosed in the delivery report and verified on the device; it does not lift the always-true refusals.", 'criterion_state_change_step_invalid': 'Point state_change_step at a blocks[] index that exists, runs before the observation, and carries a product configuration command line.', 'criterion_state_change_step_self_satisfying': 'Do not declare a step that undoes the asserted state as the cause of a not_found assertion; observe the behaviour the case tests, or bind an independently signed derived expectation.', 'blocks_invalid': 'Use one registered block kind and only its schema fields; keep every assertion identity and source field on the carrier named by the error locus.', 'document_inconsistent': 'Keep the eight body sections complete, and make each expectation_binding entry byte-identical to the identity carried by its referenced assertion slot.', 'submission_repair_blocks_changed': 'When blocks change, resubmit expectation_binding and escape_hatches with indices for the changed block array; omission is safe only when the engine can revalidate every prior index under a cited block-edit violation.', 'submission_repair_blocks_change_not_authorized': 'When omitting expectation_binding or escape_hatches, keep blocks byte-identical or use a cited block-edit violation whose old indices still revalidate. Otherwise resubmit the complete envelope with both sections recomputed for the new blocks.', 'submission_repair_envelope_rebind_required': 'Resubmit the complete expectation_binding and escape_hatches sections with indices recomputed for the changed blocks; stale indices are never guessed.'}
_LEGAL_FORM_BY_GATE: dict[str, str] = {'criterion_type_binding': 'Bind each normalized criterion to one carrier/operator pair listed by this violation, preserving its contract identity.', 'dispatch_binding': 'Preserve the dispatched autoid and submit the complete eight-section body; pass binding as an empty object for engine stamping.', 'expectation_bijection': 'Give every contract expectation at least one distinct, identity-bearing assertion slot and no assertion identity outside the contract.', 'provenance_receipts': 'Attach a resolvable authorized source to every command and expected carrier; device actual and history are not expected sources.'}
from cex_core.engine.case_compiler._sealed_io import CONTRACT_CARD_MAX_BYTES as _MAX_CONTRACT_BYTES
_INTENT_STAMP_SCHEMA = 'ist.intent-stamp-status'
_BINDING_GATE = 'dispatch_binding'
_RECOMPOSE_CONSISTENCY_SCHEMA = 'ist.recompose-consistency'
_RECOMPOSE_CONSISTENCY_VERDICTS = frozenset({'consistent', 'mutually_exclusive', 'underdetermined'})
_ABANDON_VERDICT = 'mutually_exclusive'
CONSISTENCY_NOT_STAMPED = 'not_stamped'
CONSISTENCY_NOT_APPLICABLE = 'not_applicable'
CONSISTENCY_INVALID = 'invalid'

class MechanicalCaseSubmissionBody(BaseModel):
    """Model-facing unsealed body; required keys are visible in the tool JSON Schema.

    The trusted submission boundary still stamps ``binding`` and runs the complete
    submission rules. This model only prevents a repair turn from silently dropping an
    unchanged envelope section while editing another section.
    """
    model_config = ConfigDict(extra='forbid', strict=True, populate_by_name=False)
    schema_: Literal['ist.mechanical-case'] = Field(alias='schema', serialization_alias='schema')
    autoid: str = Field(min_length=18, max_length=18)
    description: MechanicalCaseDescription
    binding: dict[str, Any] = Field(description='Pass an empty object. The trusted dispatch stamps every binding field; a non-empty value is only an exact cross-check.')
    init_commands: list[str] = Field(max_length=512)
    blocks: list[dict[str, Any]] = Field(min_length=1, max_length=1024)
    expectation_binding: list[MechanicalCaseExpectationBinding] | None = Field(default=None, min_length=1, max_length=1024, description='Required on every submission, including repair submissions. Every contract-card expectation must be bound to its current assertion slot.')
    escape_hatches: list[MechanicalCaseEscapeHatch] | None = Field(default=None, max_length=1024, description='One entry per kind=STEP block. A repair turn may omit this only when the tool can restore it from a prior submission with byte-identical blocks; otherwise omission becomes an empty array and the business gate still rejects a STEP whose ledger entry is missing.')

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        required = list(schema.get('required') or [])
        if 'expectation_binding' not in required:
            required.append('expectation_binding')
        schema['required'] = required
        return schema

class MechanicalCaseSubmissionArgs(BaseModel):
    """Payload channels: native object preferred, file channel for complete JSON bodies."""
    model_config = ConfigDict(extra='forbid', strict=True)
    mechanical_case: MechanicalCaseSubmissionBody | dict[str, Any] | str = Field(default='', description='The ist.mechanical-case submission body: the keys schema, autoid, description, binding, init_commands, blocks, expectation_binding, escape_hatches. Pass a native JSON object. A serialized JSON string is also accepted. If a receipt reports invalid or empty JSON, fs_write this body as one JSON document under workspace/outputs/<autoid>/ and pass mechanical_case_path instead. Do NOT include `seal` — the engine mints it from its own dry run of your blocks after the submission rules pass, and a self-reported seal is rejected outright. The machine-readable field-level schema of every key (including each sub-object) is the `mechanical_case_envelope` section of knowledge/data/compile_ref/blocks_schema.json — fs_read it before composing instead of searching the workspace for prior examples. The engine-owned SSL_CERT_LOAD standard-library block is accepted here and deterministically lowered before sealing. Place it after creating its bound_object and before the first TLS business observation; the engine defers its object-scoped cleanup until after the final signed business assertion and before trailing dependent-object teardown. Its exact Pass binding as an empty object: the engine stamps contract, mindmap, capability, authored-round and consistency identities from the trusted dispatch, and rejects a conflicting non-empty caller value. The sealed field and lifecycle contract is projected in that same blocks_schema.json. Omit every certificate-material field to bind its promoted release fixture; repository paths supplied by the caller are not device facts.')
    mechanical_case_path: str = Field(default='', description="Fallback file channel: path to a JSON file inside the case's outputs directory containing the submission body. Preferred when the body is too large to trust as an argument — the file channel bypasses argument serialization entirely. Wins over a stringified `mechanical_case`; a native object still wins over both.")

def _canonicalize_submission_blocks(mechanical_case: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    blocks = mechanical_case.get('blocks')
    if not isinstance(blocks, list):
        return (dict(mechanical_case), '')
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import SSL_CERT_LOAD_KIND, split_ssl_certificate_load_blocks
    if not any((isinstance(block, dict) and str(block.get('kind') or '').strip().upper() == SSL_CERT_LOAD_KIND for block in blocks)):
        return (dict(mechanical_case), '')
    expanded: list[dict[str, Any]] = []
    deferred_cleanup: list[list[dict[str, Any]]] = []
    engine_escape_hatches: list[dict[str, Any]] = []
    old_to_new: dict[int, int | None] = {}

    def _record_engine_steps(rows: list[dict[str, Any]], start: int) -> None:
        for offset, lowered in enumerate(rows):
            if str(lowered.get('kind') or '').strip().upper() != 'STEP':
                continue
            engine_escape_hatches.append({'block_index': start + offset, 'capabilities_touched': [str(lowered.get('F') or '')], 'reason': 'Engine-owned SSL_CERT_LOAD standard-library lowering uses the exact framework method projected from excel_contract.json; the caller did not select a generic STEP escape hatch.'})
    binding_indices = [entry.get('block_index') for entry in mechanical_case.get('expectation_binding') or [] if isinstance(entry, dict) and isinstance(entry.get('block_index'), int) and (not isinstance(entry.get('block_index'), bool))]
    business_anchor = max(binding_indices) if binding_indices else len(blocks) - 1

    def _flush_cleanup() -> None:
        for cleanup in reversed(deferred_cleanup):
            start = len(expanded)
            expanded.extend(cleanup)
            _record_engine_steps(cleanup, start)
        deferred_cleanup.clear()
    for index, block in enumerate(blocks):
        if isinstance(block, dict) and str(block.get('kind') or '').strip().upper() == SSL_CERT_LOAD_KIND:
            old_to_new[index] = None
            setup, cleanup, error = split_ssl_certificate_load_blocks(block)
            if error or setup is None or cleanup is None:
                return (None, f'blocks[{index}]({SSL_CERT_LOAD_KIND}): {error}')
            start = len(expanded)
            setup_copy = copy.deepcopy(setup)
            expanded.extend(setup_copy)
            _record_engine_steps(setup_copy, start)
            deferred_cleanup.append(copy.deepcopy(cleanup))
        else:
            old_to_new[index] = len(expanded)
            expanded.append(copy.deepcopy(block))
        if index == business_anchor:
            _flush_cleanup()
    _flush_cleanup()
    body = copy.deepcopy(mechanical_case)
    body['blocks'] = expanded
    for field in ('expectation_binding', 'escape_hatches'):
        entries = body.get(field)
        if not isinstance(entries, list):
            continue
        for entry_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            old_index = entry.get('block_index')
            if not isinstance(old_index, int) or isinstance(old_index, bool) or old_index not in old_to_new:
                continue
            new_index = old_to_new[old_index]
            if new_index is None:
                return (None, f'{field}[{entry_index}].block_index points to SSL_CERT_LOAD block {old_index}, which emits no assertion and cannot carry an expectation or escape-hatch entry')
            entry['block_index'] = new_index
    for block_index, block in enumerate(body['blocks']):
        if not isinstance(block, dict):
            continue
        answerer = block.get('answerer')
        if not isinstance(answerer, dict):
            continue
        if str(answerer.get('kind') or '').strip() not in ('device', 'fixture'):
            continue
        old_ref = answerer.get('ref')
        if not isinstance(old_ref, int) or isinstance(old_ref, bool) or old_ref not in old_to_new:
            continue
        new_ref = old_to_new[old_ref]
        if new_ref is None:
            return (None, f'blocks[{block_index}].answerer.ref points to SSL_CERT_LOAD block {old_ref}, which the engine lowers into setup/cleanup blocks; name the CONFIG block that creates the answering object instead')
        answerer['ref'] = new_ref
    if engine_escape_hatches and isinstance(body.get('escape_hatches'), list):
        body['escape_hatches'].extend(engine_escape_hatches)
    return (body, '')

def _violation(code: str, locus: str, detail: str, *, gate: str=_BINDING_GATE) -> dict[str, str]:
    return {'gate': gate, 'code': code, 'locus': locus, 'detail': detail}

def _violations_with_legal_forms(violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rendered: list[dict[str, Any]] = []
    for raw in violations:
        item = dict(raw)
        code = str(item.get('code') or '')
        gate = str(item.get('gate') or '')
        item['legal_form'] = _LEGAL_FORM_BY_CODE.get(code, _LEGAL_FORM_BY_GATE.get(gate, 'Repair the exact locus while preserving every other sealed identity; resubmit the complete native JSON body for the engine to re-run all gates.'))
        rendered.append(item)
    return rendered

def unique_exempt_blocks_submit(mechanical_case: dict[str, Any]) -> dict[str, str] | None:
    from cex_core.engine.case_compiler.blocks import expand_blocks
    from cex_core.engine.case_compiler.mutation_testing import EXEMPT_ISSUER_COMPILER, derive_mutation_requirements
    steps, _prov, err = expand_blocks(list(mechanical_case.get('blocks') or []))
    if err or not steps:
        return None
    checks = [step for step in steps if str(step.get('E') or '').strip() == 'check_point']
    if not checks or any((step.get('exempt') is not True for step in checks)):
        return None
    requirements, derive_error = derive_mutation_requirements(steps, None, device_build='')
    if not derive_error and requirements and all((str(item.get('issuer') or '') == EXEMPT_ISSUER_COMPILER for item in requirements)):
        return None
    return _violation('all_assertions_exempt', 'blocks', 'every product assertion is Exempt; add at least one non-exempt check_point before submit. A full exemption passes only when the compiler recomputes and issues every one. An author-declared exemption, including non_readonly_probe kept on a window that can host a pre-state control, is rejected here.', gate='exempt_governance')

def _repeated_code_disclosure(rejections: list[dict]) -> dict[str, object] | None:
    """同码连拒三次就告诉它：这条路实测救不回来。

    全语料量过：46 个 dispatch 出现过「同一个码连续三个 attempt 被拒」，其中最终
    composed 的是 **0** 个——救回率 0%。再提交同一形态只是把这一轮的预算烧完，
    而剩下的 attempt 本可以换法或把缺口说清楚。

    照 opencode `try-best-detector.ts` 的分级（productive→suspected→try_best）：
    这里只发提示、不改控制流；连拒跨派发那一档另有 `structural_rejection_disclosure`。
    """
    if len(rejections) < 3:
        return None
    tail = rejections[-3:]
    attempts = [int(row.get('attempt') or 0) for row in tail]
    if attempts != list(range(attempts[0], attempts[0] + 3)):
        return None
    code_sets = [{str(item.get('code') or '') for item in row.get('violations') or [] if str(item.get('code') or '')} for row in tail]
    if not all(code_sets):
        return None
    repeated = sorted(set.intersection(*code_sets))
    if not repeated:
        return None
    return {'code': 'repeated_rejection_streak', 'codes': repeated, 'attempts': attempts, 'detail': f"The same rule rejected attempts {attempts[0]}-{attempts[-1]}: {', '.join(repeated)}. Across the recorded corpus no dispatch that reached this streak ever produced an accepted case (0 of 46). Resubmitting this shape spends the remaining attempts without changing the outcome. Either write a different source-grounded form, or record what is missing through engine_gap and submit_authoring_account."}

def _rejected(autoid: str, violations: list[dict[str, Any]], *, disclosures: list[dict[str, Any]] | None=None) -> str:
    return json.dumps({'schema': SUBMISSION_SCHEMA, 'status': 'rejected', 'autoid': autoid, 'artifact': None, 'mechanical_case_sha256': None, 'artifact_sha256': None, 'violations': _violations_with_legal_forms(violations), 'disclosures': list(disclosures or [])}, ensure_ascii=False, sort_keys=True, indent=2)
_BODY_PAYLOAD_STREAKS: dict[str, int] = {}
_BODY_PAYLOAD_STREAK_LOCK = threading.Lock()

def _bump_body_payload_streak(key: str) -> int:
    with _BODY_PAYLOAD_STREAK_LOCK:
        value = _BODY_PAYLOAD_STREAKS.get(key, 0) + 1
        _BODY_PAYLOAD_STREAKS[key] = value
        return value

def _reset_body_payload_streak(key: str) -> None:
    with _BODY_PAYLOAD_STREAK_LOCK:
        _BODY_PAYLOAD_STREAKS.pop(key, None)

def _body_payload_streak_key(autoid: str) -> str:
    from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
    session = current_worker_device_session()
    return ':'.join((str(getattr(session, 'batch_run_id', '') or ''), str(getattr(session, 'dispatch_id', '') or ''), autoid))

def _body_payload_reject(autoid: str, code: str, locus: str, detail: str, *, streak: int | None=None) -> str:
    if streak is not None and streak >= 2:
        detail += ' → Two consecutive payload-channel failures were observed; their cause is not established. Do not repeat the unchanged payload. Use an available alternative within the existing budget, or record the unresolved issue through engine_gap and finish per your report contract. This receipt establishes neither content validity nor fault ownership.'
    return _rejected(autoid, [_violation(code, locus, detail)])

def _resolve_submission_body(mechanical_case: Any, mechanical_case_path: str, *, autoid: str) -> tuple[Any, str]:
    """载荷通道优先级：原生对象（含模型）> 文件通道 > 字符串化体（容错解析）。

    与 submit_machine_mindmap_cases 同一味药（2026-09-20/21 实证：端点会把大数组
    stringify/截断，本工具铸不出 strict，单通道下畸形体只会吃到 compat 的通用
    "arguments are invalid" 教学、同形重交烧预算）。区别在指路方向：编写孔**有**
    fs_write，所以畸形/空载荷的回执直接把文件通道作为首选修法说死；重复失败只披露原件与次数，
    不推断传输或模型责任；没有可用修法时经已有报告通道收口。显式空 dict 不劫持——那是内容级
    失误，留给交卷规则的既有违例码。载荷到站（本函数成功返回）即复位连败。
    """
    reissue_hint = f'Preferred fix: fs_write the complete submission body as one JSON document under workspace/outputs/{autoid}/ (e.g. mechanical_case_body.json), then call submit_mechanical_case again with mechanical_case_path=that path — the file channel bypasses argument serialization entirely. Re-issuing one compact native object also works, but every verbatim atom must stay exactly as authored.'
    if isinstance(mechanical_case, MechanicalCaseSubmissionBody):
        return (mechanical_case, '')
    if isinstance(mechanical_case, dict):
        return (mechanical_case, '')
    text = ''
    locus = 'mechanical_case'
    if (mechanical_case_path or '').strip():
        locus = 'mechanical_case_path'
        try:
            from cex_core.engine.ist_core.tools.device import _sealed_output
            target = _sealed_output.scoped_output_path(mechanical_case_path.strip())
            case_root = _sealed_output.case_output_path(autoid, '.payload-channel-scope').parent
            target.relative_to(case_root)
            text = _sealed_output.read_bytes(target, max_bytes=16 * 1024 * 1024).decode('utf-8')
        except Exception as exc:
            return (None, _body_payload_reject(autoid, 'body_path_unreadable', 'mechanical_case_path', f"the mechanical_case_path file could not be read ({type(exc).__name__}); it must be a regular JSON file inside the case's outputs directory.", streak=_bump_body_payload_streak(_body_payload_streak_key(autoid))))
    elif isinstance(mechanical_case, str) and mechanical_case.strip():
        text = mechanical_case
    if not text.strip():
        return (None, _body_payload_reject(autoid, 'body_payload_empty', 'mechanical_case', 'no payload channel carried content; the cause is not established. ' + reissue_hint, streak=_bump_body_payload_streak(_body_payload_streak_key(autoid))))
    try:
        from cex_core.engine.case_compiler._sealed_io import validate_json_budget
        from cex_core.engine.case_compiler.mechanical_case import _reject_constant, _reject_duplicate_keys
        if len(text.encode('utf-8')) > 16 * 1024 * 1024:
            raise ValueError('payload exceeds the byte budget')
        validate_json_budget(text, error_type=ValueError, message='payload exceeds the JSON structure budget')
        parsed = json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except Exception as exc:
        return (None, _body_payload_reject(autoid, 'body_payload_unparseable', locus, f'the payload arrived as text that is not valid JSON ({type(exc).__name__}); the cause is not established. ' + reissue_hint, streak=_bump_body_payload_streak(_body_payload_streak_key(autoid))))
    if not isinstance(parsed, dict) or not parsed:
        return (None, _body_payload_reject(autoid, 'body_payload_unparseable', locus, f'the payload must be a non-empty JSON object (the ist.mechanical-case submission body); got {type(parsed).__name__}. ' + reissue_hint, streak=_bump_body_payload_streak(_body_payload_streak_key(autoid))))
    return (parsed, '')
ANSWERER_UNDETERMINED_CLAIM_KIND = 'answerer_undetermined'

def _route_answerer_undetermined(autoid: str, mechanical_case: dict[str, Any]) -> str | None:
    from cex_core.engine.case_compiler.blocks import _DUT_HOSTS
    blocks = mechanical_case.get('blocks')
    if not isinstance(blocks, list):
        return None
    hits: list[tuple[int, str, str]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        if str(block.get('kind') or '').strip().upper() not in ('OBSERVE_ASSERT', 'OBSERVE_EXIT'):
            continue
        host = str(block.get('host') or '').strip()
        if host in _DUT_HOSTS:
            continue
        answerer = block.get('answerer')
        if not isinstance(answerer, dict):
            continue
        if str(answerer.get('kind') or '').strip() != 'undetermined':
            continue
        note = str(answerer.get('note') or '').strip()
        if not note:
            continue
        hits.append((index, host, note))
    if not hits:
        return None
    from cex_core.engine.ist_core.compile_engine.user_text_contract import validate_user_facing_text
    text_validation = validate_user_facing_text({f'blocks[{index}].answerer.note': note for index, _host, note in hits})
    if not text_validation['accepted']:
        details = ', '.join((f"{item['field']}={','.join(item['terms'])}" for item in text_validation['violations']))
        return _rejected(autoid, [_violation('answerer_note_not_user_facing', 'blocks[].answerer.note', f"the undetermined-answerer note lands verbatim in the user's decision panel, so it must be user-facing Chinese without exact internal terms ({details})", gate='answerer_statement')])
    loci = [f'blocks[{index}].answerer' for index, _host, _note in hits]
    notes = list(dict.fromkeys((note for _index, _host, note in hits)))
    entry = {'reason': '交互观测步的应答方没有来源可定：' + '；'.join(notes), 'loci': loci, 'observation_hosts': sorted({host for _i, host, _n in hits}), 'notes': notes}
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import land_answerer_undetermined_claim
    landed = land_answerer_undetermined_claim(autoid, entry)
    if not landed:
        return _rejected(autoid, [_violation('answerer_claim_landing_failed', 'needs_decision.json', 'the typed answerer_undetermined claim could not be persisted; retry the submission in this same turn before finishing', gate='answerer_statement')])
    return json.dumps({'schema': SUBMISSION_SCHEMA, 'status': 'routed', 'autoid': autoid, 'claim_kind': ANSWERER_UNDETERMINED_CLAIM_KIND, 'routed': True, 'ledger': f'workspace/outputs/{autoid}/needs_decision.json', 'loci': loci, 'detail': 'The engine landed a typed answerer_undetermined user-decision claim for the traffic-driving observation block(s) at ' + ', '.join(loci) + "; nothing was sealed and this case now waits on the user's answer. Do not resubmit the unanswered chain in this dispatch: finish with status=needs_user_decision and carry the pending claim in summary.", 'violations': []}, ensure_ascii=False, sort_keys=True, indent=2)

def _bounded_json(path: Path, *, max_bytes: int) -> tuple[dict[str, Any] | None, bytes]:
    from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow, validate_json_budget
    try:
        raw = read_regular_nofollow(path, error_type=ValueError, invalid_message='path is invalid', directory_message='directory is unavailable', open_message='file is unavailable', bounds_message='file exceeds the byte budget', changed_message='file changed while being read', max_bytes=max_bytes)
        assert isinstance(raw, bytes)
        validate_json_budget(raw, error_type=ValueError, message='file exceeds the JSON structure budget')
        payload = json.loads(raw.decode('utf-8'))
    except (OSError, ValueError, RecursionError):
        return (None, b'')
    return (payload if isinstance(payload, dict) else None, raw)

def _intent_json(path: Path, outputs_root: Path) -> dict[str, Any] | None:
    from cex_core.engine.case_compiler.contract_entry import ContractError, read_intent_json
    try:
        payload, _raw = read_intent_json(path, trusted_root=outputs_root)
    except ContractError:
        return None
    return payload

def _stamp_verified_consistency_binding(mechanical_case: dict[str, Any], *, verified_overlay_sha256: str) -> dict[str, Any]:
    binding = mechanical_case.get('binding')
    if not isinstance(binding, dict):
        return mechanical_case
    declared = binding.get('consistency_contract_sha256')
    if declared not in (None, ''):
        return mechanical_case
    stamped = dict(mechanical_case)
    stamped_binding = dict(binding)
    stamped_binding['consistency_contract_sha256'] = verified_overlay_sha256
    stamped['binding'] = stamped_binding
    return stamped

def _trusted_mindmap_source_sha256(contract: dict[str, Any], *, session: Any, project_root: Path) -> str:
    source_shas = {str(claim.get('source_sha256') or '') for item in contract.get('expectations') or [] if isinstance(item, dict) for claim in (item.get('author_claim'),) if isinstance(claim, dict) and re.fullmatch('[0-9a-f]{64}', str(claim.get('source_sha256') or ''))}
    if len(source_shas) == 1:
        return next(iter(source_shas))
    manifest_ref = str(getattr(session, 'source_manifest_ref', '') or '')
    manifest_sha = str(getattr(session, 'source_manifest_sha256', '') or '')
    if not manifest_ref or not re.fullmatch('[0-9a-f]{64}', manifest_sha):
        return ''
    manifest, raw = _bounded_json(project_root / manifest_ref, max_bytes=16 * 1024 * 1024)
    if not isinstance(manifest, dict):
        return ''
    from cex_core.engine.case_compiler._sealed_io import sha256_bytes
    source_sha = str(manifest.get('source_sha256') or '')
    if sha256_bytes(raw) != manifest_sha or re.fullmatch('[0-9a-f]{64}', source_sha) is None:
        return ''
    return source_sha

def _stamp_engine_binding(mechanical_case: dict[str, Any], *, contract: dict[str, Any], contract_sha256: str, consistency_contract_sha256: str | None, session: Any, project_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    binding = mechanical_case.get('binding')
    if binding is None:
        binding = {}
    if not isinstance(binding, dict):
        return (mechanical_case, [])
    mindmap_sha = _trusted_mindmap_source_sha256(contract, session=session, project_root=project_root)
    expected: dict[str, Any] = {'contract_sha256': contract_sha256, 'consistency_contract_sha256': consistency_contract_sha256, 'mindmap_source_sha256': mindmap_sha, 'capability_generation_id': str(getattr(session, 'capability_generation_id', '') or ''), 'capability_projection_sha256': str(getattr(session, 'capability_projection_sha256', '') or ''), 'authored_round': int(getattr(session, 'authored_round', 1) or 1)}
    missing_engine = [key for key, value in expected.items() if key != 'consistency_contract_sha256' and value in (None, '')]
    if missing_engine:
        return (mechanical_case, [_violation('engine_binding_unavailable', 'binding', 'the engine dispatch cannot stamp required binding field(s): ' + ', '.join(sorted(missing_engine)))])
    stamped_binding = dict(binding)
    violations: list[dict[str, str]] = []
    for key, value in expected.items():
        declared = stamped_binding.get(key)
        if declared in (None, ''):
            stamped_binding[key] = value
            continue
        if declared != value:
            violations.append(_violation('consistency_contract_identity_drift' if key == 'consistency_contract_sha256' else 'engine_binding_drift', f'binding.{key}', f'the caller declared {declared!r}, but the trusted dispatch binds {value!r}; omit this engine-owned field instead of copying it'))
    stamped = dict(mechanical_case)
    stamped['binding'] = stamped_binding
    return (stamped, violations)

def _frozen_contract(autoid: str, outputs_root: Path, project_root: Path) -> tuple[dict[str, Any] | None, str, list[dict[str, str]]]:
    case_dir = outputs_root / autoid
    stamp, _ = _bounded_json(case_dir / 'intent_stamp_status.json', max_bytes=64 * 1024)
    if not isinstance(stamp, dict) or stamp.get('schema') != _INTENT_STAMP_SCHEMA or str(stamp.get('autoid') or '') != autoid or (str(stamp.get('status') or '') != 'complete'):
        return (None, '', [_violation('intent_stamp_incomplete', 'intent_stamp_status.json', f'the engine has no complete intent/spec identity stamp for case {autoid}; the mechanical case submission rules have nothing to reconcile its expectations against')])
    intent = _intent_json(case_dir / 'intent.json', outputs_root)
    if not isinstance(intent, dict) or str(intent.get('autoid') or '') != autoid:
        return (None, '', [_violation('intent_stamp_incomplete', 'intent.json', f'the stamped intent for case {autoid} is unreadable or carries another case identity')])
    declared_sha = str(intent.get('typed_expectation_contract_sha256') or '').strip()
    declared_rel = str(intent.get('typed_expectation_contract_path') or '').strip()
    if not declared_sha or not declared_rel:
        return (None, '', [_violation('frozen_contract_absent', 'intent.json', f'case {autoid} has no frozen expectation contract; a mechanical case is compiled against contract-card expectations, so there is nothing to redeem. Report the gap instead of inventing expectations.')])
    from cex_core.engine.case_compiler._sealed_io import lexical_path_inside_root, sha256_bytes
    try:
        contract_path = lexical_path_inside_root(project_root / declared_rel, outputs_root, error_type=ValueError, traversal_message='contract path traversal is forbidden', outside_message='contract path escaped the outputs root')
    except ValueError as exc:
        return (None, '', [_violation('frozen_contract_unreadable', 'intent.json', f'the stamped contract path for case {autoid} is not inside outputs: {exc}')])
    contract, raw = _bounded_json(contract_path, max_bytes=_MAX_CONTRACT_BYTES)
    if contract is None:
        return (None, '', [_violation('frozen_contract_unreadable', 'contracts', f'the frozen contract card for case {autoid} cannot be read')])
    contract_sha256 = sha256_bytes(raw)
    if contract_sha256 != declared_sha:
        return (None, '', [_violation('frozen_contract_drift', 'contracts', f'the contract card on disk hashes to {contract_sha256} but the engine stamped {declared_sha} for case {autoid}')])
    return (contract, contract_sha256, [])

def recompose_consistency_state(contract: Any) -> str:
    if not isinstance(contract, dict) or 'consistency' not in contract:
        return CONSISTENCY_NOT_STAMPED
    conclusion = contract.get('consistency')
    if conclusion is None:
        return CONSISTENCY_NOT_APPLICABLE
    if not isinstance(conclusion, dict) or conclusion.get('schema') != _RECOMPOSE_CONSISTENCY_SCHEMA:
        return CONSISTENCY_INVALID
    verdict = conclusion.get('verdict')
    if verdict not in _RECOMPOSE_CONSISTENCY_VERDICTS:
        return CONSISTENCY_INVALID
    return str(verdict)
RECOMPOSE_S1_EVIDENCE_FIELDS = ('spec_quote', 'case_quote', 'spec_locator', 'case_locator', 'incompatibility')

def recompose_abandon_blocker(contract: Any, *, spec_surface_present: bool) -> str:
    if recompose_consistency_state(contract) != _ABANDON_VERDICT:
        return 'not_mutually_exclusive'
    if not spec_surface_present:
        return 'no_comparable_spec_surface'
    conclusion = contract.get('consistency') if isinstance(contract, dict) else None
    if not isinstance(conclusion, dict) or any((not str(conclusion.get(field) or '').strip() for field in RECOMPOSE_S1_EVIDENCE_FIELDS)):
        return 'scenario1_evidence_incomplete'
    return ''

def recompose_abandon_actionable(contract: Any, *, spec_surface_present: bool) -> bool:
    return not recompose_abandon_blocker(contract, spec_surface_present=spec_surface_present)

def _recompose_consistency_violation(contract: dict[str, Any], autoid: str, *, spec_surface_present: bool) -> dict[str, str] | None:
    state = recompose_consistency_state(contract)
    if state == CONSISTENCY_INVALID:
        return _violation('consistency_conclusion_invalid', 'contracts', f'the frozen contract card for case {autoid} carries a consistency conclusion that is not a {_RECOMPOSE_CONSISTENCY_SCHEMA} object with a verdict of consistent, mutually_exclusive, or underdetermined. The conclusion is engine-stamped, so this is not repairable from here: report the malformed stamp instead of resubmitting.')
    if recompose_abandon_actionable(contract, spec_surface_present=spec_surface_present):
        return _violation('case_abandoned_by_consistency', 'contracts', f'the recompose stage judged case {autoid} and its bound specification mutually exclusive on two complete sources, which abandons the case; no mechanical case is accepted for it. A case whose expectation cannot be derived because a precondition is missing is a different conclusion (underdetermined) and does not reach this rule — there, the procedure gets the missing precondition steps. Nothing here is repairable by resubmitting.')
    return None

@tool(args_schema=MechanicalCaseSubmissionArgs)
def submit_mechanical_case(mechanical_case: MechanicalCaseSubmissionBody | dict[str, Any] | str='', mechanical_case_path: str='') -> str:
    """Submit the finished mechanical case for this dispatch; the engine checks it against submission rules and seals it.

    The case identity and the frozen contract card come from the engine's dispatch, not
    from you — passing a body for another autoid is rejected rather than honoured. The
    engine runs the node-1 submission rules over your blocks (expansion dry run, draft lint,
    expectation bijection against the contract card, semantic-key group rank, escape-hatch
    accounting, exact trigger/listener reachability, and build-bound paired teardown), and
    lands nothing when any of them rejects.

    Returns one JSON object. `status: "rejected"` carries every currently-computable item
    in `violations[]`; each names the gate, a stable code, the exact locus (`blocks[i]`,
    `expectation_binding[i]`, `steps[i]`, …), what is wrong, and a minimal `legal_form`
    shape. Fix the complete batch and call again; resubmitting replaces the previous body.
    A complete eight-section resubmission may change blocks and is checked from scratch.
    Only a repair that omits expectation_binding or escape_hatches needs a cited block-edit
    code before the engine may reuse old indices; `disclosures[]` records that narrow
    restoration and any section safely restored. `status: "routed"` is the
    answerer-undetermined exit: when a traffic-driving observation block (host outside the
    two devices under test) carries `answerer: {kind: "undetermined", note}`, the engine
    lands a typed `answerer_undetermined` user-decision claim in needs_decision.json and
    seals nothing — finish with `needs_user_decision` instead of resubmitting the
    unanswered chain. `status: "sealed"` carries the sealed artifact path and its digest;
    copy that artifact path verbatim into your structured response.

    Payload channels, in priority order: the native `mechanical_case` object; optionally
    `mechanical_case_path` — a JSON file under the case's outputs directory holding the
    same body. A serialized body string is accepted too. Invalid or empty payloads are
    rejected with guidance without touching any ledger. Repeated payload failures
    disclose the observed errors and count; they establish neither fault ownership nor
    content validity. Correct the payload through an available channel within the
    existing budget, or record the unresolved issue through engine_gap and finish per
    your report contract.

    Every binding identity is engine-owned glue. Pass `binding: {}`: the engine reopens the
    frozen contract/source/capability/round and any linked consistency overlay, then stamps
    their identities into the sealed body. A non-empty caller value is only a byte-for-byte
    cross-check; a mismatch is rejected rather than overwritten.

    This tool writes no workbook and no delivery credential. A sealed mechanical case means
    the specification is self-consistent and redeems exactly the contract-card expectations
    — never that the case passes on a device.
    """
    from cex_core.engine.case_compiler.mechanical_case import mint_and_land_mechanical_case
    from cex_core.engine.case_compiler.mechanical_case_gate import AUDIENCE_WORKER, gate_report_digest, run_mechanical_case_gate
    from cex_core.engine.ist_core.compile_engine import _shared as sh
    from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
    if isinstance(mechanical_case, MechanicalCaseSubmissionBody):
        mechanical_case = mechanical_case.model_dump(mode='python', by_alias=True)
    session = current_worker_device_session()
    autoid = str(getattr(session, 'autoid', '') or '') if session is not None else ''
    if not autoid:
        return _rejected('', [_violation('no_engine_dispatch', 'session', 'submit_mechanical_case only runs inside an engine-dispatched compile worker with a bound case identity')])
    mechanical_case, payload_error = _resolve_submission_body(mechanical_case, mechanical_case_path, autoid=autoid)
    if payload_error:
        return payload_error
    _reset_body_payload_streak(_body_payload_streak_key(autoid))
    attempt = session.begin_mechanical_case_submission()
    repair_disclosures: list[dict[str, Any]] = []

    def reject(violations: list[dict[str, Any]]) -> str:
        formatted = _violations_with_legal_forms(violations)
        from cex_core.engine.ist_core.compile_engine.authoring_evidence import rule_identity
        from cex_core.engine.ist_core.compile_engine.engine_checkpoints import digest
        input_sha256 = ''
        identity_error = ''
        try:
            input_sha256 = digest(mechanical_case)
        except (RecursionError, TypeError, ValueError) as exc:
            identity_error = type(exc).__name__
        session.record_mechanical_case_rejection(attempt, formatted, input_sha256=input_sha256, rule_identity=rule_identity(), mechanical_case=mechanical_case)
        streak = _repeated_code_disclosure(list(session.mechanical_case_rejections))
        payload = json.loads(_rejected(autoid, formatted, disclosures=repair_disclosures + ([streak] if streak else [])))
        if identity_error:
            payload['input_identity'] = {'status': 'unverified', 'input_sha256': '', 'reason': 'canonical_serialization_failed', 'exception_type': identity_error, 'detail': 'The rejected input could not be canonically hashed; no input identity was issued.'}
        streak = session.structural_rejection_streak()
        if streak:
            payload['structural_rejection'] = {**streak, 'instruction': f"the same rule ({streak['gate']}) has rejected the same code ({streak['code']}) on consecutive submissions; resubmitting the same shape will not change the outcome — stop retrying, report the engine-side criterion gap in your reply"}
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    device_build = str(getattr(session, 'capability_build', '') or '').strip()
    if not device_build:
        return reject([_violation('capability_build_unbound', 'session.capability_build', 'the engine dispatch did not bind a capability build; submission refuses to select the process-wide active command tree')])
    if not isinstance(mechanical_case, dict):
        return reject([_violation('not_an_object', 'mechanical_case', 'mechanical_case must be a native JSON object, not a serialized string')])
    declared_autoid = str(mechanical_case.get('autoid') or '')
    if declared_autoid != autoid:
        return reject([_violation('autoid_not_dispatched', 'autoid', f'this fork is dispatched for case {autoid}; the body declares {declared_autoid!r}')])
    restored_body, restore_error, repair_disclosure = session.prepare_mechanical_case_envelope_sections(mechanical_case, block_edit_authorization_codes=_BLOCK_EDIT_REPAIR_CODES)
    if isinstance(repair_disclosure, dict):
        repair_disclosures.append(repair_disclosure)
        session.record_mechanical_case_repair_disclosure(attempt, repair_disclosure)
    if restored_body is None:
        if restore_error == 'blocks_change_not_authorized':
            code = 'submission_repair_blocks_change_not_authorized'
            detail = 'blocks changed while an index-bearing envelope section was omitted, but the previous rejection did not cite a stable block-edit violation. Keep blocks byte-identical for omission-based restoration, or resubmit the complete expectation_binding and escape_hatches for the new blocks.'
        elif restore_error in {'changed_blocks_require_expectation_binding', 'changed_blocks_require_escape_hatches'}:
            code = 'submission_repair_envelope_rebind_required'
            detail = f'a cited gate permits this blocks edit, but an omitted index-bearing section no longer resolves mechanically against the changed array. Resubmit the complete expectation_binding and escape_hatches for the new blocks ({restore_error}).'
        else:
            code = 'submission_repair_blocks_changed' if restore_error == 'blocks_changed' else 'submission_repair_envelope_unavailable'
            detail = f"expectation_binding or escape_hatches was omitted. The tool may restore those index-bearing sections only from this fork's previous complete submission when every reused index can be revalidated; repair the full envelope instead ({restore_error})."
        return reject([_violation(code, 'mechanical_case', detail)])
    mechanical_case = restored_body
    session.remember_mechanical_case_submission_body(mechanical_case)
    outputs_root = sh.outputs_root()
    contract, contract_sha256, violations = _frozen_contract(autoid, outputs_root, sh.project_root())
    if contract is None:
        return reject(violations)
    intent = _intent_json(outputs_root / autoid / 'intent.json', outputs_root)
    try:
        from cex_core.engine.ist_core.compile_engine.consistency_requirement import NOT_APPLICABLE, REQUIRED, ConsistencyRequirementError, batch_name_from_contract_ref, validate_consistency_requirement
        from cex_core.engine.ist_core.tools.device.consistency_receipt import ConsistencyLedgerError, current_consistency_dispatch, read_consistency_dispatch_ledger
        consistency_scope = current_consistency_dispatch()
        dispatch_id = str(getattr(session, 'dispatch_id', '') or '')
        if consistency_scope.autoid != autoid or consistency_scope.dispatch_id != dispatch_id or Path(consistency_scope.outputs_root) != Path(outputs_root):
            raise ConsistencyLedgerError('consistency dispatch scope identity drift')
        base_contract_ref = str(consistency_scope.source_context.get('base_contract_ref') or '')
        batch_name = batch_name_from_contract_ref(project_root=sh.project_root(), outputs_root=outputs_root, autoid=autoid, contract_ref=base_contract_ref)
        requirement_proof = validate_consistency_requirement(outputs_root=outputs_root, project_root=sh.project_root(), batch_name=batch_name, autoid=autoid, intent=intent if isinstance(intent, dict) else {})
        if consistency_scope.source_context.get('base_contract_sha256') != contract_sha256 or requirement_proof['base_contract_sha256'] != contract_sha256:
            raise ConsistencyRequirementError('intent_contract_identity_mismatch', 'trusted dispatch base contract differs from the projection receipt')
        consistency_record = read_consistency_dispatch_ledger(outputs_root, autoid, dispatch_id).latest()
    except ConsistencyRequirementError as exc:
        return reject([_violation(exc.code, 'consistency_requirement', exc.detail)])
    except (ConsistencyLedgerError, OSError, ValueError) as exc:
        return reject([_violation('consistency_dispatch_scope_invalid', 'consistency_requirement', str(exc))])
    abandoned = _recompose_consistency_violation(contract, autoid, spec_surface_present=requirement_proof['requirement'] != NOT_APPLICABLE)
    if abandoned is not None:
        return reject([abandoned])
    consistency_required = requirement_proof['requirement'] == REQUIRED
    consistency_contract = None
    consistency_contract_sha256 = ''
    if consistency_required:
        consistency_material = consistency_record.get('material') if isinstance(consistency_record, dict) else None
        if not isinstance(consistency_material, dict):
            return reject([_violation('consistency_verdict_missing', 'consistency_verdict', 'step 3 (case versus bound product specification consistency) must produce an accepted verdict before step 4 submits a mechanical case')])
        if str(consistency_material.get('verdict') or '') == 'conflict':
            return reject([_violation('case_abandoned_by_consistency', 'consistency_verdict', 'an accepted consistency verdict on this dispatch says the case and its bound specification cannot both hold, so the case is abandoned at case level and no mechanical case is accepted. Resubmitting changes nothing here.')])
        if str(consistency_material.get('verdict') or '') != 'consistent':
            return reject([_violation('consistency_verdict_missing', 'consistency_verdict', 'the latest consistency credential has no accepted closed verdict')])
        try:
            from cex_core.engine.case_compiler.consistency_contract import load_consistency_contract, validate_consistency_contract
            consistency_contract, consistency_contract_sha256 = load_consistency_contract(outputs_root / autoid / 'consistency_contract.json')
            overlay_error = validate_consistency_contract(consistency_contract, base_contract=contract, base_contract_sha256=contract_sha256, accepted_material=consistency_material, consistency_receipt_sha256=str(consistency_record.get('receipt_sha256') or ''), machine_case=consistency_scope.source_context.get('case') if isinstance(consistency_scope.source_context.get('case'), dict) else None)
            if overlay_error:
                raise ConsistencyLedgerError(overlay_error)
        except (ConsistencyLedgerError, OSError, ValueError):
            return reject([_violation('consistency_contract_invalid', 'consistency_contract.json', 'the linked consistency contract is absent or does not match this dispatch, accepted material, and frozen base contract')])
    else:
        if consistency_record is not None:
            return reject([_violation('consistency_not_applicable_receipt_present', 'consistency_requirement', 'the engine stamped this case not-applicable but the dispatch ledger contains a consistency verdict')])
        declared_overlay = (mechanical_case.get('binding') or {}).get('consistency_contract_sha256') if isinstance(mechanical_case.get('binding'), dict) else None
        if declared_overlay is not None:
            return reject([_violation('consistency_not_applicable_binding_present', 'binding.consistency_contract_sha256', 'the engine stamped no governing specification comparison; the mechanical binding must carry null')])
    mechanical_case, binding_violations = _stamp_engine_binding(mechanical_case, contract=contract, contract_sha256=contract_sha256, consistency_contract_sha256=consistency_contract_sha256 if consistency_required else None, session=session, project_root=sh.project_root())
    if binding_violations:
        return reject(binding_violations)
    mechanical_case, canonicalization_error = _canonicalize_submission_blocks(mechanical_case)
    if mechanical_case is None:
        return reject([_violation('ssl_cert_load_invalid', 'blocks', canonicalization_error, gate='mechanical_case_body')])
    routed = _route_answerer_undetermined(autoid, mechanical_case)
    if routed is not None:
        return routed
    try:
        ok, report = run_mechanical_case_gate(mechanical_case, contract, contract_sha256=contract_sha256, device_build=device_build, outputs_root=outputs_root, consistency_contract=consistency_contract, consistency_contract_sha256=consistency_contract_sha256, consistency_required=consistency_required, source_case_slice=dict(session.source_case_slice or {}), source_case_slice_sha256=str(session.source_case_slice_sha256 or ''))
        gate_report_sha256 = gate_report_digest(report)
        from cex_core.engine.case_compiler.mechanical_case_gate import ADVISE_CODE_CONSUMERS
        for item in report.get('advisories') or []:
            code = str(item.get('code') or '')
            consumer = ADVISE_CODE_CONSUMERS.get(code)
            if consumer is None and code.startswith('gate_disabled:'):
                consumer = 'gate_advisory'
            if consumer and consumer != 'no-consumer':
                session.record_gate_advisory({'gate': str(item.get('gate') or ''), 'code': code, 'locus': str(item.get('locus') or ''), 'detail': str(item.get('detail') or ''), 'fact_event': consumer})
    except (TypeError, ValueError, RecursionError) as exc:
        return reject([_violation('gate_uncomputable', 'mechanical_case', f'the mechanical case could not be gated: {type(exc).__name__}')])
    if not ok:
        worker_violations: list[dict[str, Any]] = []
        for item in report['hard_rejects']:
            if item.get('audience') != AUDIENCE_WORKER:
                continue
            finding: dict[str, Any] = {key: str(item.get(key) or '') for key in ('gate', 'code', 'locus', 'detail')}
            expectation_ids = item.get('expectation_ids')
            if isinstance(expectation_ids, list):
                finding['expectation_ids'] = [str(value) for value in expectation_ids if str(value)]
            worker_violations.append(finding)
        return reject(worker_violations)
    exempt_violation = unique_exempt_blocks_submit(mechanical_case)
    if exempt_violation is not None:
        return reject([exempt_violation])
    try:
        from cex_core.engine.ist_core.compile_engine.engine_checkpoints import digest as _digest
        _accepted_sha256 = _digest(mechanical_case)
    except (RecursionError, TypeError, ValueError):
        _accepted_sha256 = ''
    session.record_mechanical_case_acceptance(attempt, mechanical_case, input_sha256=_accepted_sha256)
    measurements = report['measurements']
    from cex_core.engine.ist_core.compile_engine.engine_quarantine import session_admission_boundary
    with session_admission_boundary(session):
        minted = mint_and_land_mechanical_case(dict(mechanical_case), outputs_root / autoid / MECHANICAL_CASE_SIDECAR_NAME, capabilities_used=list(measurements['capabilities_used']), expanded_step_count=int(measurements['expanded_step_count']), check_point_count=int(measurements['check_point_count']), gate_report_sha256=gate_report_sha256)
    if minted.document is None:
        return reject([_violation(minted.code, {'seal_uncastable': 'seal', 'sealed_document_invalid': 'case', 'artifact_not_landed': 'artifact'}.get(minted.code, 'case'), minted.detail)])
    seal = minted.document['seal']
    return json.dumps({'schema': SUBMISSION_SCHEMA, 'status': 'sealed', 'autoid': autoid, 'artifact': f'workspace/outputs/{autoid}/{MECHANICAL_CASE_SIDECAR_NAME}', 'mechanical_case_sha256': seal['mechanical_case_sha256'], 'artifact_sha256': seal['mechanical_case_sha256'], 'violations': [], 'disclosures': repair_disclosures}, ensure_ascii=False, sort_keys=True, indent=2)
CONSISTENCY_ABANDON_VERDICT = _ABANDON_VERDICT
__all__ = ['ANSWERER_UNDETERMINED_CLAIM_KIND', 'CONSISTENCY_ABANDON_VERDICT', 'CONSISTENCY_INVALID', 'CONSISTENCY_NOT_APPLICABLE', 'CONSISTENCY_NOT_STAMPED', 'MechanicalCaseSubmissionArgs', 'SUBMISSION_SCHEMA', 'recompose_abandon_actionable', 'recompose_consistency_state', 'submit_mechanical_case', 'unique_exempt_blocks_submit']
