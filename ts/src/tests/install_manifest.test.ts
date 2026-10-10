import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import { Installer, distributableFiles } from "../install";

const TS_ROOT = path.resolve(__dirname, "..", "..");

test("package, plugin manifest and MCP server report one version", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(TS_ROOT, "package.json"), "utf8"));
  const plugin = JSON.parse(fs.readFileSync(path.join(TS_ROOT, ".claude-plugin", "plugin.json"), "utf8"));
  assert.equal(plugin.version, pkg.version, "plugin manifest version must track package.json");
  const reply = execFileSync(
    process.execPath,
    [path.join(TS_ROOT, "dist", "bin", "cex_mcp_proxy.js")],
    {
      input: '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}',
      timeout: 15000,
    },
  ).toString("utf8");
  const serverInfo = JSON.parse(reply.trim().split("\n")[0]).result.serverInfo;
  assert.equal(serverInfo.version, pkg.version, "MCP serverInfo.version must track package.json");
});

test("the install manifest ships dist/ and the claude plugin metadata", () => {
  const files = distributableFiles(TS_ROOT);
  const has = (rel: string) => files.includes(rel);
  assert.ok(has("dist/bin/cex_tool.js"), "manifest must include dist/bin/cex_tool.js");
  assert.ok(has("dist/bin/cex_mcp_proxy.js"), "manifest must include dist/bin/cex_mcp_proxy.js");
  assert.ok(has("dist/cex_client/tools.js"), "manifest must include dist/cex_client/tools.js");
  assert.ok(has(".claude-plugin/plugin.json"), "manifest must include .claude-plugin/plugin.json");
  assert.ok(has(".claude-plugin/marketplace.json"), "manifest must include .claude-plugin/marketplace.json");
  assert.ok(has("skills/compile-excel/SKILL.md"), "manifest must include the skill doc");
  assert.ok(has("skills/compile-excel/scripts/_cex_path.js"), "manifest must include the node bootstrap");
  assert.ok(!files.some((f) => f.startsWith("node_modules/")), "manifest must not ship node_modules");
  assert.ok(!files.some((f) => f.startsWith("skills/compile-excel/scripts/") && f.endsWith(".py")), "no stale python skill scripts");
});

test("a fresh install lands under versions/ with a current ref and shared npm metadata", () => {
  const prefix = fs.mkdtempSync(path.join(os.tmpdir(), "cex-prefix-"));
  try {
    const installer = new Installer(prefix, false);
    const report = installer.placeDistribution(false);
    const version = report.version;
    assert.ok(fs.existsSync(path.join(prefix, "versions", version, "dist", "bin", "cex_tool.js")), "version dir must hold the distribution");
    assert.equal(fs.readFileSync(path.join(prefix, "current"), "utf8").trim(), version, "current ref must name the installed version");
    assert.ok(fs.existsSync(path.join(prefix, "package.json")), "npm metadata must sit at the layout root for the shared node_modules");
    assert.equal(installer.currentRoot(), path.join(prefix, "versions", version));
    // reinstalling the same version without --upgrade refuses
    assert.throws(() => new Installer(prefix, false).placeDistribution(false), /already installed/);
  } finally {
    fs.rmSync(prefix, { recursive: true, force: true });
  }
});

test("an upgrade adopts a flat 0.3.0 install as a rollback candidate", () => {
  const prefix = fs.mkdtempSync(path.join(os.tmpdir(), "cex-prefix-"));
  try {
    // build a fake flat install: what 0.3.0 left behind
    fs.mkdirSync(path.join(prefix, "dist"), { recursive: true });
    fs.writeFileSync(path.join(prefix, ".cex_install.json"), "{}", "utf8");
    fs.writeFileSync(path.join(prefix, "package.json"), JSON.stringify({ version: "0.3.0" }), "utf8");
    const installer = new Installer(prefix, false);
    const report = installer.placeDistribution(true);
    const version = report.version;
    assert.ok(fs.existsSync(path.join(prefix, "versions", "legacy-0.3.0")), "the flat install must be kept as a rollback candidate");
    assert.ok(fs.existsSync(path.join(prefix, "versions", "legacy-0.3.0", ".orphaned_at")), "the adopted copy must be marked for eventual cleanup");
    assert.equal(fs.readFileSync(path.join(prefix, "current"), "utf8").trim(), version);
    assert.ok(fs.existsSync(path.join(prefix, "versions", version, "dist", "bin", "cex_tool.js")));
    // rollback to the adopted copy
    const rolled = installer.rollback("legacy-0.3.0");
    assert.equal(rolled.ok, true);
    assert.equal(fs.readFileSync(path.join(prefix, "current"), "utf8").trim(), "legacy-0.3.0");
    assert.equal(installer.currentRoot(), path.join(prefix, "versions", "legacy-0.3.0"));
  } finally {
    fs.rmSync(prefix, { recursive: true, force: true });
  }
});

test("rollback without a target picks the newest older version", () => {
  const prefix = fs.mkdtempSync(path.join(os.tmpdir(), "cex-prefix-"));
  try {
    const installer = new Installer(prefix, false);
    installer.placeDistribution(true);
    const version = installer.currentRef();
    // plant an older version by hand
    fs.mkdirSync(path.join(prefix, "versions", "0.0.1", "dist"), { recursive: true });
    fs.writeFileSync(path.join(prefix, "versions", "0.0.1", "package.json"), JSON.stringify({ version: "0.0.1" }), "utf8");
    const rolled = installer.rollback(null);
    assert.equal(rolled.rolled_back_to, "0.0.1");
    assert.notEqual(rolled.rolled_back_to, version);
  } finally {
    fs.rmSync(prefix, { recursive: true, force: true });
  }
});

test("sweepOrphans marks replaced versions and expires old ones", () => {
  const prefix = fs.mkdtempSync(path.join(os.tmpdir(), "cex-prefix-"));
  try {
    const installer = new Installer(prefix, false);
    installer.placeDistribution(true);
    const current = installer.currentRef() as string;
    const oldDir = path.join(prefix, "versions", "0.0.1");
    fs.mkdirSync(oldDir, { recursive: true });
    const actions = installer.sweepOrphans(current);
    assert.ok(fs.existsSync(path.join(oldDir, ".orphaned_at")), "a replaced version gains the orphan marker");
    // age it past the grace window and sweep again
    fs.writeFileSync(path.join(oldDir, ".orphaned_at"), String(Math.floor(Date.now() / 1000) - 15 * 86400), "utf8");
    installer.sweepOrphans(current);
    assert.ok(!fs.existsSync(oldDir), "an expired orphan is removed");
    assert.ok(actions.some((a) => a.includes("orphaned")), actions.join("; "));
  } finally {
    fs.rmSync(prefix, { recursive: true, force: true });
  }
});

test("_cex_path resolves a versions layout through the current ref", async () => {
  const prefix = fs.mkdtempSync(path.join(os.tmpdir(), "cex-prefix-"));
  try {
    const installer = new Installer(prefix, false);
    installer.placeDistribution(true);
    const out = execFileSync(
      process.execPath,
      [path.join(prefix, "versions", installer.currentRef() as string, "dist", "skills_scripts", "_cex_path.js")],
      { env: { ...process.env, CEX_HOME: prefix }, timeout: 30000 },
    ).toString("utf8").trim();
    assert.equal(out, path.join(prefix, "versions", installer.currentRef() as string));
  } finally {
    fs.rmSync(prefix, { recursive: true, force: true });
  }
});
