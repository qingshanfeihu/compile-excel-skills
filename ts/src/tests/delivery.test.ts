// 交付台账（issue #6）的 TS 端测试：构建器、幂等台账、出件落盘，以及与 Python 端和真
// 抽取件对表的钉住。TS 端没有假引擎——delivery 是纯胶水，直接摆状态与 emit 结果。
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import {
  EV_NEEDS_DECISION,
  EV_RECOMPOSE_DONE,
  EV_SUBMISSION_REJECTED,
  MANIFEST_SCHEMA,
  REPORT_SCHEMA,
  appendFacts,
  buildEngineReport,
  buildManifest,
  decisionEvent,
  recomposeDoneEvent,
  rejectionEvent,
  writeReports,
} from "../cex_client/delivery.js";
import { init as initWorkspace } from "../cex_client/workspace.js";
import { ClientError } from "../cex_client/errors.js";

const A = "202609240000000001";
const B = "245861784181666726";
const C = "245861784181694845";

const scratch = (): string => fs.mkdtempSync(path.join(os.tmpdir(), "cex-delivery-"));

const violation = {
  gate: "command_tree",
  code: "command_not_in_tree",
  locus: "blocks[0].F",
  detail: "the step names a command the device tree does not carry",
};

const demoState = (extra: Record<string, unknown> = {}): Record<string, unknown> => ({
  out_name: "demo",
  phase: "published",
  receipt: {
    written_autoids: [A, B, C],
    abandoned_autoids: [],
    contract_sha256_by_autoid: { [A]: "a".repeat(64), [B]: "b".repeat(64), [C]: "c".repeat(64) },
    machine_mindmap_sha256: "m".repeat(64),
    governing_spec_status: "none",
  },
  sealed: { [A]: { mechanical_case_sha256: "s".repeat(64), artifact: `x/${A}/mechanical_case.json` } },
  submissions: {
    [B]: { at: "2026-10-13T00:00:00", status: "rejected", attempt: 2, violations: [violation], advisories: [] },
  },
  ...extra,
});

const emitOut = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  xlsx: null,
  cases_json: null,
  emitted_autoids: [A],
  not_sealed_autoids: [B, C],
  not_emitted: [],
  verify: { pass: 1, fail: 0, failures: [] },
  ...over,
});

test("delivery: buildManifest keeps batch identity from the receipt", () => {
  const manifest = buildManifest(demoState());
  assert.equal(manifest.schema, MANIFEST_SCHEMA);
  assert.equal(manifest.name, "demo");
  const contracts = manifest.contract_sha256_by_autoid as Record<string, string>;
  assert.equal(contracts[A], "a".repeat(64));
  assert.deepEqual(manifest.written_autoids, [A, B, C]);
});

test("delivery: buildEngineReport names every case with its last submission", () => {
  const report = buildEngineReport(demoState(), emitOut(), {});
  assert.equal(report.schema, REPORT_SCHEMA);
  assert.equal(report.hard_check_contracted_equals_delivered, false);
  const totals = report.totals as Record<string, number>;
  assert.equal(totals.contracted, 3);
  assert.equal(totals.delivered, 1);
  assert.equal(totals.rejected_last, 1);
  assert.equal(totals.not_submitted, 1);
  const cases = report.cases as Record<string, Record<string, unknown>>;
  assert.equal(cases[A].status, "delivered");
  assert.equal(cases[B].status, "rejected");
  const last = cases[B].last_submission as Record<string, unknown>;
  assert.equal((last.violations as Record<string, unknown>[])[0].code, "command_not_in_tree");
  assert.equal(cases[C].status, "not_submitted");
  assert.deepEqual(report.not_delivered_autoids, [B, C]);
});

