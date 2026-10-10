#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import ExcelJS from "exceljs";
import {
  CONTRACT_MARKER,
  EXECUTION_HEADERS,
  PINNED_CONTRACT_SHA256,
  ExcelContractError,
  resolve_execution_sheet,
} from "../cex_core/ist_emit/excel_contract";
import { TEMPLATE_PATH } from "../cex_core/ist_emit/xlsx_emit";

const REPORT_SCHEMA = "ist.excel.verify-report";

class Report {
  checks: any[] = [];

  add(name: string, ok: boolean, detail = ""): void {
    this.checks.push({ name, ok: Boolean(ok), detail });
  }

  payload(p: string): any {
    const failures = this.checks.filter((c) => !c.ok);
    return {
      schema: REPORT_SCHEMA,
      path: p,
      totals: this.checks.length,
      pass: this.checks.length - failures.length,
      fail: failures.length,
      failures,
      checks: this.checks,
    };
  }
}

function cellText(ws: ExcelJS.Worksheet, row: number, col: number): string {
  const v = ws.getCell(row, col).value;
  if (v === null || v === undefined) return "";
  if (typeof v === "object" && "text" in (v as any)) return String((v as any).text);
  if (typeof v === "object" && "richText" in (v as any)) {
    return (v as any).richText.map((r: any) => r.text).join("");
  }
  return String(v);
}

async function efSetsFromTemplate(): Promise<[Set<string>, Map<string, Set<string>>]> {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(TEMPLATE_PATH);
  const [ws] = resolve_execution_sheet(wb as any, { allow_legacy: false });
  const eValues = new Set<string>();
  const fMap = new Map<string, Set<string>>();
  for (let r = 3; r <= 12; r++) {
    for (let idx = 0; idx < 6; idx++) {
      const col = 11 + idx;
      const text = cellText(ws, r, col).trim();
      if (!text) continue;
      if (idx === 0) {
        eValues.add(text);
      } else {
        const groupHeader = cellText(ws, 2, col);
        for (const eName of groupHeader.split("/")) {
          const name = eName.trim();
          if (!name) continue;
          if (!fMap.has(name)) fMap.set(name, new Set());
          fMap.get(name)!.add(text);
        }
      }
    }
  }
  return [eValues, fMap];
}

function commandEchoHits(data: any[][]): string[] {
  const hits: string[] = [];
  let lastCmd = "";
  const saved: Record<string, string> = {};
  for (const row of data) {
    const e = String(row[4] || "").trim();
    const f = String(row[5] || "").trim();
    const g = String(row[6] || "");
    const h = String(row[7] || "").trim();
    const iCol = String(row[8] || "").trim();
    if (e === "check_point") {
      if (h || !g.trim() || !["found", "not_found", "abs_found"].includes(f)) continue;
      const src = iCol ? saved[iCol] : lastCmd;
      if (!src) continue;
      let matched: boolean;
      try {
        matched = f === "abs_found" ? src.includes(g) : new RegExp(g, "s").test(src);
      } catch {
        continue;
      }
      if (matched) hits.push(`${f} ${JSON.stringify(g)} matches command ${JSON.stringify(src.slice(0, 48))}`);
      continue;
    }
    if (e.startsWith("APV") && f === "cmd_config") {
      if (h) saved[h] = g;
      else lastCmd = g;
    }
  }
  return hits;
}

