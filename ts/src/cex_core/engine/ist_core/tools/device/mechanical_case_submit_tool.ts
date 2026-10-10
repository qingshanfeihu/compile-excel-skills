import { MECHANICAL_CASE_SIDECAR_NAME } from "../../../engine_managed_outputs";
import { pyJsonDumps } from "../../../_py";

export const SUBMISSION_SCHEMA = "ist.mechanical-case-submission";
const _BLOCK_EDIT_REPAIR_CODES = new Set(["all_assertions_exempt", "blocks_invalid", "criterion_binding_missing", "criterion_lowering_mismatch", "criterion_status_claim_literalized", "criterion_status_target_unbound", "environment_unreachable_ip", "expectation_bijection_failed", "fixture_expected_not_config_backref", "missing_teardown", "no_assertion_in_case", "provenance_source_unresolved", "seal_uncastable", "trigger_reachability_invalid"]);
const _LEGAL_FORM_BY_CODE: Record<string, string> = { expectation_bijection_failed: "Put expectation_id and semantic_key on the assertion slot itself, then point one expectation_binding entry at that exact block/assert index. A normal Author assertion uses ref='intent:<expectation_id>'; a contract-authorized fixture uses ref='config_derived:<recipe>' and the sealed fixture binding_input.", seal_uncastable: "Include at least one assertion-producing block and bind every contract expectation to one of its assertion slots; the engine mints the seal.", no_assertion_in_case: "Add an assertion-producing block whose final expansion contains E='check_point'; an execution-only block is not an assertion.", provenance_source_unresolved: "Use one resolvable kind:locator on each command carrier and one authorized expected ref on each assertion; split commands that use different locators.", fixture_expected_not_config_backref: "Use ref='config_derived:<recipe>' and binding_input={rule_id: 'config.fixture-literal-backref', source_input: {operator, value, fixture_kind, config_block_index, config_command_index}}; the indices name an earlier CONFIG literal and operator/value equal the assertion tuple.", criterion_binding_missing: "Place the contract expectation_id and semantic_key on a legal assertion carrier, then add expectation_binding with its block_index and assert_index.", criterion_status_target_unbound: "Either bind the assertion to the value the nearest causal CONFIG step changes, or, when the causing step's own command line cannot contain that value, declare it: set state_change_step to that step's blocks[] index and write binding_disclosure — one user-facing Chinese sentence saying why the value is absent from that command line and how the step causes the change. The declaration is disclosed in the delivery report and verified on the device; it does not lift the always-true refusals.", criterion_state_change_step_invalid: "Point state_change_step at a blocks[] index that exists, or remove the declaration.", criterion_lowering_mismatch: "The materialization of a criterion status claim must be an exact criterion-check; do not strengthen or weaken it.", criterion_status_claim_literalized: "Keep the criterion status claim as a status check; do not rewrite it into a literal value assertion.", missing_teardown: "Add the build-bound paired teardown for the mutating configuration.", environment_unreachable_ip: "Bind the observation to a reachable target, or report the environment prerequisite gap.", trigger_reachability_invalid: "Fix the exact trigger/listener reachability pair.", blocks_invalid: "Repair the block structure at the named locus.", all_assertions_exempt: "Add at least one non-exempt check_point before submit." };
const _LEGAL_FORM_BY_GATE: Record<string, string> = { criterion_type_binding: "Bind each normalized criterion to one carrier/operator pair listed by this violation, preserving its contract identity.", dispatch_binding: "Preserve the dispatched autoid and submit the complete eight-section body; pass binding as an empty object for engine stamping.", expectation_bijection: "Give every contract expectation at least one distinct, identity-bearing assertion slot and no assertion identity outside the contract.", provenance_receipts: "Attach a resolvable authorized source to every command and expected carrier; device actual and history are not expected sources." };

const _MAX_CONTRACT_BYTES: number = require("../../../case_compiler/_sealed_io").CONTRACT_CARD_MAX_BYTES;
const _INTENT_STAMP_SCHEMA = "ist.intent-stamp-status";
const _BINDING_GATE = "dispatch_binding";
const _RECOMPOSE_CONSISTENCY_SCHEMA = "ist.recompose-consistency";
const _RECOMPOSE_CONSISTENCY_VERDICTS = new Set(["consistent", "mutually_exclusive", "underdetermined"]);
const _ABANDON_VERDICT = "mutually_exclusive";
export const CONSISTENCY_NOT_STAMPED = "not_stamped";
export const CONSISTENCY_NOT_APPLICABLE = "not_applicable";
export const CONSISTENCY_INVALID = "invalid";

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _isInt(v: any): boolean {
  return typeof v === "number" && Number.isInteger(v);
}

function _deepcopy<T>(v: T): T {
  return v === undefined ? v : JSON.parse(JSON.stringify(v));
}

