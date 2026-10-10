import { pyJsonDumps } from "../../../_py";
import { P } from "../../../_py";

const _PARTS_COMPLETE_NEXT = "All dispatched cases are recorded. The only legal next action is to call submit_machine_mindmap now to seal; further submit_machine_mindmap_cases calls will be rejected.";
const _SHARD_COMPLETE_NEXT = "Every case assigned to this dispatch is recorded. Do not call submit_machine_mindmap: sibling shards may still be running and the engine seals the batch itself once the whole set is recorded. Finish your turn with the Chinese report.";

const logger = { warning: (..._args: any[]) => {} };

function _scopeOutstanding(ledgerMissing: readonly string[], assigned: readonly string[]): string[] {
  if (!assigned.length) return [...ledgerMissing];
  const scope = new Set(assigned);
  return ledgerMissing.filter((aid) => scope.has(aid));
}

export function current_dispatch_outstanding_autoids(): readonly string[] | null {
  const { current_recompose_assignment, current_recompose_dispatch } = require("./recompose_submission");
  const { read_machine_mindmap_parts } = require("./recompose_parts");
  try {
    const [outputsRoot, outName] = current_recompose_dispatch();
    const assigned = current_recompose_assignment();
    const ledger = read_machine_mindmap_parts(outputsRoot, outName);
    return _scopeOutstanding(ledger.missing_autoids, assigned);
  } catch {
    return null;
  }
}

function _rejected(schema: string, violations: Array<Record<string, any>>): string {
  return pyJsonDumps({ schema, status: "rejected", violations }, { ensure_ascii: false, sort_keys: true, indent: 2 });
}

const _SUBMIT_PAYLOAD_STREAKS = new Map<string, number>();

function _bumpSubmitPayloadStreak(key: string): number {
  const value = (_SUBMIT_PAYLOAD_STREAKS.get(key) ?? 0) + 1;
  _SUBMIT_PAYLOAD_STREAKS.set(key, value);
  return value;
}

function _resetSubmitPayloadStreak(key: string): void {
  _SUBMIT_PAYLOAD_STREAKS.delete(key);
}

function _payloadReject(code: string, locus: string, detail: string, opts: { streak?: number | null; json_decode_error?: Record<string, any> | null } = {}): [null, string] {
  const streak = opts.streak ?? null;
  if (streak !== null && streak >= 2) {
    detail += " → Two consecutive payload-channel failures were observed; their cause is not established. Do not repeat the unchanged payload. If it cannot be corrected within the remaining budget, finish per your report contract and include this receipt verbatim. This receipt establishes neither content validity nor fault ownership.";
  }
  const violation: Record<string, any> = { code, locus, detail };
  if (opts.json_decode_error !== null && opts.json_decode_error !== undefined) {
    violation.json_decode_error = opts.json_decode_error;
  }
  return [null, _rejected("ist.machine-mindmap-parts-result", [violation])];
}

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _resolveCasesPayload(cases: any, cases_path: string, opts: { out_name: string; dispatch_id: string }): [Array<Record<string, any>> | null, string | null] {
  const { out_name, dispatch_id } = opts;
  const streakKey = `${out_name}:${dispatch_id}`;
  const reissueHint = "Re-issue the call once with the same case content as a compact native array: trim free-form prose (notes, reasons, basis), keep every verbatim atom exactly as authored.";
  if (Array.isArray(cases) && cases.length) {
    return [[...cases], null];
  }
  if (Array.isArray(cases) && !(cases_path ?? "").trim()) {
    return [[], null];
  }
  let text = "";
  let locus = "cases";
  if ((cases_path ?? "").trim()) {
    locus = "cases_path";
    try {
      const _sealed_output = require("./_sealed_output");
      const target = _sealed_output.scoped_output_path(cases_path.trim());
      const batchRoot = _sealed_output.scoped_output_path(_sealed_output.output_root().joinpath(out_name, ".payload-channel-scope")).parent;
      target.relative_to(batchRoot);
      text = (_sealed_output.read_bytes(target, { max_bytes: 16 * 1024 * 1024 }) as Buffer).toString("utf8");
    } catch (exc) {
      return _payloadReject("cases_path_unreadable", "cases_path", `the cases_path file could not be read (${(exc as any)?.constructor?.name ?? "Error"}); it must be a regular JSON file inside the current batch's outputs directory.`, { streak: _bumpSubmitPayloadStreak(streakKey) });
    }
  } else if (typeof cases === "string" && cases.trim()) {
    text = cases;
  }
  if (!text.trim()) {
    return _payloadReject("cases_payload_empty", "cases", "no payload channel carried content; the cause is not established. " + reissueHint, { streak: _bumpSubmitPayloadStreak(streakKey) });
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
    let diagnostic: Record<string, any> | null = null;
    let syntaxLocation = "";
    if ((exc as any)?.name === "SyntaxError") {
      const msg = String((exc as Error).message);
      diagnostic = { msg };
      syntaxLocation = `JSON syntax: ${msg}. `;
    }
    return _payloadReject("cases_payload_unparseable", locus, `the payload arrived as text that is not valid JSON (${(exc as any)?.constructor?.name ?? "Error"}); ` + syntaxLocation + "the cause is not established. " + reissueHint, { streak: _bumpSubmitPayloadStreak(streakKey), json_decode_error: diagnostic });
  }
  if (!Array.isArray(parsed) || !parsed.length || !parsed.every((entry) => _isMapping(entry))) {
    return _payloadReject("cases_payload_unparseable", locus, `the payload must be a non-empty JSON array of case objects; got ${parsed === null ? "null" : Array.isArray(parsed) ? "Array" : typeof parsed}. ` + reissueHint, { streak: _bumpSubmitPayloadStreak(streakKey) });
  }
  return [parsed, null];
}

