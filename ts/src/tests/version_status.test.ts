import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";

import { installedVersion, latestUpstreamRelease, versionStatus } from "../cex_client/tools";

const TS_ROOT = path.resolve(__dirname, "..", "..");

test("installedVersion reads the shipped package.json", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(TS_ROOT, "package.json"), "utf8"));
  assert.equal(installedVersion(), pkg.version);
});

test("latestUpstreamRelease resolves to a string or degrades to null", async () => {
  const latest = await latestUpstreamRelease();
  assert.ok(latest === null || /^\d+\.\d+\.\d+/.test(latest), `unexpected release value: ${latest}`);
});

test("versionStatus reports both sides and a boolean update flag", async () => {
  const status = await versionStatus();
  assert.equal(status.installed_version, installedVersion());
  assert.equal(typeof status.update_available, "boolean");
  if (status.latest_upstream_release === null) {
    assert.equal(status.update_available, false, "offline degrade must not claim an update");
  }
});