export function _canonicalize_submission_blocks(mechanical_case: Record<string, any>): [Record<string, any> | null, string] {
  const blocks = mechanical_case.blocks;
  if (!Array.isArray(blocks)) {
    return [{ ...mechanical_case }, ""];
  }
  const { SSL_CERT_LOAD_KIND, split_ssl_certificate_load_blocks } = require("./emit_xlsx_tool");
  if (!blocks.some((block) => _isMapping(block) && String(block.kind ?? "").trim().toUpperCase() === SSL_CERT_LOAD_KIND)) {
    return [{ ...mechanical_case }, ""];
  }
  const expanded: Array<Record<string, any>> = [];
  const deferredCleanup: Array<Array<Record<string, any>>> = [];
  const engineEscapeHatches: Array<Record<string, any>> = [];
  const oldToNew = new Map<number, number | null>();

  const recordEngineSteps = (rows: Array<Record<string, any>>, start: number): void => {
    for (const [offset, lowered] of rows.entries()) {
      if (String(lowered.kind ?? "").trim().toUpperCase() !== "STEP") continue;
      engineEscapeHatches.push({ block_index: start + offset, capabilities_touched: [String(lowered.F ?? "")], reason: "Engine-owned SSL_CERT_LOAD standard-library lowering uses the exact framework method projected from excel_contract.json; the caller did not select a generic STEP escape hatch." });
    }
  };
  const bindingIndices = ((mechanical_case.expectation_binding ?? []) as any[]).filter((entry) => _isMapping(entry) && _isInt(entry.block_index)).map((entry) => entry.block_index as number);
  const businessAnchor = bindingIndices.length ? Math.max(...bindingIndices) : blocks.length - 1;

  const flushCleanup = (): void => {
    for (const cleanup of [...deferredCleanup].reverse()) {
      const start = expanded.length;
      expanded.push(...cleanup);
      recordEngineSteps(cleanup, start);
    }
    deferredCleanup.length = 0;
  };
  for (const [index, block] of blocks.entries()) {
    if (_isMapping(block) && String(block.kind ?? "").trim().toUpperCase() === SSL_CERT_LOAD_KIND) {
      oldToNew.set(index, null);
      const [setup, cleanup, error] = split_ssl_certificate_load_blocks(block);
      if (error || setup === null || setup === undefined || cleanup === null || cleanup === undefined) {
        return [null, `blocks[${index}](${SSL_CERT_LOAD_KIND}): ${error}`];
      }
      const start = expanded.length;
      const setupCopy = _deepcopy(setup);
      expanded.push(...setupCopy);
      recordEngineSteps(setupCopy, start);
      deferredCleanup.push(_deepcopy(cleanup));
    } else {
      oldToNew.set(index, expanded.length);
      expanded.push(_deepcopy(block));
    }
    if (index === businessAnchor) {
      flushCleanup();
    }
  }
  flushCleanup();
  const body = _deepcopy(mechanical_case);
  body.blocks = expanded;
  for (const field of ["expectation_binding", "escape_hatches"]) {
    const entries = body[field];
    if (!Array.isArray(entries)) continue;
    for (const [entryIndex, entry] of entries.entries()) {
      if (!_isMapping(entry)) continue;
      const oldIndex = entry.block_index;
      if (!_isInt(oldIndex) || !oldToNew.has(oldIndex)) continue;
      const newIndex = oldToNew.get(oldIndex);
      if (newIndex === null || newIndex === undefined) {
        return [null, `${field}[${entryIndex}].block_index points to SSL_CERT_LOAD block ${oldIndex}, which emits no assertion and cannot carry an expectation or escape-hatch entry`];
      }
      entry.block_index = newIndex;
    }
  }
  for (const [blockIndex, block] of (body.blocks as any[]).entries()) {
    if (!_isMapping(block)) continue;
    const answerer = block.answerer;
    if (!_isMapping(answerer)) continue;
    if (!["device", "fixture"].includes(String(answerer.kind ?? "").trim())) continue;
    const oldRef = answerer.ref;
    if (!_isInt(oldRef) || !oldToNew.has(oldRef)) continue;
    const newRef = oldToNew.get(oldRef);
    if (newRef === null || newRef === undefined) {
      return [null, `blocks[${blockIndex}].answerer.ref points to SSL_CERT_LOAD block ${oldRef}, which the engine lowers into setup/cleanup blocks; name the CONFIG block that creates the answering object instead`];
    }
    answerer.ref = newRef;
  }
  if (engineEscapeHatches.length && Array.isArray(body.escape_hatches)) {
    body.escape_hatches.push(...engineEscapeHatches);
  }
  return [body, ""];
}

function _violation(code: string, locus: string, detail: string, opts: { gate?: string } = {}): Record<string, string> {
  return { gate: opts.gate ?? _BINDING_GATE, code, locus, detail };
}

function _violations_with_legal_forms(violations: Array<Record<string, any>>): Array<Record<string, any>> {
  const rendered: Array<Record<string, any>> = [];
  for (const raw of violations) {
    const item = { ...raw };
    const code = String(item.code ?? "");
    const gate = String(item.gate ?? "");
    item.legal_form = _LEGAL_FORM_BY_CODE[code] ?? _LEGAL_FORM_BY_GATE[gate] ?? "Repair the exact locus while preserving every other sealed identity; resubmit the complete native JSON body for the engine to re-run all gates.";
    rendered.push(item);
  }
  return rendered;
}

export function unique_exempt_blocks_submit(mechanical_case: Record<string, any>): Record<string, string> | null {
  const { expand_blocks } = require("../../../case_compiler/blocks");
  const { EXEMPT_ISSUER_COMPILER, derive_mutation_requirements } = require("../../../case_compiler/mutation_testing");
  const [steps, , err] = expand_blocks([...(mechanical_case.blocks ?? [])]);
  if (err || !steps.length) return null;
  const checks = steps.filter((step: any) => String(step.E ?? "").trim() === "check_point");
  if (!checks.length || checks.some((step: any) => step.exempt !== true)) return null;
  const [requirements, deriveError] = derive_mutation_requirements(steps, null, { device_build: "" });
  if (!deriveError && requirements.length && requirements.every((item: any) => String(item.issuer ?? "") === EXEMPT_ISSUER_COMPILER)) {
    return null;
  }
  return _violation("all_assertions_exempt", "blocks", "every product assertion is Exempt; add at least one non-exempt check_point before submit. A full exemption passes only when the compiler recomputes and issues every one. An author-declared exemption, including non_readonly_probe kept on a window that can host a pre-state control, is rejected here.", { gate: "exempt_governance" });
}