test("delivery: facts appends are idempotent by the engine keys, receipts always land", () => {
  const wsDir = scratch();
  const ws = initWorkspace(wsDir, { server: "https://ces.example.test", deviceBuild: "B_1" });
  const batch = path.join(ws.outputsDir, "demo");
  fs.mkdirSync(batch, { recursive: true });
  const receipt = { ev: EV_RECOMPOSE_DONE, reentry_round: 0, written: 1 };
  appendFacts(ws, batch, [recomposeDoneEvent("demo", receipt)]);
  appendFacts(ws, batch, [recomposeDoneEvent("demo", receipt)]); // 重发布：再落一条，读者找最新
  appendFacts(ws, batch, [decisionEvent("demo", A, ["who answers?"])]);
  appendFacts(ws, batch, [decisionEvent("demo", A, ["who answers?"])]); // 幂等键吞重复
  appendFacts(ws, batch, [rejectionEvent("demo", B, 1, [violation])]);
  appendFacts(ws, batch, [rejectionEvent("demo", B, 2, [violation])]); // occurrence 各占一行
  const lines = fs
    .readFileSync(path.join(batch, "facts.jsonl"), "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as Record<string, unknown>);
  assert.deepEqual(lines.map((l) => l.ev), [
    EV_RECOMPOSE_DONE,
    EV_RECOMPOSE_DONE,
    EV_NEEDS_DECISION,
    EV_SUBMISSION_REJECTED,
    EV_SUBMISSION_REJECTED,
  ]);
  assert.equal(lines[4].attempt, 2);
  assert.notEqual(lines[3].occurrence_id, lines[4].occurrence_id);
  assert.throws(() => appendFacts(ws, batch, [{ ev: "cex_something_new" }]), ClientError);
});

test("delivery: writeReports lands the ledger and the narratives name the dropped cases", () => {
  const wsDir = scratch();
  const ws = initWorkspace(wsDir, { server: "https://ces.example.test", deviceBuild: "B_1" });
  const batch = path.join(ws.outputsDir, "demo");
  fs.mkdirSync(path.join(batch, "cases", B), { recursive: true });
  fs.writeFileSync(path.join(batch, "cases", B, "intent.json"), JSON.stringify({ title: "监听器改造" }));
  fs.writeFileSync(path.join(batch, "case.xlsx"), "xlsx-bytes");
  fs.writeFileSync(path.join(batch, "cases.json"), JSON.stringify({ batch: "demo" }));
  const out = emitOut({ xlsx: path.join(batch, "case.xlsx"), cases_json: path.join(batch, "cases.json") });
  const produced = writeReports(ws, demoState(), batch, out);
  for (const name of ["manifest.json", "engine_report.json", "delivery_report.md", "unsuccessful_cases.md"]) {
    assert.ok(fs.existsSync(path.join(batch, name)), name);
    assert.equal(produced[name], path.join(batch, name));
  }
  const md = fs.readFileSync(path.join(batch, "unsuccessful_cases.md"), "utf8");
  assert.ok(md.includes(`## ${B}`));
  assert.ok(md.includes("command_not_in_tree"));
  assert.ok(md.includes("监听器改造"), "title comes from the intent sidecar");
  assert.ok(!md.includes(`## ${A}`), "delivered cases stay out of the failure narrative");
  assert.ok(!fs.existsSync(path.join(batch, "facts.jsonl")), "emit adds no fact line");
  const report = JSON.parse(fs.readFileSync(path.join(batch, "engine_report.json"), "utf8")) as Record<string, unknown>;
  const artifacts = report.artifacts as Record<string, string>;
  assert.match(artifacts["case.xlsx.sha256"], /^[0-9a-f]{64}$/);
  const delivery = fs.readFileSync(path.join(batch, "delivery_report.md"), "utf8");
  assert.ok(delivery.includes("contracted 3 == delivered 1"));
  assert.ok(delivery.includes("不通过"));
});

test("delivery: a complete batch leaves the failure narrative away", () => {
  const wsDir = scratch();
  const ws = initWorkspace(wsDir, { server: "https://ces.example.test", deviceBuild: "B_1" });
  const batch = path.join(ws.outputsDir, "demo");
  fs.mkdirSync(batch, { recursive: true });
  const state = demoState({
    sealed: { [A]: {}, [B]: {}, [C]: {} },
    submissions: {},
  });
  const out = emitOut({
    emitted_autoids: [A, B, C],
    not_sealed_autoids: [],
    xlsx: "x",
    cases_json: "j",
  });
  const produced = writeReports(ws, state, batch, out);
  assert.ok(!("unsuccessful_cases.md" in produced));
  const delivery = fs.readFileSync(path.join(batch, "delivery_report.md"), "utf8");
  assert.ok(delivery.includes("通过**"));
  assert.ok(!delivery.includes("不通过**"));
});

test("delivery: the tables match the Python twin and the extracted registry", () => {
  const root = path.resolve(__dirname, "..", "..", "..");
  const py = fs.readFileSync(path.join(root, "cex_client", "delivery.py"), "utf8");
  for (const [name, value] of Object.entries({
    MANIFEST_SCHEMA,
    REPORT_SCHEMA,
    EV_RECOMPOSE_DONE,
    EV_SUBMISSION_REJECTED,
    EV_NEEDS_DECISION,
  })) {
    assert.ok(py.includes(`${name} = "${value}"`), name);
  }
  // 事件名必须在真抽取件的闭集里（TS 镜像的登记表是滞后快照，写侧以 Python 端为准）
  const registry = fs
    .readFileSync(path.join(root, "cex_core", "engine", "ist_core", "compile_engine", "fact_events.py"), "utf8");
  for (const ev of [EV_RECOMPOSE_DONE, EV_SUBMISSION_REJECTED, EV_NEEDS_DECISION]) {
    assert.ok(registry.includes(`'${ev}'`), ev);
  }
  const lexicon = fs
    .readFileSync(path.join(root, "cex_core", "engine", "ist_core", "display_lexicon.py"), "utf8");
  const block = py.split("DELIVERY_FILE_LABELS = {")[1].split("}")[0];
  for (const m of [...block.matchAll(/"([\w.]+)": "(.*?)"/g)]) {
    assert.ok(lexicon.includes(`'${m[1]}': '${m[2]}'`), m[1]);
  }
});
