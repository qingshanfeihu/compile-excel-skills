#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import ExcelJS from "exceljs";
import { XMLParser } from "fast-xml-parser";
import * as workspace from "../cex_client/workspace";
import * as bundle from "../cex_client/bundle";
import { ClientError } from "../cex_client/errors";
import { load_projection, resolve_vendor_command } from "../cex_core/vendor_cmd";
import {
  parse_g_arguments,
  strip_apv_command_kwargs,
} from "../cex_core/engine/case_compiler/excel_contract";
import { resolve_execution_sheet } from "../cex_core/ist_emit/excel_contract";

const REPORT_SCHEMA = "ist.excel.cmdtree-check";
const BUILD_RE = /cmdtree[_\-]?(\w+)\.xml$/i;
const SENTINEL_AUTOID = "999999999999999";
const INIT = "init";
const CLI_METHODS = new Set(["cmd_config", "cmds_config", "cmd_enable"]);
const ROOT_SHELL_METHOD = "cmd";
const PROMPT_ANSWERS = new Set(["YES", "NO"]);
const FRAMEWORK_WORDS = new Set(["page"]);

function field(step: any, key: string): any {
  if (key in step) return step[key];
  return step[key.toUpperCase()];
}

function selectedBuild(ws: workspace.Workspace | null): string {
  if (!ws) return "";
  try {
    return ws.selectedBuild;
  } catch (e) {
    if (e instanceof ClientError) return "";
    throw e;
  }
}

function findTree(explicit: string): [string | null, string] {
  const p = explicit.replace(/^~/, process.env.USERPROFILE || process.env.HOME || "~");
  if (!fs.existsSync(p) || !fs.statSync(p).isFile()) return [null, ""];
  const m = BUILD_RE.exec(path.basename(p));
  return [p, m ? m[1] : ""];
}

function findProjection(explicit: string, workspaceDir: string): string | null {
  if (explicit) {
    const p = explicit.replace(/^~/, process.env.USERPROFILE || process.env.HOME || "~");
    return fs.existsSync(p) && fs.statSync(p).isFile() ? p : null;
  }
  const ws = workspace.find(workspaceDir);
  if (!ws) return null;
  try {
    return bundle.entry_path(ws, "cmdtree", "vendor_stdlib_");
  } catch {
    return null;
  }
}

function normalized(step: any): any {
  return {
    E: String(field(step, "e") || "").trim(),
    F: String(field(step, "f") || "").trim(),
    G: field(step, "g") === null || field(step, "g") === undefined ? "" : String(field(step, "g")),
  };
}

function commandLines(groups: [string, any[]][]): [any[], any[]] {
  const cli: any[] = [];
  const shell: any[] = [];
  for (const [autoid, steps] of groups) {
    for (let index = 0; index < steps.length; index++) {
      const step = steps[index];
      const { E: e, F: f, G: g } = step;
      if (!e.startsWith("APV") || !g.trim()) continue;
      if (!CLI_METHODS.has(f) && f !== ROOT_SHELL_METHOD) continue;
      let command: string;
      try {
        command = strip_apv_command_kwargs(g, f);
      } catch {
        command = g;
      }
      const lines = command.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
      if (f === ROOT_SHELL_METHOD) {
        shell.push(...lines.map((line) => ({ autoid, e, f, command: line })));
        continue;
      }
      if (f === "cmd_config" && lines.length && PROMPT_ANSWERS.has(lines[0].toUpperCase()) && index > 0
          && steps[index - 1].E === e && steps[index - 1].F === "cmd_config") {
        let kwargs: any = {};
        try {
          [, kwargs] = parse_g_arguments(steps[index - 1].G, "cmd_config");
        } catch {}
        if (String(kwargs.prompt || "").trim()) continue;
      }
      cli.push(...lines.map((line) => ({ autoid, e, f, command: line })));
    }
  }
  return [cli, shell];
}

function groupsFromCases(casesPath: string): [string, any[]][] {
  const data = JSON.parse(fs.readFileSync(casesPath, "utf8"));
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new TypeError("cases JSON 顶层必须是对象");
  }
  const groups: [string, any[]][] = [];
  const rawInit = data.init_commands;
  const initGroups: Record<string, any> = rawInit && typeof rawInit === "object" && !Array.isArray(rawInit)
    ? rawInit : { APV_0: rawInit || [] };
  const initRows: any[] = [];
  for (const [device, commands] of Object.entries(initGroups)) {
    const init = Array.isArray(commands) ? commands.map((c: any) => String(c)).filter((c: string) => c.trim()) : [];
    if (init.length) initRows.push({ E: String(device), F: "cmds_config", G: init.join("\n") });
  }
  if (initRows.length) groups.push([INIT, initRows]);
  for (const case_ of data.cases || []) {
    if (!case_ || typeof case_ !== "object") continue;
    const steps = (case_.steps || []).filter((s: any) => s && typeof s === "object").map(normalized);
    groups.push([String(case_.autoid || ""), steps]);
  }
  return groups;
}