function _repeated_code_disclosure(rejections: Array<Record<string, any>>): Record<string, any> | null {
  if (rejections.length < 3) return null;
  const tail = rejections.slice(-3);
  const attempts = tail.map((row) => Number(row.attempt ?? 0));
  if (!(attempts[1] === attempts[0] + 1 && attempts[2] === attempts[0] + 2)) return null;
  const codeSets = tail.map((row) => new Set<string>((row.violations ?? []).map((item: any) => String(item.code ?? "")).filter((c: string) => c)));
  if (codeSets.some((s) => s.size === 0)) return null;
  const repeated = [...codeSets[0]].filter((c) => codeSets.every((s) => s.has(c))).sort();
  if (!repeated.length) return null;
  return { code: "repeated_rejection_streak", codes: repeated, attempts, detail: `The same rule rejected attempts ${attempts[0]}-${attempts[attempts.length - 1]}: ${repeated.join(", ")}. Across the recorded corpus no dispatch that reached this streak ever produced an accepted case (0 of 46). Resubmitting this shape spends the remaining attempts without changing the outcome. Either write a different source-grounded form, or record what is missing through engine_gap and submit_authoring_account.` };
}

function _rejected(autoid: string, violations: Array<Record<string, any>>, opts: { disclosures?: Array<Record<string, any>> | null } = {}): string {
  return pyJsonDumps({ schema: SUBMISSION_SCHEMA, status: "rejected", autoid, artifact: null, mechanical_case_sha256: null, artifact_sha256: null, violations: _violations_with_legal_forms(violations), disclosures: [...(opts.disclosures ?? [])] }, { ensure_ascii: false, sort_keys: true, indent: 2 });
}

const _BODY_PAYLOAD_STREAKS = new Map<string, number>();

function _bumpBodyPayloadStreak(key: string): number {
  const value = (_BODY_PAYLOAD_STREAKS.get(key) ?? 0) + 1;
  _BODY_PAYLOAD_STREAKS.set(key, value);
  return value;
}

function _resetBodyPayloadStreak(key: string): void {
  _BODY_PAYLOAD_STREAKS.delete(key);
}

function _bodyPayloadStreakKey(autoid: string): string {
  const { current_worker_device_session } = require("../worker_device_context");
  const session = current_worker_device_session();
  return [String(session?.batch_run_id ?? ""), String(session?.dispatch_id ?? ""), autoid].join(":");
}

function _bodyPayloadReject(autoid: string, code: string, locus: string, detail: string, opts: { streak?: number | null } = {}): string {
  const streak = opts.streak ?? null;
  if (streak !== null && streak >= 2) {
    detail += " → Two consecutive payload-channel failures were observed; their cause is not established. Do not repeat the unchanged payload. Use an available alternative within the existing budget, or record the unresolved issue through engine_gap and finish per your report contract. This receipt establishes neither content validity nor fault ownership.";
  }
  return _rejected(autoid, [_violation(code, locus, detail)]);
}

function _resolveSubmissionBody(mechanical_case: any, mechanical_case_path: string, opts: { autoid: string }): [any, string] {
  const autoid = opts.autoid;
  const reissueHint = `Preferred fix: fs_write the complete submission body as one JSON document under workspace/outputs/${autoid}/ (e.g. mechanical_case_body.json), then call submit_mechanical_case again with mechanical_case_path=that path — the file channel bypasses argument serialization entirely. Re-issuing one compact native object also works, but every verbatim atom must stay exactly as authored.`;
  if (_isMapping(mechanical_case)) {
    return [mechanical_case, ""];
  }
  let text = "";
  let locus = "mechanical_case";
  if ((mechanical_case_path ?? "").trim()) {
    locus = "mechanical_case_path";
    try {
      const _sealed_output = require("./_sealed_output");
      const target = _sealed_output.scoped_output_path(mechanical_case_path.trim());
      const caseRoot = _sealed_output.case_output_path(autoid, ".payload-channel-scope").parent;
      target.relative_to(caseRoot);
      text = (_sealed_output.read_bytes(target, { max_bytes: 16 * 1024 * 1024 }) as Buffer).toString("utf8");
    } catch (exc) {
      return [null, _bodyPayloadReject(autoid, "body_path_unreadable", "mechanical_case_path", `the mechanical_case_path file could not be read (${(exc as any)?.constructor?.name ?? "Error"}); it must be a regular JSON file inside the case's outputs directory.`, { streak: _bumpBodyPayloadStreak(_bodyPayloadStreakKey(autoid)) })];
    }
  } else if (typeof mechanical_case === "string" && mechanical_case.trim()) {
    text = mechanical_case;
  }
  if (!text.trim()) {
    return [null, _bodyPayloadReject(autoid, "body_payload_empty", "mechanical_case", "no payload channel carried content; the cause is not established. " + reissueHint, { streak: _bumpBodyPayloadStreak(_bodyPayloadStreakKey(autoid)) })];
  }
  let parsed: any;
  try {
    const { validate_json_budget } = require("../../../case_compiler/_sealed_io");
    if (Buffer.byteLength(text, "utf8") > 16 * 1024 * 1024) {
      throw new Error("payload exceeds the byte budget");
    }
    validate_json_budget(text, { errorType: Error, message: "payload exceeds the JSON structure budget" });
    parsed = JSON.parse(text, (_key, value) => {
      if (typeof value === "number" && !Number.isFinite(value)) throw new Error("non-finite constant");
      if (value !== null && typeof value === "object" && !Array.isArray(value)) {
        const keys = Object.keys(value);
        if (new Set(keys).size !== keys.length) throw new Error("duplicate key");
      }
      return value;
    });
  } catch (exc) {
    return [null, _bodyPayloadReject(autoid, "body_payload_unparseable", locus, `the payload arrived as text that is not valid JSON (${(exc as any)?.constructor?.name ?? "Error"}); the cause is not established. ` + reissueHint, { streak: _bumpBodyPayloadStreak(_bodyPayloadStreakKey(autoid)) })];
  }
  if (!_isMapping(parsed) || Object.keys(parsed).length === 0) {
    return [null, _bodyPayloadReject(autoid, "body_payload_unparseable", locus, `the payload must be a non-empty JSON object (the ist.mechanical-case submission body); got ${parsed === null ? "null" : Array.isArray(parsed) ? "Array" : typeof parsed}. ` + reissueHint, { streak: _bumpBodyPayloadStreak(_bodyPayloadStreakKey(autoid)) })];
  }
  return [parsed, ""];
}

