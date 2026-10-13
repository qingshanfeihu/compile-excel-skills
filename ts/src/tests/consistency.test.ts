import assert from "node:assert/strict";
import crypto from "node:crypto";
import { test } from "node:test";

import * as consistency from "../cex_client/consistency";
import {
  _expectation_id,
  resolve_consistency_evidence,
  stamp_consistency_quotes,
} from "../cex_core/engine/case_compiler/mindmap_contract_projector";
import {
  build_consistency_contract,
  consistency_material_receipt_sha256,
  validate_consistency_contract,
} from "../cex_core/engine/case_compiler/consistency_contract";

const MODULE = "consistency packaging";

const A1 = "203600000000000001";
const SPEC_NAME = "12345_Listener_Spec.md";
const SPEC_TEXT = "# 监听器配置指南\n\n3、监听器端口修改后需执行 write mem 才落盘\n4、重启设备后未保存的监听器配置回退为出厂值\n";
const TITLE = "1.配置port 为53.执行write mem后重启设备\n2.查看sdns listener  [check1]";
const SPEC_LINE3 = "3、监听器端口修改后需执行 write mem 才落盘";
const NODES = JSON.stringify([{ data: { text: "12345 监听器改造" }, children: [
  { data: { text: "配置保存" }, children: [{
    data: { text: TITLE, autoid: A1 }, children: [
      { data: { text: "2.查看sdns listener" }, children: [
        { data: { text: "[check1]配置未被保存" } }] }] }] }] }]);
const MM_CASE = {
  autoid: A1, title: TITLE, group_path: ["配置保存"],
  steps: [{ n: "2", text: "2.查看sdns listener" }],
  expectations_by_step: [{ n: "2", text: "[check1]配置未被保存",
    origin: "expectation:check1", assertion: null }],
};

function conclusion(verdict: string, disposition: string): any {
  return { schema: "ist.recompose-consistency", verdict,
    spec_locator: `spec:${SPEC_NAME}:3`, case_locator: "expectation:check1",
    incompatibility: verdict === "mutually_exclusive" ? "不能同时成立" : "对得上",
    premises: [{ origin: "spec", locator: `spec:${SPEC_NAME}:3` },
      { origin: "case", locator: "expectation:check1" }],
    spec_clauses: [{ text: SPEC_LINE3, disposition, reason: "r" }],
    missing_preconditions: [] };
}

function stamp(conclusion_: any): any {
  const c = structuredClone(conclusion_);
  stamp_consistency_quotes(c, A1, { mindmap_text: NODES, governing_spec: SPEC_NAME,
    spec_text: SPEC_TEXT, defect_spec_receipt: null, cross_check: false });
  return c;
}

function makeCard(conclusion_: any): [any, string] {
  const card = { autoid: A1, batch: "b",
    expectations: [{ assertion: { expectation_id: _expectation_id(A1, "2", 1),
      semantic_key: "k" } }],
    consistency: conclusion_ };
  const raw = Buffer.from(JSON.stringify(card), "utf8");
  return [card, crypto.createHash("sha256").update(raw).digest("hex")];
}

test(`${MODULE}: a stamped consistent conclusion resolves to a validating overlay`, async () => {
  const concl = stamp(conclusion("consistent", "consistent"));
  assert.equal(concl.spec_quote, SPEC_LINE3, "the engine stamps the quote from the locator");
  const [draft, error] = await consistency.draftFromConclusion(A1, concl);
  assert.equal(error, "");
  assert.equal(draft!.verdict, "consistent");
  assert.deepEqual(Object.keys(draft!).sort(),
    ["autoid", "case_locator", "case_quote", "incompatibility", "premises", "schema",
      "spec_clauses", "spec_locator", "spec_quote", "verdict"],
    "the draft carries exactly the ten material keys");
  const [state, reason, material] = resolve_consistency_evidence(
    { ...MM_CASE, consistency: concl }, draft!,
    { mindmap_text: NODES, governing_spec: SPEC_NAME, spec_text: SPEC_TEXT,
      defect_spec_receipt: null });
  assert.equal(state, "consistent", reason);
  const [card, sha] = makeCard(concl);
  const overlay = build_consistency_contract({ autoid: A1, base_contract: card,
    base_contract_sha256: sha, accepted_material: material, machine_case: MM_CASE });
  assert.equal(validate_consistency_contract(overlay, { base_contract: card,
    base_contract_sha256: sha, accepted_material: material,
    consistency_receipt_sha256: consistency_material_receipt_sha256(material),
    machine_case: MM_CASE }), "");
  assert.equal(overlay.spec_endorsement.scope.kind, "expectation");
});

