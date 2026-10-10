import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

const MODULE = "../cex_core/ist_emit/config";

async function loadFreshConfig(): Promise<any> {
  delete require.cache[require.resolve(MODULE)];
  return await import(MODULE);
}

test("missing config file falls back to defaults silently", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cex-config-"));
  process.env.COMPILE_EXCEL_COMPILER_CONFIG = path.join(dir, "absent.json");
  const warnings: unknown[] = [];
  const originalWarn = console.warn;
  console.warn = (...args: unknown[]) => {
    warnings.push(args);
  };
  try {
    const { CompilerConfig } = await loadFreshConfig();
    const cfg = CompilerConfig.load();
    assert.equal(cfg.build, "SAMPLE_BUILD_LOCAL");
    assert.equal(cfg.xlsx.header_row, 28);
  } finally {
    console.warn = originalWarn;
  }
  assert.deepEqual(warnings, [], "a missing config file is the documented normal state and must stay silent");
  delete process.env.COMPILE_EXCEL_COMPILER_CONFIG;
  fs.rmSync(dir, { recursive: true, force: true });
});

test("existing but unparsable config warns with a message, not a stack dump", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cex-config-"));
  const file = path.join(dir, "broken.json");
  fs.writeFileSync(file, "{not json", "utf8");
  process.env.COMPILE_EXCEL_COMPILER_CONFIG = file;
  const warnings: unknown[][] = [];
  const originalWarn = console.warn;
  console.warn = (...args: unknown[]) => {
    warnings.push(args);
  };
  try {
    const { CompilerConfig } = await loadFreshConfig();
    const cfg = CompilerConfig.load();
    assert.equal(cfg.build, "SAMPLE_BUILD_LOCAL");
  } finally {
    console.warn = originalWarn;
  }
  assert.equal(warnings.length, 1);
  const text = warnings[0].map((a) => String(a)).join(" ");
  assert.ok(text.includes("配置文件读取/解析失败"), text);
  assert.ok(!text.includes("\n    at "), `warning must not carry a stack trace: ${text}`);
  delete process.env.COMPILE_EXCEL_COMPILER_CONFIG;
  fs.rmSync(dir, { recursive: true, force: true });
});