export const ANSWERER_UNDETERMINED_CLAIM_KIND = "answerer_undetermined";

function _routeAnswererUndetermined(autoid: string, mechanical_case: Record<string, any>): string | null {
  const { _DUT_HOSTS } = require("../../../case_compiler/blocks");
  const blocks = mechanical_case.blocks;
  if (!Array.isArray(blocks)) return null;
  const hits: Array<[number, string, string]> = [];
  for (const [index, block] of blocks.entries()) {
    if (!_isMapping(block)) continue;
    if (!["OBSERVE_ASSERT", "OBSERVE_EXIT"].includes(String(block.kind ?? "").trim().toUpperCase())) continue;
    const host = String(block.host ?? "").trim();
    if (_DUT_HOSTS.has ? _DUT_HOSTS.has(host) : (Array.isArray(_DUT_HOSTS) ? _DUT_HOSTS.includes(host) : host in _DUT_HOSTS)) continue;
    const answerer = block.answerer;
    if (!_isMapping(answerer)) continue;
    if (String(answerer.kind ?? "").trim() !== "undetermined") continue;
    const note = String(answerer.note ?? "").trim();
    if (!note) continue;
    hits.push([index, host, note]);
  }
  if (!hits.length) return null;
  const { validate_user_facing_text } = require("../compile_engine/user_text_contract");
  const textValidation = validate_user_facing_text(Object.fromEntries(hits.map(([index, , note]) => [`blocks[${index}].answerer.note`, note])));
  if (!textValidation.accepted) {
    const details = textValidation.violations.map((item: any) => `${item.field}=${(item.terms as string[]).join(",")}`).join(", ");
    return _rejected(autoid, [_violation("answerer_note_not_user_facing", "blocks[].answerer.note", `the undetermined-answerer note lands verbatim in the user's decision panel, so it must be user-facing Chinese without exact internal terms (${details})`, { gate: "answerer_statement" })]);
  }
  const loci = hits.map(([index]) => `blocks[${index}].answerer`);
  const notes = [...new Set(hits.map(([, , note]) => note))];
  const entry = { reason: "交互观测步的应答方没有来源可定：" + notes.join("；"), loci, observation_hosts: [...new Set(hits.map(([, host]) => host))].sort(), notes };
  const { land_answerer_undetermined_claim } = require("./emit_xlsx_tool");
  const landed = land_answerer_undetermined_claim(autoid, entry);
  if (!landed) {
    return _rejected(autoid, [_violation("answerer_claim_landing_failed", "needs_decision.json", "the typed answerer_undetermined claim could not be persisted; retry the submission in this same turn before finishing", { gate: "answerer_statement" })]);
  }
  return pyJsonDumps({ schema: SUBMISSION_SCHEMA, status: "routed", autoid, claim_kind: ANSWERER_UNDETERMINED_CLAIM_KIND, routed: true, ledger: `workspace/outputs/${autoid}/needs_decision.json`, loci, detail: "The engine landed a typed answerer_undetermined user-decision claim for the traffic-driving observation block(s) at " + loci.join(", ") + "; nothing was sealed and this case now waits on the user's answer. Do not resubmit the unanswered chain in this dispatch: finish with status=needs_user_decision and carry the pending claim in summary.", violations: [] }, { ensure_ascii: false, sort_keys: true, indent: 2 });
}

function _boundedJson(path: any, opts: { max_bytes: number }): [Record<string, any> | null, Buffer] {
  const { read_regular_nofollow, validate_json_budget } = require("../../../case_compiler/_sealed_io");
  try {
    const raw = read_regular_nofollow(path._p ?? String(path), { errorType: Error, invalid_message: "path is invalid", directory_message: "directory is unavailable", open_message: "file is unavailable", bounds_message: "file exceeds the byte budget", changed_message: "file changed while being read", max_bytes: opts.max_bytes }) as Buffer;
    validate_json_budget(raw, { errorType: Error, message: "file exceeds the JSON structure budget" });
    const payload = JSON.parse(raw.toString("utf8"));
    return [_isMapping(payload) ? payload : null, raw];
  } catch {
    return [null, Buffer.alloc(0)];
  }
}

function _intentJson(path: any, outputs_root: any): Record<string, any> | null {
  const { ContractError, read_intent_json } = require("../../../case_compiler/contract_entry");
  try {
    const [payload] = read_intent_json(path, { trusted_root: outputs_root });
    return payload;
  } catch (exc) {
    if (exc instanceof ContractError) return null;
    return null;
  }
}

function _trustedMindmapSourceSha256(contract: Record<string, any>, opts: { session: any; project_root: any }): string {
  const { session, project_root } = opts;
  const sourceShas = new Set<string>();
  for (const item of contract.expectations ?? []) {
    if (!_isMapping(item)) continue;
    const claim = item.author_claim;
    if (_isMapping(claim) && /^[0-9a-f]{64}$/.test(String(claim.source_sha256 ?? ""))) {
      sourceShas.add(String(claim.source_sha256));
    }
  }
  if (sourceShas.size === 1) {
    return [...sourceShas][0];
  }
  const manifestRef = String(session.source_manifest_ref ?? "");
  const manifestSha = String(session.source_manifest_sha256 ?? "");
  if (!manifestRef || !/^[0-9a-f]{64}$/.test(manifestSha)) return "";
  const [manifest, raw] = _boundedJson(project_root.joinpath ? project_root.joinpath(manifestRef) : manifestRef, { max_bytes: 16 * 1024 * 1024 });
  if (!_isMapping(manifest)) return "";
  const { sha256_bytes } = require("../../../case_compiler/_sealed_io");
  const sourceSha = String(manifest.source_sha256 ?? "");
  if (sha256_bytes(raw) !== manifestSha || !/^[0-9a-f]{64}$/.test(sourceSha)) return "";
  return sourceSha;
}

