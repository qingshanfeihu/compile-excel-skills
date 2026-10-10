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

test("an upgrade keeps the previously installed node_modules", () => {
  const prefix = fs.mkdtempSync(path.join(os.tmpdir(), "cex-prefix-"));
  try {
    const first = new Installer(path.join(prefix, "dist-root"), false);
    first.placeDistribution(false);
    const markerDir = path.join(prefix, "dist-root", "node_modules", "exceljs");
    fs.mkdirSync(markerDir, { recursive: true });
    fs.writeFileSync(path.join(markerDir, "marker"), "kept", "utf8");
    const second = new Installer(path.join(prefix, "dist-root"), false);
    second.placeDistribution(true);
    assert.equal(
      fs.readFileSync(path.join(prefix, "dist-root", "node_modules", "exceljs", "marker"), "utf8"),
      "kept",
      "upgrade must carry node_modules into the new prefix",
    );
    assert.ok(!fs.existsSync(prefix + ".old"), "the old prefix must be cleaned up");
  } finally {
    fs.rmSync(prefix, { recursive: true, force: true });
  }
});