const PROMPT_LIKE = /^(apv|router[a-z]?|[a-z_]+\(config\)#?|[#>*%-]{1,6}|\s*[#>-]{1,4}\s*)$/i;

function matchesEmpty(pattern: string): boolean {
  try {
    return new RegExp(pattern, "s").test("");
  } catch {
    return false;
  }
}

function tautologyFamily(data: any[][]): string[] {
  const bad: string[] = [];
  let lastCmd = "";
  const saved: Record<string, string> = {};
  for (const row of data) {
    const e = String(row[4] || "").trim();
    const f = String(row[5] || "").trim();
    const g = String(row[6] || "");
    const h = String(row[7] || "").trim();
    const iCol = String(row[8] || "").trim();
    if (e === "check_point") {
      if (h || !g.trim() || !["found", "not_found", "abs_found"].includes(f)) continue;
      const expected = g.trim();
      if (PROMPT_LIKE.test(expected)) {
        bad.push(`${f} ${JSON.stringify(expected)} 是提示符形态（每行回显都命中）→ 恒真${f === "not_found" ? "假" : ""}`);
        continue;
      }
      if (f === "found" && matchesEmpty(g)) {
        bad.push(`found /${g}/ 可匹配空串 → 恒真`);
        continue;
      }
      if (f === "not_found") {
        const src = iCol ? saved[iCol] : lastCmd;
        if (src) {
          const toks = new Set(src.split(/\s+/).map((t) => t.replace(/^["']|["']$/g, "")));
          if (toks.has(expected.replace(/^["']|["']$/g, ""))) {
            bad.push(`not_found ${JSON.stringify(expected)} 出现在命令 ${JSON.stringify(src.slice(0, 40))} 里（回显含命令行）→ 恒假`);
          }
        }
      }
      continue;
    }
    if (e.startsWith("APV") && f === "cmd_config") {
      if (h) saved[h] = g;
      else lastCmd = g;
    }
  }
  return bad;
}

function provenanceProblems(xlsx: string, data: any[][]): string[] {
  const provPath = path.join(path.dirname(xlsx), "provenance.json");
  if (!fs.existsSync(provPath)) {
    return [`缺 ${path.basename(provPath)}（先跑 compile_excel，不要手写 xlsx）`];
  }
  let prov: any;
  try {
    prov = JSON.parse(fs.readFileSync(provPath, "utf8"));
  } catch (e: any) {
    return [`provenance.json 不可读: ${e.message || e}`];
  }
  if (prov.schema !== "ist.excel.provenance") {
    return [`provenance schema 不符: ${JSON.stringify(prov.schema)}`];
  }
  const cases = prov.cases && typeof prov.cases === "object" ? prov.cases : {};
  const problems: string[] = [];
  const cpCounts = new Map<string, number>();
  for (const row of data) {
    const a = String(row[0] || "").trim();
    const e = String(row[4] || "").trim();
    if (/^\d+$/.test(a) && a.length >= 12 && a !== "999999999999999") {
      if (!cpCounts.has(a)) cpCounts.set(a, 0);
    }
    if (e === "check_point" && cpCounts.size) {
      const last = [...cpCounts.keys()].pop()!;
      cpCounts.set(last, cpCounts.get(last)! + 1);
    }
  }
  for (const [autoid, n] of cpCounts) {
    const entries = cases[autoid];
    if (!Array.isArray(entries) || !entries.length) {
      problems.push(`${autoid}: provenance 缺该 case 的来源记录`);
      continue;
    }
    if (entries.length !== n) {
      problems.push(`${autoid}: provenance ${entries.length} 条 ≠ xlsx check_point ${n} 条`);
    }
    for (const ent of entries) {
      const src = (ent || {}).source || {};
      if (!String(src.kind || "").trim() || !String(src.ref || "").trim()) {
        problems.push(`${autoid}: 存在 kind/ref 为空的来源记录`);
      }
    }
  }
  return problems;
}

const OBSERVATION_METHODS = new Set(["cmd", "cmd_config", "execute"]);

function danglingAssertions(data: any[][]): string[] {
  const bad: string[] = [];
  let autoid = "", inCase = false, hasResult = false, observe = false, last = "";
  for (const row of data) {
    const a = row[0] !== null && row[0] !== undefined ? String(row[0]).trim() : "";
    const c = row[2] !== null && row[2] !== undefined ? String(row[2]).trim() : "";
    if (a && !["0", "1", "None"].includes(c) && a !== EXECUTION_HEADERS[0]) {
      autoid = a; inCase = true; hasResult = false; observe = false; last = "";
    }
    if (!inCase) continue;
    const e = String(row[4] || "").trim();
    const f = String(row[5] || "").trim();
    const h = String(row[7] || "").trim();
    const iCol = String(row[8] || "").trim();
    if (!e) continue;
    if (e === "check_point") {
      if (iCol && f !== "found_times") continue;
      const what = `${f} ${JSON.stringify(String(row[6] || "").slice(0, 40))}`;
      if (!hasResult) {
        bad.push(`${autoid}: ${what} 之前本案没有不带 H 的观察步（框架 preflight 整卷拒跑）`);
      } else if (!observe) {
        bad.push(`${autoid}: ${what} 读的是 ${last} 的返回，不是观察回显`);
      }
      continue;
    }
    if (h) continue;
    hasResult = true;
    observe = e === "test_env" || OBSERVATION_METHODS.has(f);
    last = `${e}::${f}`;
  }
  return bad;
}

const INIT_NEUTRAL = /^(clear|no|show)\s|^(config(ure)?\s+t(erminal)?|conf\s+t|enable|end|exit)$/i;

function initIsolationProblems(data: any[][]): string[] {
  const problems: string[] = [];
  for (const row of data) {
    if (String(row[2]).trim() !== "1") continue;
    const e = String(row[4] || "").trim();
    if (!e.startsWith("APV_")) continue;
    for (const line of String(row[6] || "").split(/\r?\n/)) {
      const command = line.trim();
      if (command && !INIT_NEUTRAL.test(command)) {
        problems.push(command);
      }
    }
  }
  return problems;
}

export async function verifyBatch(xlsxPath: string): Promise<any> {
  const report = new Report();
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(xlsxPath);

  let sheet: ExcelJS.Worksheet;
  let layout: any;
  try {
    [sheet, layout] = resolve_execution_sheet(wb as any, { allow_legacy: false });
    report.add("execution-sheet resolve (pinned identity)", true,
      `header_row=${layout.header_row} data_start=${layout.data_start}`);
  } catch (exc: any) {
    if (exc instanceof ExcelContractError) {
      report.add("execution-sheet resolve (pinned identity)", false, String(exc.message || exc));
      return report.payload(xlsxPath);
    }
    throw exc;
  }
  const markerCell = sheet.getCell(1, 1).value;
  const markerSha = String(sheet.getCell(1, 3).value || "");
  report.add("contract marker present", markerCell === CONTRACT_MARKER, `A1=${JSON.stringify(markerCell)}`);
  report.add("marker contract sha pinned", markerSha === PINNED_CONTRACT_SHA256, markerSha.slice(0, 12) + "…");

  const grid: any[][] = [];
  sheet.eachRow({ includeEmpty: true }, (row) => {
    const values: any[] = [];
    for (let c = 1; c <= Math.max(16, row.cellCount); c++) {
      const v = row.getCell(c).value;
      if (v === null || v === undefined) values.push(null);
      else if (typeof v === "object" && "text" in (v as any)) values.push((v as any).text);
      else if (typeof v === "object" && "richText" in (v as any)) values.push((v as any).richText.map((r: any) => r.text).join(""));
      else if (typeof v === "object" && "result" in (v as any)) values.push((v as any).result);
      else values.push(v);
    }
    grid.push(values);
  });
  let data = grid.slice(layout.data_start - 1).map((row) => {
    const r = [...row];
    while (r.length < 9) r.push(null);
    return r;
  });
  data = data.filter((row) => row.slice(0, 9).some((v) => v !== null && v !== ""));

  const first = data[0] || [];
  report.add("author row first (C=0)",
    Boolean(data.length) && String(first[2]) === "0" && String(first[3] || "").includes("Author"));
  const stmtBad = data.map((row, i) => ({ row, i })).filter(({ row }) =>
    row[2] !== null && row[2] !== undefined && !["0", "1"].includes(String(row[2]).trim()) && !/^\d+$/.test(String(row[2]).trim()));
  report.add("stmt_type column discipline (0/1/int>=2)", stmtBad.length === 0,
    `bad_rows=${JSON.stringify(stmtBad.slice(0, 5).map(({ row }) => row[0] || row[4]))}`);

  const [eValues, fMap] = await efSetsFromTemplate();
  const efBad: string[] = [];
  for (const row of data) {
    const e = String(row[4] || "").trim();
    const f = String(row[5] || "").trim();
    if (!e) continue;
    if (!eValues.has(e)) {
      efBad.push(`E=${e}`);
      continue;
    }
    const allowed = fMap.get(e);
    if (allowed && f && !allowed.has(f)) efBad.push(`E=${e} F=${f}`);
  }
  report.add("E/F membership (template-derived)", efBad.length === 0,
    `violations=${JSON.stringify(efBad.slice(0, 5))} known_E=${JSON.stringify([...eValues].sort())}`);

  const autoids: string[] = [];
  let current: { autoid: string; cp: number } | null = null;
  const caseResults: [string, boolean, string][] = [];
  for (const row of data) {
    const a = row[0] !== null && row[0] !== undefined ? String(row[0]).trim() : "";
    const c = row[2] !== null && row[2] !== undefined ? String(row[2]).trim() : "";
    if (a && !["1", "0", "None"].includes(c) && a !== EXECUTION_HEADERS[0]) {
      if (current !== null) caseResults.push([current.autoid, current.cp > 0, ""]);
      current = { autoid: a, cp: 0 };
      if (autoids.includes(a)) caseResults.push([a, false, "autoid 重复"]);
      autoids.push(a);
    }
    const e = String(row[4] || "").trim();
    const f = String(row[5] || "").trim();
    if (current !== null && e === "check_point") {
      current.cp += 1;
      if (f === "found_times") {
        const iText = String(row[8] || "").trim();
        const hText = String(row[7] || "").trim();
        const count = Number(iText);
        const okFt = Number.isInteger(count) && count > 0 && String(count) === iText && !hText;
        if (!okFt) {
          caseResults.push([current.autoid, false, `found_times 契约违规：I=${JSON.stringify(iText)} H=${JSON.stringify(hText)}`]);
        }
      }
    }
  }
  if (current !== null) caseResults.push([current.autoid, current.cp > 0, ""]);
  const noCp = caseResults.filter(([aid, ok]) => !ok && aid !== "999999999999999").map(([aid]) => aid);
  report.add("every case has check_point", noCp.length === 0, `missing=${JSON.stringify(noCp)}`);
  report.add("autoid unique", autoids.length === new Set(autoids).size);
  const realAutoids = autoids.filter((a) => a !== "999999999999999");
  const badIds = realAutoids.filter((a) => !(/^\d+$/.test(a) && a.length >= 12));
  report.add("autoid >= 12 digits (framework boundary)", badIds.length === 0,
    `bad=${JSON.stringify(badIds)}（生产惯例 18 位）`);
  report.add("case count", true, `cases=${autoids.length} autoids=${JSON.stringify(autoids)}`);
  const dangling = danglingAssertions(data);
  report.add("every assertion reads an observation echo (no dangling check_point)", dangling.length === 0,
    `dangling=${JSON.stringify(dangling.slice(0, 4))}`);
  const echoBad = commandEchoHits(data);
  report.add("assertion does not match the command text", echoBad.length === 0,
    `hits=${JSON.stringify(echoBad.slice(0, 4))}`);
  const tautBad = tautologyFamily(data);
  report.add("tautology family (prompt-like / empty-match / not_found-in-command)",
    tautBad.length === 0, `hits=${JSON.stringify(tautBad.slice(0, 4))}`);
  const provBad = provenanceProblems(xlsxPath, data);
  report.add("provenance sidecar (expected-value sources)", provBad.length === 0,
    `problems=${JSON.stringify(provBad.slice(0, 4))}`);
  const initBad = initIsolationProblems(data);
  report.add("init rows only reset state (they replay before every case)", initBad.length === 0,
    `state-creating init commands=${JSON.stringify(initBad.slice(0, 4))}（放进用到它的那个案的步骤里）`);

  return report.payload(xlsxPath);
}

export async function main(argv: string[]): Promise<number> {
  let xlsxArg = "";
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--xlsx") xlsxArg = argv[++i] || "";
  }
  if (!xlsxArg) {
    console.log(JSON.stringify({ ok: false, error: "usage: verify_batch --xlsx <case.xlsx>" }));
    return 2;
  }
  const result = await verifyBatch(path.resolve(xlsxArg));
  console.log(JSON.stringify(result, null, 2));
  return result.fail === 0 ? 0 : 1;
}

if (require.main === module) {
  main(process.argv.slice(2)).then((code) => process.exit(code));
}