export function _stampEngineBinding(
  mechanical_case: Record<string, any>,
  opts: { contract: Record<string, any>; contract_sha256: string; consistency_contract_sha256: string | null; session: any; project_root: any },
): [Record<string, any>, Array<Record<string, string>>] {
  let binding = mechanical_case.binding;
  if (binding === null || binding === undefined) binding = {};
  if (!_isMapping(binding)) {
    return [mechanical_case, []];
  }
  const mindmapSha = _trustedMindmapSourceSha256(opts.contract, { session: opts.session, project_root: opts.project_root });
  const expected: Record<string, any> = {
    contract_sha256: opts.contract_sha256,
    consistency_contract_sha256: opts.consistency_contract_sha256,
    mindmap_source_sha256: mindmapSha,
    capability_generation_id: String(opts.session.capability_generation_id ?? ""),
    capability_projection_sha256: String(opts.session.capability_projection_sha256 ?? ""),
    authored_round: Number(opts.session.authored_round ?? 1) || 1,
  };
  const missingEngine = Object.entries(expected).filter(([key, value]) => key !== "consistency_contract_sha256" && (value === null || value === undefined || value === "")).map(([key]) => key);
  if (missingEngine.length) {
    return [mechanical_case, [_violation("engine_binding_unavailable", "binding", "the engine dispatch cannot stamp required binding field(s): " + missingEngine.sort().join(", "))]];
  }
  const stampedBinding = { ...binding };
  const violations: Array<Record<string, string>> = [];
  for (const [key, value] of Object.entries(expected)) {
    const declared = stampedBinding[key];
    if (declared === null || declared === undefined || declared === "") {
      stampedBinding[key] = value;
      continue;
    }
    if (declared !== value) {
      violations.push(_violation(key === "consistency_contract_sha256" ? "consistency_contract_identity_drift" : "engine_binding_drift", `binding.${key}`, `the caller declared ${JSON.stringify(declared)}, but the trusted dispatch binds ${JSON.stringify(value)}; omit this engine-owned field instead of copying it`));
    }
  }
  const stamped = { ...mechanical_case, binding: stampedBinding };
  return [stamped, violations];
}

function _frozenContract(autoid: string, outputs_root: any, project_root: any): [Record<string, any> | null, string, Array<Record<string, string>>] {
  const caseDir = outputs_root.joinpath ? outputs_root.joinpath(autoid) : outputs_root;
  const [stamp] = _boundedJson(caseDir.joinpath ? caseDir.joinpath("intent_stamp_status.json") : "", { max_bytes: 64 * 1024 });
  if (!_isMapping(stamp) || stamp.schema !== _INTENT_STAMP_SCHEMA || String(stamp.autoid ?? "") !== autoid || String(stamp.status ?? "") !== "complete") {
    return [null, "", [_violation("intent_stamp_incomplete", "intent_stamp_status.json", `the engine has no complete intent/spec identity stamp for case ${autoid}; the mechanical case submission rules have nothing to reconcile its expectations against`)]];
  }
  const intent = _intentJson(caseDir.joinpath("intent.json"), outputs_root);
  if (!_isMapping(intent) || String(intent.autoid ?? "") !== autoid) {
    return [null, "", [_violation("intent_stamp_incomplete", "intent.json", `the stamped intent for case ${autoid} is unreadable or carries another case identity`)]];
  }
  const declaredSha = String(intent.typed_expectation_contract_sha256 ?? "").trim();
  const declaredRel = String(intent.typed_expectation_contract_path ?? "").trim();
  if (!declaredSha || !declaredRel) {
    return [null, "", [_violation("frozen_contract_absent", "intent.json", `case ${autoid} has no frozen expectation contract; a mechanical case is compiled against contract-card expectations, so there is nothing to redeem. Report the gap instead of inventing expectations.`)]];
  }
  const { lexical_path_inside_root, sha256_bytes } = require("../../../case_compiler/_sealed_io");
  let contractPath: string;
  try {
    contractPath = lexical_path_inside_root(project_root.joinpath ? project_root.joinpath(declaredRel)._p : declaredRel, outputs_root._p ?? String(outputs_root), { errorType: Error, traversal_message: "contract path traversal is forbidden", outside_message: "contract path escaped the outputs root" });
  } catch (exc) {
    return [null, "", [_violation("frozen_contract_unreadable", "intent.json", `the stamped contract path for case ${autoid} is not inside outputs: ${exc}`)]];
  }
  const [contract, raw] = _boundedJson(contractPath, { max_bytes: _MAX_CONTRACT_BYTES });
  if (contract === null) {
    return [null, "", [_violation("frozen_contract_unreadable", "contracts", `the frozen contract card for case ${autoid} cannot be read`)]];
  }
  const contractSha256 = sha256_bytes(raw);
  if (contractSha256 !== declaredSha) {
    return [null, "", [_violation("frozen_contract_drift", "contracts", `the contract card on disk hashes to ${contractSha256} but the engine stamped ${declaredSha} for case ${autoid}`)]];
  }
  return [contract, contractSha256, []];
}

export function recompose_consistency_state(contract: any): string {
  if (!_isMapping(contract) || !("consistency" in contract)) return CONSISTENCY_NOT_STAMPED;
  const conclusion = contract.consistency;
  if (conclusion === null || conclusion === undefined) return CONSISTENCY_NOT_APPLICABLE;
  if (!_isMapping(conclusion) || conclusion.schema !== _RECOMPOSE_CONSISTENCY_SCHEMA) return CONSISTENCY_INVALID;
  const verdict = conclusion.verdict;
  if (!_RECOMPOSE_CONSISTENCY_VERDICTS.has(String(verdict))) return CONSISTENCY_INVALID;
  return String(verdict);
}

export const RECOMPOSE_S1_EVIDENCE_FIELDS = ["spec_quote", "case_quote", "spec_locator", "case_locator", "incompatibility"];