function cellValue(v: any): any {
  if (v === null || v === undefined) return null;
  if (typeof v === "object") {
    if ("text" in v) return v.text;
    if ("richText" in v) return v.richText.map((r: any) => r.text).join("");
    if ("result" in v) return v.result;
  }
  return v;
}

async function groupsFromXlsx(xlsx: string): Promise<[string, any[]][]> {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(xlsx);
  const [ws, layout] = resolve_execution_sheet(wb as any, { allow_legacy: false });
  const rows: any[][] = [];
  let r = 0;
  ws.eachRow({ includeEmpty: true }, (row, rowNumber) => {
    if (rowNumber < layout.data_start) return;
    const values: any[] = [];
    for (let c = 1; c <= 9; c++) values.push(cellValue(row.getCell(c).value));
    rows.push(values);
    r++;
  });
  const groups: [string, any[]][] = [];
  const init: any[] = [];
  let current: any[] | null = null;
  for (const row of rows) {
    const a = row[0] !== null ? String(row[0]).trim() : "";
    const c = row[2] !== null ? String(row[2]).trim() : "";
    const step = {
      E: String(row[4] || "").trim(),
      F: String(row[5] || "").trim(),
      G: row[6] === null ? "" : String(row[6]),
    };
    if (c === "1") {
      init.push(step);
      continue;
    }
    if (/^\d+$/.test(a) && a.length >= 12) {
      current = a !== SENTINEL_AUTOID ? [] : null;
      if (current !== null) groups.push([a, current]);
    }
    if (current !== null && step.E) current.push(step);
  }
  return (init.length ? [[INIT, init] as [string, any[]]] : []).concat(groups);
}

function checkWithProjection(lines: any[], shell: any[], projectionPath: string, report: any): void {
  const projection = load_projection(projectionPath);
  for (const item of lines) {
    const cmd = item.command;
    report.checked += 1;
    if (FRAMEWORK_WORDS.has(cmd.toLowerCase())) {
      report.ok += 1;
      continue;
    }
    const verdict = resolve_vendor_command(cmd, projection);
    if (verdict.hit) {
      report.ok += 1;
      continue;
    }
    if (!verdict.decided) {
      report.warnings.push(`${JSON.stringify(cmd)}: 投影无法判定（不是以命令词开头的行）`);
      report.ok += 1;
      continue;
    }
    report.unknown.push({
      autoid: item.autoid,
      command: cmd,
      matched_prefix: verdict.head || "",
      reason: verdict.reason_code === "parameter_contract_violation" ? "参数不合投影记录的契约" : "命令头不在投影里",
      reason_code: verdict.reason_code || "",
      parameter_error: verdict.parameter_error,
    });
  }
  for (const item of shell) {
    const verdict = resolve_vendor_command(item.command, projection);
    if (verdict.head) {
      report.warnings.push(`${item.autoid}: ${JSON.stringify(item.command)} 是一条 CLI 命令，但 F=cmd 在设备的 Linux root shell 里执行它，拿不到 CLI 回显；CLI 命令用 cmd_config`);
    }
  }
}

function treePaths(xmlPath: string): [Map<string, boolean>, Map<string, Set<string>>] {
  const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: "@_", preserveOrder: false });
  const doc = parser.parse(fs.readFileSync(xmlPath, "utf8"));
  const isItem = new Map<string, boolean>();
  const children = new Map<string, Set<string>>();

  function asArray(x: any): any[] {
    if (x === null || x === undefined) return [];
    return Array.isArray(x) ? x : [x];
  }

  function walk(node: any, prefix: string[]): void {
    for (const tag of Object.keys(node)) {
      if (tag.startsWith("@_")) continue;
      for (const child of asArray(node[tag])) {
        if (!child || typeof child !== "object") continue;
        const name = String(child["@_name"] || "").trim().toLowerCase();
        if (!name) continue;
        const p = [...prefix, name];
        const key = p.join("");
        if (tag === "item") {
          isItem.set(key, true);
        } else {
          if (!isItem.has(key)) isItem.set(key, false);
          walk(child, p);
        }
        const pkey = prefix.join("");
        if (!children.has(pkey)) children.set(pkey, new Set());
        children.get(pkey)!.add(name);
      }
    }
  }

  walk(doc, []);
  return [isItem, children];
}

