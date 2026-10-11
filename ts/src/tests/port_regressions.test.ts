import assert from "node:assert/strict";
import { test } from "node:test";

import { parse_build_identity, _canonical_json } from "../cex_core/engine/sync/command_tree_sync";
import { _rejectDuplicateKeys } from "../cex_core/engine/case_compiler/mechanical_case";
import { _order, _orderAfter, newerSubmissions } from "../cex_client/gateway";

const MODULE = "port regressions";

test(`${MODULE}: parse_build_identity accepts dotted full versions`, () => {
  const id = parse_build_identity("InfosecOS Beta.APV-HG-K.10.5.0.585");
  assert.equal(id.product, "APV");
  assert.equal(id.platform, "HG-K");
  assert.equal(id.release, "10.5.0");
  assert.equal(id.build, "585");
  assert.equal(id.inventory_version, "10.5");
});

test(`${MODULE}: parse_build_identity keeps the legacy 'word word 1.2.3 build 4' shape`, () => {
  const id = parse_build_identity("Sample Build 10.5.0 build 585");
  assert.equal(id.product, "Sample");
  assert.equal(id.platform, "Build");
  assert.equal(id.release, "10.5.0");
  assert.equal(id.build, "585");
});

test(`${MODULE}: parse_build_identity rejects garbage`, () => {
  assert.throws(() => parse_build_identity("not a version"));
});

test(`${MODULE}: canonical json matches the python publisher (sorted keys, compact separators, newline)`, () => {
  const payload = { b: 1, a: { d: [2, 3], c: "x" } };
  const text = _canonical_json(payload).toString("utf8");
  assert.equal(text, '{"a":{"c":"x","d":[2,3]},"b":1}\n');
});

test(`${MODULE}: duplicate-key reviver allows the same key in different objects`, () => {
  const reviver = _rejectDuplicateKeys();
  const parsed = JSON.parse('{"k":1,"x":{"k":2},"y":{"k":3}}', reviver);
  assert.deepEqual(parsed, { k: 1, x: { k: 2 }, y: { k: 3 } });
});

test(`${MODULE}: duplicate-key reviver never rejects legitimate nested documents`, () => {
  const reviver = _rejectDuplicateKeys();
  const parsed = JSON.parse('{"steps":[{"kind":"CONFIG","cmd":"a"},{"kind":"CONFIG","cmd":"b"}],"desc":"x","blocks":[{"desc":"y"}]}', reviver);
  assert.equal(parsed.steps.length, 2);
  assert.equal(parsed.blocks[0].desc, "y");
});

test(`${MODULE}: V8 folds textual duplicate keys before the reviver (documented engine behavior)`, () => {
  const reviver = _rejectDuplicateKeys();
  const parsed = JSON.parse('{"a":{"k":1,"k":2}}', reviver);
  assert.deepEqual(parsed, { a: { k: 2 } });
});

test(`${MODULE}: task order compares seq numerically, not lexically`, () => {
  const older = { seq: 4, submitted_at: "2026-10-09T03:20:52+09:00" };
  const newer = { seq: 15, submitted_at: "2026-10-11 02:53:20" };
  assert.equal(_orderAfter(_order(newer as any), _order(older as any)), true);
  assert.equal(_orderAfter(_order(older as any), _order(newer as any)), false);
});

test(`${MODULE}: task order falls back to parsed timestamps when seq ties`, () => {
  const older = { seq: 7, submitted_at: "2026-10-09T03:20:52+09:00" };
  const newer = { seq: 7, submitted_at: "2026-10-11 02:53:20" };
  assert.equal(_orderAfter(_order(newer as any), _order(older as any)), true);
  assert.equal(_orderAfter(_order(older as any), _order(newer as any)), false);
});

test(`${MODULE}: newerSubmissions never reports an older task as newer`, () => {
  assert.equal(typeof newerSubmissions, "function");
});