function _verbatimPrecheck(outputs_root: P | string, out_name: string, dispatch_id: string, opts: { source_sha256: string; cases: Array<Record<string, any>> }): [Array<Record<string, any>>, Array<Record<string, string>>, string] {
  const { lexical_absolute, read_regular_nofollow, sha256_bytes } = require("../../../case_compiler/_sealed_io");
  const _sh = require("../compile_engine/_shared");
  const { MachineMindmapPartsError, machine_mindmap_case_verbatim_violations } = require("./recompose_parts");
  const { read_machine_mindmap_submission } = require("./recompose_submission");
  const receipt = read_machine_mindmap_submission(outputs_root, out_name, dispatch_id);
  const binding = receipt.binding;
  const root = lexical_absolute(String(outputs_root));
  const batch = new P(root).joinpath(out_name);
  const raw = read_regular_nofollow(batch.joinpath("mindmap_source.json")._p, {
    errorType: MachineMindmapPartsError,
    invalid_message: "mindmap snapshot path is invalid",
    directory_message: "mindmap snapshot directory is unavailable",
    open_message: "mindmap snapshot is unavailable",
    bounds_message: "mindmap snapshot exceeds its sealed size boundary",
    changed_message: "mindmap snapshot changed while being read",
    max_bytes: 32 * 1024 * 1024,
    min_bytes: 1,
    trusted_root: root,
    require_current_uid: true,
  }) as Buffer;
  if (sha256_bytes(raw) !== String(opts.source_sha256 ?? "")) {
    throw new MachineMindmapPartsError("mindmap snapshot identity drift");
  }
  let specText: string | null = null;
  const specName = String(binding.governing_spec ?? "").trim();
  if (specName) {
    const { resolve_indexed_spec } = require("../../../../kms/spec_index");
    const resolved = resolve_indexed_spec(_sh.project_root(), specName);
    if (resolved === null || resolved === undefined || resolved.sha256 !== String(binding.governing_spec_sha256 ?? "") || resolved.generation_id !== String(binding.governing_spec_generation_id ?? "") || resolved.manifest_sha256 !== String(binding.governing_spec_manifest_sha256 ?? "")) {
      throw new MachineMindmapPartsError("governing spec identity drift");
    }
    specText = Buffer.isBuffer(resolved.content) ? resolved.content.toString("utf8") : String(resolved.content);
  }
  let defectReceipt: Record<string, any> | null = null;
  try {
    const statusRaw = read_regular_nofollow(batch.joinpath("defect_spec_status.json")._p, {
      errorType: MachineMindmapPartsError,
      invalid_message: "defect spec status path is invalid",
      directory_message: "defect spec status directory is unavailable",
      open_message: "defect spec status is unavailable",
      bounds_message: "defect spec status exceeds its boundary",
      changed_message: "defect spec status changed while being read",
      max_bytes: 4 * 1024 * 1024,
      min_bytes: 1,
      trusted_root: root,
      require_current_uid: true,
    }) as Buffer;
    const payload = JSON.parse(statusRaw.toString("utf8"));
    const candidate = _isMapping(payload) ? payload.receipt : null;
    if (_isMapping(candidate)) {
      if (String(payload.receipt_sha256 ?? "") !== String(binding.defect_spec_receipt_sha256 ?? "")) {
        throw new MachineMindmapPartsError("defect spec receipt identity drift");
      }
      defectReceipt = candidate;
    }
  } catch (exc) {
    if (exc instanceof MachineMindmapPartsError && /identity drift/.test((exc as Error).message)) {
      throw exc;
    }
  }
  const mindmapText = raw.toString("utf8").replace(/^﻿?/, "");
  const [verifiedCases, verbatimViolations] = machine_mindmap_case_verbatim_violations(opts.cases, {
    mindmap_text: mindmapText,
    spec_text: specText,
    governing_spec: specName || null,
    governing_spec_status: String(binding.governing_spec_status ?? "") || null,
    defect_spec_receipt: defectReceipt,
    defect_spec_status: String(binding.defect_spec_status ?? "") || null,
    defect_spec_receipt_sha256: String(binding.defect_spec_receipt_sha256 ?? "") || null,
  });
  return [verifiedCases, verbatimViolations, mindmapText];
}

