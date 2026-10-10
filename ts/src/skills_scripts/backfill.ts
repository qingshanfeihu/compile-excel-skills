#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const RESULTS_SCHEMA = "ist.excel.device-run-result";
const FOOTPRINT_SCHEMA = "ist.excel.device-footprint";
const STATE_DIR = ".compile-excel";

function sha256(p: string): string {
  return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
}

function resolveXlsx(recorded: string, resultsPath: string): string | null {
  if (!recorded) return null;
  const p = recorded.replace(/^~/, process.env.USERPROFILE || process.env.HOME || "~");
  if (path.isAbsolute(p)) return fs.existsSync(p) && fs.statSync(p).isFile() ? p : null;
  let dir = path.dirname(resultsPath);
  for (;;) {
    if (fs.existsSync(path.join(dir, STATE_DIR))) {
      const candidate = path.join(dir, p);
      return fs.existsSync(candidate) && fs.statSync(candidate).isFile() ? candidate : null;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  const candidate = path.join(path.dirname(resultsPath), path.basename(p));
  return fs.existsSync(candidate) && fs.statSync(candidate).isFile() ? candidate : null;
}

function alreadyBackfilled(outPath: string, taskId: string): boolean {
  if (!taskId || !fs.existsSync(outPath)) return false;
  for (const line of fs.readFileSync(outPath, "utf8").split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      const rec = JSON.parse(line);
      if (rec && typeof rec === "object" && rec.run && rec.run.task_id === taskId) return true;
    } catch {}
  }
  return false;
}

export function main(argv: string[]): number {
  let resultsArg = "";
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--results") resultsArg = argv[++i] || "";
  }
  if (!resultsArg) {
    console.log(JSON.stringify({ ok: false, error: "usage: backfill --results <run_results.json>" }));
    return 2;
  }
  const resultsPath = path.resolve(resultsArg);
  let data: any;
  try {
    data = JSON.parse(fs.readFileSync(resultsPath, "utf8"));
  } catch (e: any) {
    const reason = e && e.code === "ENOENT" ? `results 不存在: ${resultsPath}` : `results 不可读: ${e.message || e}`;
    console.log(JSON.stringify({ ok: false, error: reason }));
    return 2;
  }
  if (!data || typeof data !== "object" || data.schema !== RESULTS_SCHEMA) {
    console.log(JSON.stringify({ ok: false, error: `schema 不符: ${JSON.stringify(data && data.schema)}` }));
    return 2;
  }
  const cases = data.cases;
  if (!Array.isArray(cases) || !cases.every((c: any) => c && typeof c === "object" && c.autoid)) {
    console.log(JSON.stringify({ ok: false, error: "run_results.json 的 cases 不是带 autoid 的对象数组" }));
    return 2;
  }

  let xlsxSha = String(data.xlsx_sha256 || "");
  let shaSource = "run_results";
  if (!xlsxSha) {
    const xlsx = resolveXlsx(String(data.xlsx || ""), resultsPath);
    xlsxSha = xlsx !== null ? sha256(xlsx) : "";
    shaSource = xlsx !== null ? "workbook" : "unavailable";
  }
  const taskId = String(data.task_id || "");
  const runIdentity: any = {
    task_id: taskId || null,
    xlsx: data.xlsx,
    xlsx_sha256: xlsxSha,
    xlsx_sha256_source: shaSource,
    submitted: data.submitted,
    finished: data.finished,
    result_channel: data.result_channel,
    batch: data.batch,
  };
  for (const key of ["rc", "run_dir", "submit_autoid"]) {
    if (data[key] !== null && data[key] !== undefined) runIdentity[key] = data[key];
  }

  const outPath = path.join(path.dirname(resultsPath), "footprint.jsonl");
  const totals = data.totals || {};
  const summary = {
    true_pass: totals.pass ?? 0, fail: totals.fail ?? 0,
    broken: totals.broken ?? 0, not_run: totals.not_run ?? 0,
  };
  if (alreadyBackfilled(outPath, taskId)) {
    console.log(JSON.stringify({ ok: true, footprint: outPath, appended: 0,
      note: `task ${taskId} 已经回填过，不重复追加`, ...summary }));
    return 0;
  }

  let written = 0;
  const lines: string[] = [];
  for (const c of cases) {
    const verdict = String(c.verdict || "not_run");
    const rec: any = {
      schema: FOOTPRINT_SCHEMA,
      autoid: String(c.autoid),
      verdict,
      true_pass: verdict === "pass",
      failed_checks: Array.isArray(c.failed_checks) ? c.failed_checks : [],
      attribution: c.attribution ? c.attribution.layer : undefined,
      note: c.note,
      run: runIdentity,
    };
    if (c.broken_reason) rec.broken_reason = c.broken_reason;
    lines.push(JSON.stringify(rec));
    written += 1;
  }
  fs.appendFileSync(outPath, lines.join("\n") + "\n", "utf8");

  console.log(JSON.stringify({ ok: true, footprint: outPath, appended: written, ...summary }));
  return 0;
}

if (require.main === module) {
  process.exit(main(process.argv.slice(2)));
}