function checkWithTree(lines: any[], isItem: Map<string, boolean>, children: Map<string, Set<string>>, report: any): void {
  for (const item of lines) {
    const cmd = item.command;
    report.checked += 1;
    if (FRAMEWORK_WORDS.has(cmd.toLowerCase())) {
      report.ok += 1;
      continue;
    }
    const toks = cmd.toLowerCase().split(/\s+/);
    let depth = 0;
    for (let d = toks.length; d > 0; d--) {
      if (isItem.has(toks.slice(0, d).join(""))) {
        depth = d;
        break;
      }
    }
    if (depth && isItem.get(toks.slice(0, depth).join(""))) {
      report.ok += 1;
      continue;
    }
    const prefix = depth ? toks.slice(0, depth).join("") : "";
    const sibsRaw = [...(children.get(prefix) || new Set<string>())].sort();
    const last = depth < toks.length ? toks[depth] : "";
    const rank = (s: string): [number, string] => {
      const near = s.startsWith(last.slice(0, 3))
        || s.replace(/s$/, "") === last.replace(/s$/, "")
        || s.includes(last.replace(/s$/, ""));
      return [near ? 0 : 1, s];
    };
    const sibs = sibsRaw.map((s) => rank(s) as [number, string])
      .sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1]))
      .map(([, s]) => s)
      .slice(0, 8);
    report.unknown.push({
      autoid: item.autoid,
      command: cmd,
      match_depth: depth,
      tokens: toks.length,
      matched_prefix: depth ? toks.slice(0, depth).join(" ") : "",
      reason: depth ? "head 只到 menu 不是完整命令" : "head 不在树中",
      suggestions: sibs,
    });
  }
}

export async function main(argv: string[]): Promise<number> {
  let casesArg = "", xlsxArg = "", projectionArg = "", treeArg = "";
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--cases") casesArg = argv[++i] || "";
    else if (a === "--xlsx") xlsxArg = argv[++i] || "";
    else if (a === "--projection") projectionArg = argv[++i] || "";
    else if (a === "--tree") treeArg = argv[++i] || "";
  }
  if (!casesArg && !xlsxArg) {
    console.log(JSON.stringify({ ok: false, error: "--cases 或 --xlsx 必填其一" }));
    return 2;
  }
  const src = path.resolve((casesArg || xlsxArg).replace(/^~/, process.env.USERPROFILE || process.env.HOME || "~"));
  if (!fs.existsSync(src)) {
    console.log(JSON.stringify({ ok: false, error: `输入不存在: ${src}` }));
    return 2;
  }
  let groups: [string, any[]][];
  try {
    groups = casesArg ? groupsFromCases(src) : await groupsFromXlsx(src);
  } catch (e: any) {
    console.log(JSON.stringify({ ok: false, error: `输入不可读: ${e.message || e}` }));
    return 2;
  }
  const [lines, shell] = commandLines(groups);

  if (!treeArg) {
    const projection = findProjection(projectionArg, path.dirname(src));
    if (projection === null) {
      console.log(JSON.stringify({ ok: false, error: "找不到命令树投影：先 cex_sync 同步数据包，或用 --projection 指定" }));
      return 2;
    }
    const report: any = { schema: REPORT_SCHEMA, projection, source: src, checked: 0, ok: 0, unknown: [], warnings: [] };
    try {
      checkWithProjection(lines, shell, projection, report);
    } catch (e: any) {
      console.log(JSON.stringify({ ok: false, error: `投影不可用: ${e.message || e}` }));
      return 2;
    }
    report.ok_flag = report.unknown.length === 0;
    console.log(JSON.stringify(report, null, 1));
    return report.ok_flag ? 0 : 1;
  }

  const [treePath, build] = findTree(treeArg);
  if (treePath === null) {
    console.log(JSON.stringify({ ok: false, error: `--tree 指定的文件不存在: ${treeArg}` }));
    return 2;
  }

  let isItem: Map<string, boolean>, children: Map<string, Set<string>>;
  try {
    [isItem, children] = treePaths(treePath);
  } catch (e: any) {
    console.log(JSON.stringify({ ok: false, error: `命令树解析失败: ${e.message || e}` }));
    return 2;
  }

  const report: any = { schema: REPORT_SCHEMA, tree: treePath, tree_build: build, source: src, checked: 0, ok: 0, unknown: [], warnings: [] };
  const ws = workspace.find(path.dirname(src));
  const wantBuild = selectedBuild(ws);
  if (build && wantBuild && !wantBuild.toLowerCase().includes(build.toLowerCase())) {
    report.warnings.push(`树 build=${build} 与工作区 device_build=${wantBuild} 不一致——树判定可能不代表床固件，建议换对应 build 的树`);
  } else if (build && ws !== null && !wantBuild) {
    report.warnings.push(`工作区${workspace.NO_DEVICE_BUILD}；暂时没法核对树 build=${build} 是否对应床固件`);
  }
  checkWithTree(lines, isItem, children, report);
  report.ok_flag = report.unknown.length === 0;
  console.log(JSON.stringify(report, null, 1));
  return report.ok_flag ? 0 : 1;
}

if (require.main === module) {
  main(process.argv.slice(2)).then((code) => process.exit(code));
}