export function recompose_abandon_blocker(contract: any, opts: { spec_surface_present: boolean }): string {
  if (recompose_consistency_state(contract) !== _ABANDON_VERDICT) {
    return "not_mutually_exclusive";
  }
  if (!opts.spec_surface_present) {
    return "no_comparable_spec_surface";
  }
  const conclusion = _isMapping(contract) ? contract.consistency : null;
  if (!_isMapping(conclusion) || RECOMPOSE_S1_EVIDENCE_FIELDS.some((field) => !String(conclusion[field] ?? "").trim())) {
    return "scenario1_evidence_incomplete";
  }
  return "";
}

export function recompose_abandon_actionable(contract: any, opts: { spec_surface_present: boolean }): boolean {
  return !recompose_abandon_blocker(contract, { spec_surface_present: opts.spec_surface_present });
}

function _recomposeConsistencyViolation(contract: Record<string, any>, autoid: string, opts: { spec_surface_present: boolean }): Record<string, string> | null {
  const state = recompose_consistency_state(contract);
  if (state === CONSISTENCY_INVALID) {
    return _violation("consistency_conclusion_invalid", "contracts", `the frozen contract card for case ${autoid} carries a consistency conclusion that is not a ${_RECOMPOSE_CONSISTENCY_SCHEMA} object with a verdict of consistent, mutually_exclusive, or underdetermined. The conclusion is engine-stamped, so this is not repairable from here: report the malformed stamp instead of resubmitting.`);
  }
  if (recompose_abandon_actionable(contract, { spec_surface_present: opts.spec_surface_present })) {
    return _violation("case_abandoned_by_consistency", "contracts", `the recompose stage judged case ${autoid} and its bound specification mutually exclusive on two complete sources, which abandons the case; no mechanical case is accepted for it. A case whose expectation cannot be derived because a precondition is missing is a different conclusion (underdetermined) and does not reach this rule — there, the procedure gets the missing precondition steps. Nothing here is repairable by resubmitting.`);
  }
  return null;
}