function _normalizeDisclosureShapes(payload: Record<string, any>): Record<string, any> {
  const normalized = { ...payload };
  const notes = normalized.orphan_notes;
  if (_isMapping(notes)) {
    normalized.orphan_notes = Object.values(notes).map((v) => String(v));
  } else if (notes === null && "orphan_notes" in normalized) {
    normalized.orphan_notes = [];
  }
  const check = normalized.self_check;
  if (check === null && "self_check" in normalized) {
    normalized.self_check = {};
  }
  return normalized;
}

export function submit_machine_mindmap_cases(cases: any = "", cases_path = ""): string {
  const { current_recompose_assignment, current_recompose_dispatch, machine_mindmap_submission_open_guard } = require("./recompose_submission");
  const { append_machine_mindmap_cases, machine_mindmap_case_value_violations, read_machine_mindmap_parts } = require("./recompose_parts");
  const {
    LEGAL_FORM_ENTRY,
    STEP_STRUCTURE_KEY,
    apply_engine_slots,
    budget_violations,
    distribution_criterion_bindings,
    normalized_expectations_for_case,
    object_kind_closed_set,
    step_structure_violations,
    strip_engine_slots,
  } = require("../../../case_compiler/step_structure");
  const [outputsRoot, outName, dispatchId] = current_recompose_dispatch();
  const assigned = current_recompose_assignment();
  const [resolvedCases, payloadError] = _resolveCasesPayload(cases, cases_path, { out_name: outName, dispatch_id: dispatchId });
  if (payloadError !== null) return payloadError;
  const caseList = resolvedCases!;
  const snapshot = machine_mindmap_submission_open_guard(outputsRoot, outName, dispatchId, (): any => {
    const ledger = read_machine_mindmap_parts(outputsRoot, outName);
    if (!_scopeOutstanding(ledger.missing_autoids, assigned).length) {
      return _rejected("ist.machine-mindmap-parts-result", [{ code: "case_set_complete", locus: "cases", detail: assigned.length ? _SHARD_COMPLETE_NEXT : _PARTS_COMPLETE_NEXT }]);
    }
    const violations = machine_mindmap_case_value_violations(caseList, ledger.case_autoids);
    if (violations.length) {
      return _rejected("ist.machine-mindmap-parts-result", violations);
    }
    if (assigned.length) {
      const scope = new Set<string>(assigned);
      const outside = [...new Set(caseList.map((c) => String(c?.autoid ?? "")).filter((aid) => aid && !scope.has(aid)))].sort();
      if (outside.length) {
        return _rejected("ist.machine-mindmap-parts-result", [{ code: "case_outside_assignment", locus: "cases", detail: "This dispatch is responsible only for its assigned autoids; a sibling shard owns " + outside.slice(0, 8).join(", ") + ". Submit only your own outstanding cases." }]);
      }
    }
    const [verbatimCases, verbatimViolations, mindmapText] = _verbatimPrecheck(outputsRoot, outName, dispatchId, { source_sha256: ledger.source_sha256, cases: caseList });
    if (verbatimViolations.length) {
      return _rejected("ist.machine-mindmap-parts-result", verbatimViolations);
    }
    const normalizedViolations = machine_mindmap_case_value_violations(verbatimCases, ledger.case_autoids);
    if (normalizedViolations.length) {
      return _rejected("ist.machine-mindmap-parts-result", normalizedViolations);
    }
    const structureObjectKinds = object_kind_closed_set();
    const structureRejections: Array<Record<string, string>> = [];
    for (const [caseIndex, case_] of verbatimCases.entries()) {
      strip_engine_slots(case_);
      structureRejections.push(...step_structure_violations(case_, { index: caseIndex, object_kinds: structureObjectKinds }));
    }
    if (structureRejections.length) {
      return _rejected("ist.machine-mindmap-parts-result", budget_violations(structureRejections));
    }
    for (const case_ of verbatimCases) {
      try {
        apply_engine_slots(case_, distribution_criterion_bindings(normalized_expectations_for_case(case_, { mindmap_text: mindmapText, mindmap_source_sha256: ledger.source_sha256 })));
      } catch (exc) {
        logger.warning("engine slot pairing failed for %s", String(case_.autoid ?? ""));
        return _rejected("ist.machine-mindmap-parts-result", budget_violations([{ code: "step_structure_count_out_of_range", locus: `cases[${String(case_.autoid ?? "")}].${STEP_STRUCTURE_KEY}`, detail: `the engine could not pair this case's distribution criteria with its observation steps from the structure as submitted (${(exc as any)?.constructor?.name ?? "Error"}). The engine records no sampling count of its own; it only records which observation step each distribution criterion pairs with. Check the step numbers, object roles and stated conditions of the observation steps against the authored text, within the declared bounds.`, legal_form: LEGAL_FORM_ENTRY }]));
      }
    }
    return append_machine_mindmap_cases(outputsRoot, outName, dispatchId, verbatimCases);
  });
  if (typeof snapshot === "string") return snapshot;
  _resetSubmitPayloadStreak(`${outName}:${dispatchId}`);
  const scopeOutstanding = _scopeOutstanding(snapshot.missing_autoids, assigned);
  const result: Record<string, any> = { schema: "ist.machine-mindmap-parts-result", recorded: snapshot.submitted_autoids.length, total: snapshot.case_autoids.length, outstanding_autoids: scopeOutstanding, artifact_sha256: snapshot.ledger_sha256 };
  if (!scopeOutstanding.length) {
    result.next = assigned.length ? _SHARD_COMPLETE_NEXT : _PARTS_COMPLETE_NEXT;
  }
  return pyJsonDumps(result, { ensure_ascii: false, sort_keys: true });
}

export function submit_machine_mindmap(machine_mindmap: Record<string, any>): string {
  const { MachineMindmapContentError, canonical_machine_mindmap_submission_result, current_recompose_assignment, current_recompose_dispatch, submit_machine_mindmap_payload } = require("./recompose_submission");
  const [outputsRoot, outName, dispatchId] = current_recompose_dispatch();
  const assigned = current_recompose_assignment();
  if (assigned.length) {
    return _rejected("ist.machine-mindmap-submission-result", [{ code: "shard_must_not_seal", locus: "machine_mindmap", detail: _SHARD_COMPLETE_NEXT }]);
  }
  try {
    submit_machine_mindmap_payload(outputsRoot, outName, dispatchId, _normalizeDisclosureShapes(machine_mindmap));
  } catch (exc) {
    if (exc instanceof MachineMindmapContentError) {
      return _rejected("ist.machine-mindmap-submission-result", [{ code: (exc as any).code, locus: "machine_mindmap", detail: String((exc as any).message) }]);
    }
    throw exc;
  }
  return canonical_machine_mindmap_submission_result(outputsRoot, outName, dispatchId);
}