test(`${MODULE}: underdetermined maps to a continuing verdict, missing clauses is refused`, async () => {
  const under = stamp(conclusion("underdetermined", "not_applicable"));
  const [draft] = await consistency.draftFromConclusion(A1, under);
  assert.equal(draft!.verdict, "consistent");
  const noClauses = stamp(conclusion("consistent", "consistent"));
  delete noClauses.spec_clauses;
  const [draft2] = await consistency.draftFromConclusion(A1, noClauses);
  const [state, reason] = resolve_consistency_evidence(
    { ...MM_CASE, consistency: noClauses }, draft2!,
    { mindmap_text: NODES, governing_spec: SPEC_NAME, spec_text: SPEC_TEXT,
      defect_spec_receipt: null });
  assert.equal(state, "invalid");
  assert.equal(reason, "scenario1_clauses_invalid");
});

test(`${MODULE}: drifted premise text is refused by the re-stamp`, async () => {
  const concl = stamp(conclusion("consistent", "consistent"));
  concl.premises[0].text = "我自己写的一句";
  const [draft] = await consistency.draftFromConclusion(A1, concl);
  const [state, reason] = resolve_consistency_evidence(
    { ...MM_CASE, consistency: concl }, draft!,
    { mindmap_text: NODES, governing_spec: SPEC_NAME, spec_text: SPEC_TEXT,
      defect_spec_receipt: null });
  assert.equal(state, "invalid");
  assert.equal(reason, "consistency_premise_0_text_drift",
    "TS must use the Python stamp-failure code grammar");
});

test(`${MODULE}: the record path freezes the verdict and rejects forged quotes`, async () => {
  const model = { spec_locator: `spec:${SPEC_NAME}:3`, case_locator: "expectation:check1",
    incompatibility: "对得上", premises: [{ origin: "spec", locator: `spec:${SPEC_NAME}:3` },
      { origin: "case", locator: "expectation:check1" }],
    spec_clauses: [{ text: SPEC_LINE3, disposition: "consistent", reason: "r" }] };
  const concl = stamp(conclusion("mutually_exclusive", "contradicts"));
  let [draft, error] = await consistency.draftForRecord(A1, concl, { ...model, verdict: "consistent" });
  assert.equal(draft, null);
  assert.equal(error, "consistency_verdict_frozen");
  [draft, error] = await consistency.draftForRecord(A1, concl, { ...model, verdict: "conflict" });
  assert.equal(error, "");
  assert.equal(draft!.verdict, "conflict");
  [draft, error] = await consistency.draftForRecord(A1, null, { ...model, verdict: "consistent" });
  assert.equal(error, "");
  const [state] = resolve_consistency_evidence(MM_CASE, draft!,
    { mindmap_text: NODES, governing_spec: SPEC_NAME, spec_text: SPEC_TEXT,
      defect_spec_receipt: null });
  assert.equal(state, "consistent");
  [draft, error] = await consistency.draftForRecord(A1, null,
    { ...model, verdict: "consistent", spec_quote: "我编的一句" });
  const [forgedState, forgedReason] = resolve_consistency_evidence(MM_CASE, draft!,
    { mindmap_text: NODES, governing_spec: SPEC_NAME, spec_text: SPEC_TEXT,
      defect_spec_receipt: null });
  assert.equal(forgedState, "invalid");
  assert.equal(forgedReason, "consistency_spec_quote_drift");
  [, error] = await consistency.draftForRecord(A1, null, { spec_locator: "x", bogus: 1 });
  assert.ok(String(error).startsWith("record_keys_invalid"), error);
});

test(`${MODULE}: a full mutually_exclusive conclusion is actionable abandonment`, async () => {
  const { recompose_abandon_actionable } =
    require("../cex_core/engine/ist_core/tools/device/mechanical_case_submit_tool");
  const [card] = makeCard(stamp(conclusion("mutually_exclusive", "contradicts")));
  assert.equal(recompose_abandon_actionable(card, { spec_surface_present: true }), true);
  const thin = stamp(conclusion("mutually_exclusive", "contradicts"));
  delete thin.spec_quote; delete thin.case_quote;
  const [thinCard] = makeCard(thin);
  assert.equal(recompose_abandon_actionable(thinCard, { spec_surface_present: true }), false,
    "incomplete S1 evidence is not actionable — same as the engine");
});