export function submit_mechanical_case(mechanical_case: any = "", mechanical_case_path = ""): string {
  const { mint_and_land_mechanical_case } = require("../../../case_compiler/mechanical_case");
  const { AUDIENCE_WORKER, gate_report_digest, run_mechanical_case_gate } = require("../../../case_compiler/mechanical_case_gate");
  const sh = require("../compile_engine/_shared");
  const { current_worker_device_session } = require("../worker_device_context");
  const session = current_worker_device_session();
  const autoid = session !== null && session !== undefined ? String(session.autoid ?? "") : "";
  if (!autoid) {
    return _rejected("", [_violation("no_engine_dispatch", "session", "submit_mechanical_case only runs inside an engine-dispatched compile worker with a bound case identity")]);
  }
  const [resolvedBody, payloadError] = _resolveSubmissionBody(mechanical_case, mechanical_case_path, { autoid });
  if (payloadError) return payloadError;
  mechanical_case = resolvedBody;
  _resetBodyPayloadStreak(_bodyPayloadStreakKey(autoid));
  const attempt = session.begin_mechanical_case_submission();
  const repairDisclosures: Array<Record<string, any>> = [];

  const reject = (violations: Array<Record<string, any>>): string => {
    const formatted = _violations_with_legal_forms(violations);
    const { rule_identity } = require("../compile_engine/authoring_evidence");
    const { digest } = require("../compile_engine/engine_checkpoints");
    let inputSha256 = "";
    let identityError = "";
    try {
      inputSha256 = digest(mechanical_case);
    } catch (exc) {
      identityError = (exc as any)?.constructor?.name ?? "Error";
    }
    session.record_mechanical_case_rejection(attempt, formatted, { input_sha256: inputSha256, rule_identity: rule_identity(), mechanical_case });
    const streak = _repeated_code_disclosure([...session.mechanical_case_rejections]);
    const payload = JSON.parse(_rejected(autoid, formatted, { disclosures: [...repairDisclosures, ...(streak ? [streak] : [])] }));
    if (identityError) {
      payload.input_identity = { status: "unverified", input_sha256: "", reason: "canonical_serialization_failed", exception_type: identityError, detail: "The rejected input could not be canonically hashed; no input identity was issued." };
    }
    const structuralStreak = session.structural_rejection_streak();
    if (structuralStreak) {
      payload.structural_rejection = { ...structuralStreak, instruction: `the same rule (${structuralStreak.gate}) has rejected the same code (${structuralStreak.code}) on consecutive submissions; resubmitting the same shape will not change the outcome — stop retrying, report the engine-side criterion gap in your reply` };
    }
    return pyJsonDumps(payload, { ensure_ascii: false, sort_keys: true, indent: 2 });
  };
  const deviceBuild = String(session.capability_build ?? "").trim();
  if (!deviceBuild) {
    return reject([_violation("capability_build_unbound", "session.capability_build", "the engine dispatch did not bind a capability build; submission refuses to select the process-wide active command tree")]);
  }
  if (!_isMapping(mechanical_case)) {
    return reject([_violation("not_an_object", "mechanical_case", "mechanical_case must be a native JSON object, not a serialized string")]);
  }
  const declaredAutoid = String(mechanical_case.autoid ?? "");
  if (declaredAutoid !== autoid) {
    return reject([_violation("autoid_not_dispatched", "autoid", `this fork is dispatched for case ${autoid}; the body declares ${JSON.stringify(declaredAutoid)}`)]);
  }
  const [restoredBody, restoreError, repairDisclosure] = session.prepare_mechanical_case_envelope_sections(mechanical_case, { block_edit_authorization_codes: _BLOCK_EDIT_REPAIR_CODES });
  if (_isMapping(repairDisclosure)) {
    repairDisclosures.push(repairDisclosure);
    session.record_mechanical_case_repair_disclosure(attempt, repairDisclosure);
  }
  if (restoredBody === null || restoredBody === undefined) {
    let code: string;
    let detail: string;
    if (restoreError === "blocks_change_not_authorized") {
      code = "submission_repair_blocks_change_not_authorized";
      detail = "blocks changed while an index-bearing envelope section was omitted, but the previous rejection did not cite a stable block-edit violation. Keep blocks byte-identical for omission-based restoration, or resubmit the complete expectation_binding and escape_hatches for the new blocks.";
    } else if (["changed_blocks_require_expectation_binding", "changed_blocks_require_escape_hatches"].includes(String(restoreError))) {
      code = "submission_repair_envelope_rebind_required";
      detail = `a cited gate permits this blocks edit, but an omitted index-bearing section no longer resolves mechanically against the changed array. Resubmit the complete expectation_binding and escape_hatches for the new blocks (${restoreError}).`;
    } else {
      code = restoreError === "blocks_changed" ? "submission_repair_blocks_changed" : "submission_repair_envelope_unavailable";
      detail = `expectation_binding or escape_hatches was omitted. The tool may restore those index-bearing sections only from this fork's previous complete submission when every reused index can be revalidated; repair the full envelope instead (${restoreError}).`;
    }
    return reject([_violation(code, "mechanical_case", detail)]);
  }
  mechanical_case = restoredBody;
  session.remember_mechanical_case_submission_body(mechanical_case);
  const outputsRoot = sh.outputs_root();
  const [contract, contractSha256, contractViolations] = _frozenContract(autoid, outputsRoot, sh.project_root());
  if (contract === null) {
    return reject(contractViolations);
  }
  const intent = _intentJson(outputsRoot.joinpath(autoid, "intent.json"), outputsRoot);
  let requirementProof: Record<string, any>;
  let consistencyRecord: any;
  try {
    const { NOT_APPLICABLE, REQUIRED, ConsistencyRequirementError, batch_name_from_contract_ref, validate_consistency_requirement } = require("../compile_engine/consistency_requirement");
    const { ConsistencyLedgerError, current_consistency_dispatch, read_consistency_dispatch_ledger } = require("./consistency_receipt");
    const consistencyScope = current_consistency_dispatch();
    const dispatchId = String(session.dispatch_id ?? "");
    if (consistencyScope.autoid !== autoid || consistencyScope.dispatch_id !== dispatchId || String(consistencyScope.outputs_root) !== String(outputsRoot)) {
      throw new ConsistencyLedgerError("consistency dispatch scope identity drift");
    }
    const baseContractRef = String(consistencyScope.source_context?.base_contract_ref ?? "");
    const batchName = batch_name_from_contract_ref({ project_root: sh.project_root(), outputs_root: outputsRoot, autoid, contract_ref: baseContractRef });
    requirementProof = validate_consistency_requirement({ outputs_root: outputsRoot, project_root: sh.project_root(), batch_name: batchName, autoid, intent: _isMapping(intent) ? intent : {} });
    if (consistencyScope.source_context?.base_contract_sha256 !== contractSha256 || requirementProof.base_contract_sha256 !== contractSha256) {
      throw new ConsistencyRequirementError("intent_contract_identity_mismatch", "trusted dispatch base contract differs from the projection receipt");
    }
    consistencyRecord = read_consistency_dispatch_ledger(outputsRoot, autoid, dispatchId).latest();
    void NOT_APPLICABLE;
    void REQUIRED;
  } catch (exc) {
    const { ConsistencyRequirementError } = require("../compile_engine/consistency_requirement");
    if (exc instanceof ConsistencyRequirementError) {
      return reject([_violation((exc as any).code, "consistency_requirement", (exc as any).detail)]);
    }
    return reject([_violation("consistency_dispatch_scope_invalid", "consistency_requirement", String(exc instanceof Error ? exc.message : exc))]);
  }
  const { NOT_APPLICABLE, REQUIRED } = require("../compile_engine/consistency_requirement");
  const abandoned = _recomposeConsistencyViolation(contract, autoid, { spec_surface_present: requirementProof.requirement !== NOT_APPLICABLE });
  if (abandoned !== null) {
    return reject([abandoned]);
  }
  const consistencyRequired = requirementProof.requirement === REQUIRED;
  let consistencyContract: any = null;
  let consistencyContractSha256 = "";
  if (consistencyRequired) {
    const consistencyMaterial = _isMapping(consistencyRecord) ? consistencyRecord.material : null;
    if (!_isMapping(consistencyMaterial)) {
      return reject([_violation("consistency_verdict_missing", "consistency_verdict", "step 3 (case versus bound product specification consistency) must produce an accepted verdict before step 4 submits a mechanical case")]);
    }
    if (String(consistencyMaterial.verdict ?? "") === "conflict") {
      return reject([_violation("case_abandoned_by_consistency", "consistency_verdict", "an accepted consistency verdict on this dispatch says the case and its bound specification cannot both hold, so the case is abandoned at case level and no mechanical case is accepted. Resubmitting changes nothing here.")]);
    }
    if (String(consistencyMaterial.verdict ?? "") !== "consistent") {
      return reject([_violation("consistency_verdict_missing", "consistency_verdict", "the latest consistency credential has no accepted closed verdict")]);
    }
    try {
      const { load_consistency_contract, validate_consistency_contract } = require("../../../case_compiler/consistency_contract");
      [consistencyContract, consistencyContractSha256] = load_consistency_contract(outputsRoot.joinpath(autoid, "consistency_contract.json"));
      const { current_consistency_dispatch, ConsistencyLedgerError } = require("./consistency_receipt");
      const scope = current_consistency_dispatch();
      const overlayError = validate_consistency_contract(consistencyContract, { base_contract: contract, base_contract_sha256: contractSha256, accepted_material: consistencyMaterial, consistency_receipt_sha256: String(consistencyRecord.receipt_sha256 ?? ""), machine_case: _isMapping(scope.source_context?.case) ? scope.source_context.case : null });
      if (overlayError) {
        throw new ConsistencyLedgerError(overlayError);
      }
    } catch {
      return reject([_violation("consistency_contract_invalid", "consistency_contract.json", "the linked consistency contract is absent or does not match this dispatch, accepted material, and frozen base contract")]);
    }
  } else {
    if (consistencyRecord !== null && consistencyRecord !== undefined) {
      return reject([_violation("consistency_not_applicable_receipt_present", "consistency_requirement", "the engine stamped this case not-applicable but the dispatch ledger contains a consistency verdict")]);
    }
    const declaredOverlay = _isMapping(mechanical_case.binding) ? mechanical_case.binding.consistency_contract_sha256 : null;
    if (declaredOverlay !== null && declaredOverlay !== undefined) {
      return reject([_violation("consistency_not_applicable_binding_present", "binding.consistency_contract_sha256", "the engine stamped no governing specification comparison; the mechanical binding must carry null")]);
    }
  }
  {
    const [stamped, bindingViolations] = _stampEngineBinding(mechanical_case, { contract, contract_sha256: contractSha256, consistency_contract_sha256: consistencyRequired ? consistencyContractSha256 : null, session, project_root: sh.project_root() });
    if (bindingViolations.length) {
      return reject(bindingViolations);
    }
    mechanical_case = stamped;
  }
  {
    const [canonicalized, canonicalizationError] = _canonicalize_submission_blocks(mechanical_case);
    if (canonicalized === null) {
      return reject([_violation("ssl_cert_load_invalid", "blocks", canonicalizationError, { gate: "mechanical_case_body" })]);
    }
    mechanical_case = canonicalized;
  }
  const routed = _routeAnswererUndetermined(autoid, mechanical_case);
  if (routed !== null) {
    return routed;
  }
  let ok: boolean;
  let report: Record<string, any>;
  let gateReportSha256: string;
  try {
    [ok, report] = run_mechanical_case_gate(mechanical_case, contract, { contract_sha256: contractSha256, device_build: deviceBuild, outputs_root: outputsRoot, consistency_contract: consistencyContract, consistency_contract_sha256: consistencyContractSha256, consistency_required: consistencyRequired, source_case_slice: { ...(session.source_case_slice ?? {}) }, source_case_slice_sha256: String(session.source_case_slice_sha256 ?? "") });
    gateReportSha256 = gate_report_digest(report);
    const { ADVISE_CODE_CONSUMERS } = require("../../../case_compiler/mechanical_case_gate");
    for (const item of report.advisories ?? []) {
      const code = String(item.code ?? "");
      let consumer = ADVISE_CODE_CONSUMERS[code];
      if (consumer === null && consumer === undefined && code.startsWith("gate_disabled:")) {
        consumer = "gate_advisory";
      }
      if (consumer && consumer !== "no-consumer") {
        session.record_gate_advisory({ gate: String(item.gate ?? ""), code, locus: String(item.locus ?? ""), detail: String(item.detail ?? ""), fact_event: consumer });
      }
    }
  } catch (exc) {
    return reject([_violation("gate_uncomputable", "mechanical_case", `the mechanical case could not be gated: ${(exc as any)?.constructor?.name ?? "Error"}`)]);
  }
  if (!ok) {
    const workerViolations: Array<Record<string, any>> = [];
    for (const item of report.hard_rejects) {
      if (item.audience !== AUDIENCE_WORKER) continue;
      const finding: Record<string, any> = {};
      for (const key of ["gate", "code", "locus", "detail"]) {
        finding[key] = String(item[key] ?? "");
      }
      const expectationIds = item.expectation_ids;
      if (Array.isArray(expectationIds)) {
        finding.expectation_ids = expectationIds.map((v: any) => String(v)).filter((v: string) => v);
      }
      workerViolations.push(finding);
    }
    return reject(workerViolations);
  }
  const exemptViolation = unique_exempt_blocks_submit(mechanical_case);
  if (exemptViolation !== null) {
    return reject([exemptViolation]);
  }
  let acceptedSha256 = "";
  try {
    const { digest: _digest } = require("../compile_engine/engine_checkpoints");
    acceptedSha256 = _digest(mechanical_case);
  } catch {
    acceptedSha256 = "";
  }
  session.record_mechanical_case_acceptance(attempt, mechanical_case, { input_sha256: acceptedSha256 });
  const measurements = report.measurements;
  const { session_admission_boundary } = require("../compile_engine/engine_quarantine");
  let minted: any;
  const boundary = session_admission_boundary(session);
  try {
    if (boundary && typeof boundary.enter === "function") boundary.enter();
    minted = mint_and_land_mechanical_case({ ...mechanical_case }, outputsRoot.joinpath(autoid, MECHANICAL_CASE_SIDECAR_NAME), { capabilities_used: [...measurements.capabilities_used], expanded_step_count: Number(measurements.expanded_step_count), check_point_count: Number(measurements.check_point_count), gate_report_sha256: gateReportSha256 });
  } finally {
    if (boundary && typeof boundary.exit === "function") boundary.exit();
  }
  if (minted.document === null || minted.document === undefined) {
    const locusMap: Record<string, string> = { seal_uncastable: "seal", sealed_document_invalid: "case", artifact_not_landed: "artifact" };
    return reject([_violation(minted.code, locusMap[minted.code] ?? "case", minted.detail)]);
  }
  const seal = minted.document.seal;
  return pyJsonDumps({ schema: SUBMISSION_SCHEMA, status: "sealed", autoid, artifact: `workspace/outputs/${autoid}/${MECHANICAL_CASE_SIDECAR_NAME}`, mechanical_case_sha256: seal.mechanical_case_sha256, artifact_sha256: seal.mechanical_case_sha256, violations: [], disclosures: repairDisclosures }, { ensure_ascii: false, sort_keys: true, indent: 2 });
}

export const CONSISTENCY_ABANDON_VERDICT = _ABANDON_VERDICT;

export const _stamp_engine_binding = _stampEngineBinding;
