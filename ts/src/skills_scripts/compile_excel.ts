#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { CaseIR, FileIR, Row, Step } from "../cex_core/ist_emit/case_ir";
import { emit_xlsx } from "../cex_core/ist_emit/xlsx_emit";

export const SENTINEL_AUTOID = "999999999999999";
const AUTOID_RE = /^\d{12,24}$/;

export class CompileError extends Error {}

export function _step_field(step: any, lowerKey: string): any {
  const upper = ({ e: "E", f: "F", g: "G", h: "H", i: "I" } as Record<string, string>)[lowerKey];
  if (lowerKey in step) return step[lowerKey];
  return step[upper];
}

function validateBatch(batch: any): string {
  const b = String(batch || "").trim();
  if (!b) throw new CompileError("cases JSON 顶层缺少 batch 字段（批次名，决定产物目录 <--out>/<batch>/）");
  if (b.includes("/") || b.startsWith(".") || b === "/" || b === "\\") {
    throw new CompileError(`batch 名不安全: ${JSON.stringify(b)}`);
  }
  return b;
}

export function _steps_to_caseir(autoid: string, steps: any[], opts: { priority?: string; title?: string } = {}): CaseIR {
  const priority = opts.priority || "P1";
  const title = opts.title || "";
  const istSteps: Step[] = [];
  let hasCp = false;
  const seenVars = new Set<string>();
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (!s || typeof s !== "object" || Array.isArray(s)) {
      throw new CompileError(`用例 ${autoid}: step[${i}] 不是对象`);
    }
    const e = String(_step_field(s, "e") || "").trim();
    let f = String(_step_field(s, "f") || "").trim();
    if (!e || !f) throw new CompileError(`用例 ${autoid}: step[${i}] 缺少 E 或 F`);
    if (e === "test_env") f = f.toLowerCase();
    const rawG = _step_field(s, "g");
    let gVal = rawG === null || rawG === undefined ? "" : String(rawG);
    let hVal: string | null = _step_field(s, "h") || null;
    const iRaw = _step_field(s, "i");
    const iVal: string | null = iRaw === null || iRaw === undefined ? null : String(iRaw);
    if (e === "check_point" && !hVal && seenVars.has(gVal)) {
      hVal = gVal;
      gVal = "";
    }
    if (e === "check_point") {
      hasCp = true;
      if (hVal && f === "found") f = "abs_found";
    } else if (hVal) {
      seenVars.add(String(hVal));
    }
    if (e === "check_point" && f === "found_times") {
      const countText = (iVal || "").trim();
      const count = Number(countText);
      if (!Number.isInteger(count) || count <= 0 || String(count) !== countText) {
        throw new CompileError(`用例 ${autoid} step[${i}]: found_times 要求 I 列为正整数次数`);
      }
      if (hVal) {
        throw new CompileError(`用例 ${autoid} step[${i}]: found_times 要求 H 列为空`);
      }
    }
    const row: Row = { test_object: e, method: f, data: gVal, save_as: hVal, input_var: iVal };
    istSteps.push({ stmt_type: 2 + i, description: String(s.desc || s.description || ""), rows: [row] });
  }
  if (!hasCp) {
    throw new CompileError(`用例 ${autoid} 没有任何 check_point 步骤——上机必失败（pass 要求 success>0），请补一条 found 断言`);
  }
  return { autoid, priority: priority || "P1", title: title || `agent_${autoid}`, steps: istSteps };
}

function buildSentinel(): CaseIR {
  return {
    autoid: SENTINEL_AUTOID, priority: "P9", title: "sentinel-do-not-execute",
    steps: [{ stmt_type: 2, description: "sentinel",
      rows: [{ test_object: "time", method: "sleep", data: "1" }] }],
  };
}

export const INIT_DEVICES = ["APV_0", "APV_1", "APV_2"];

function initRows(raw: any): Row[] {
  if (raw === null || raw === undefined) return [];
  let groups: Record<string, any>;
  if (Array.isArray(raw)) {
    groups = { APV_0: raw };
  } else if (typeof raw === "object") {
    const unknown = Object.keys(raw).filter((k) => !INIT_DEVICES.includes(k)).sort();
    if (unknown.length) {
      throw new CompileError(`cases JSON 顶层 init_commands 的键只能是 ${INIT_DEVICES.join("/")}，不认 ${JSON.stringify(unknown)}`);
    }
    groups = raw;
  } else {
    throw new CompileError('cases JSON 顶层 init_commands 要么是命令数组，要么是 {"APV_0": [...], "APV_1": [...]} 这样按设备分组');
  }
  const rows: Row[] = [];
  for (const device of INIT_DEVICES) {
    const commands = groups[device];
    if (commands === null || commands === undefined) continue;
    if (!Array.isArray(commands)) throw new CompileError(`init_commands.${device} 必须是命令数组`);
    const shared = commands.map((c: any) => String(c)).filter((c: string) => c.trim()).join("\n").trim();
    if (shared) rows.push({ test_object: device, method: "cmds_config", data: shared });
  }
  return rows;
}

export function build_file_ir(doc: any, opts: { sentinel?: boolean } = {}): FileIR {
  const sentinel = opts.sentinel !== false;
  if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
    throw new CompileError("cases JSON 顶层必须是对象");
  }
  const batch = validateBatch(doc.batch);
  const cases = doc.cases;
  if (!Array.isArray(cases) || !cases.length) throw new CompileError("cases 必须是非空数组");

  const caseIrs: CaseIR[] = [];
  for (let idx = 0; idx < cases.length; idx++) {
    const case_ = cases[idx];
    if (!case_ || typeof case_ !== "object" || Array.isArray(case_)) {
      throw new CompileError(`cases[${idx}] 不是对象`);
    }
    const autoid = String(case_.autoid || "").trim();
    if (!autoid) throw new CompileError(`cases[${idx}] 缺少 autoid`);
    if (!AUTOID_RE.test(autoid)) {
      throw new CompileError(`cases[${idx}] autoid 必须是 12-24 位纯数字（InfoTest 框架按 ≥12 位数字识别用例边界，生产惯例 18 位），当前 ${JSON.stringify(autoid)}`);
    }
    if (caseIrs.some((existing) => existing.autoid === autoid)) {
      throw new CompileError(`autoid 重复: ${autoid}`);
    }
    const steps = case_.steps;
    if (!Array.isArray(steps) || !steps.length) {
      throw new CompileError(`用例 ${autoid}: steps 必须是非空数组`);
    }
    caseIrs.push(_steps_to_caseir(autoid, steps, {
      priority: String(case_.priority || "P1"),
      title: String(case_.description || ""),
    }));
  }

  const init = initRows(doc.init_commands);
  const casesOut = sentinel ? [...caseIrs, buildSentinel()] : caseIrs;
  return { feature: batch, author: "IST-Core-agent", init_rows: init, cases: casesOut, module: "ist_smoke" };
}

export const PROVENANCE_SCHEMA = "ist.excel.provenance";
export const _SOURCE_KINDS = [
  "author-verbatim", "author", "spec", "manual",
  "defectspec", "defect", "configbinding", "capabilityxml",
  "intent", "defect_spec", "capability_xml", "footprint", "env_facts", "skeleton",
  "config_derived", "captured_relation", "distribution_derived", "membership_derived",
  "status_derived",
];

export function _build_provenance(doc: any, fir: FileIR): [any, number] {
  const rawCases: Record<string, any> = {};
  for (const c of doc.cases || []) {
    if (c && typeof c === "object") rawCases[String(c.autoid || "").trim()] = c;
  }
  const prov: any = { schema: PROVENANCE_SCHEMA, batch: fir.feature, cases: {} };
  let defaulted = 0;
  for (const caseIr of fir.cases ?? []) {
    const raw = rawCases[caseIr.autoid] || {};
    const entries: any[] = [];
    for (const s of raw.steps || []) {
      if (String(_step_field(s, "e") || "").trim() !== "check_point") continue;
      const src = s.source || {};
      let kind = String(src.kind || "").trim().toLowerCase();
      let ref = String(src.ref || "").trim();
      if (!_SOURCE_KINDS.includes(kind) || !ref) {
        defaulted += 1;
        kind = "author-verbatim";
        ref = `mindmap:${caseIr.autoid}`;
      }
      entries.push({
        E: "check_point",
        F: String(_step_field(s, "f") || ""),
        G: String(_step_field(s, "g") || ""),
        source: { kind, ref },
      });
    }
    if (entries.length) prov.cases[caseIr.autoid] = entries;
  }
  return [prov, defaulted];
}

export async function compile_excel(casesPath: string, outDir: string, opts: { sentinel?: boolean } = {}): Promise<any> {
  const sentinel = opts.sentinel !== false;
  let doc: any;
  try {
    doc = JSON.parse(fs.readFileSync(casesPath, "utf8"));
  } catch (e: any) {
    if (e && e.code === "ENOENT") throw new CompileError(`cases 文件不存在: ${casesPath}`);
    throw new CompileError(`cases JSON 解析失败: ${e.message || e}`);
  }

  const fir = build_file_ir(doc, { sentinel });
  let outRoot = path.resolve(outDir);
  if (path.basename(outRoot) === fir.feature) outRoot = path.dirname(outRoot);
  const target = path.join(outRoot, fir.feature, "case.xlsx");
  const stats = await emit_xlsx(fir, target, { trusted_outputs_root: outRoot });
  const [prov, defaulted] = _build_provenance(doc, fir);
  fs.writeFileSync(path.join(outRoot, fir.feature, "provenance.json"), JSON.stringify(prov, null, 1), "utf8");
  stats.ok = true;
  stats.batch = fir.feature;
  stats.batch_dir = path.join(outRoot, fir.feature);
  stats.init_commands = (fir.init_rows ?? []).length;
  stats.sources_defaulted = defaulted;
  return stats;
}

export const EMIT_MARKER = "_generated";

function emitMarker(casesPath: string): string | null {
  let doc: any;
  try {
    doc = JSON.parse(fs.readFileSync(casesPath, "utf8"));
  } catch {
    return null;
  }
  if (doc && typeof doc === "object" && !Array.isArray(doc) && EMIT_MARKER in doc) {
    return String(doc[EMIT_MARKER] || EMIT_MARKER);
  }
  return null;
}

export async function main(argv: string[]): Promise<number> {
  let casesArg = "";
  let out = "compile_outputs";
  let noSentinel = false;
  let allowEditedEmit = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--cases") casesArg = argv[++i] || "";
    else if (a === "--out") out = argv[++i] || out;
    else if (a === "--no-sentinel") noSentinel = true;
    else if (a === "--allow-edited-emit") allowEditedEmit = true;
  }
  if (!casesArg) {
    console.log(JSON.stringify({ ok: false, error: "usage: compile_excel --cases cases.json [--out ROOT] [--no-sentinel] [--allow-edited-emit]" }));
    return 1;
  }

  const marker = emitMarker(casesArg);
  if (marker && !allowEditedEmit) {
    console.log(JSON.stringify({ ok: false, error:
      `${casesArg} 是 cex_author_emit 出件的 cases.json（${EMIT_MARKER}: ${marker}）。脑图批只经 cex_author_submit_case 重交用例、再 cex_author_emit 出件；手改出件后直接编译会绕过引擎的全部提交规则闸。用户明确要编译改过的出件时才加 --allow-edited-emit，并在报告里说明` }));
    return 1;
  }
  if (marker) {
    console.error(`警告：${casesArg} 是 cex_author_emit 出件的 cases.json；按 --allow-edited-emit 编译，产物不再是引擎封存的卷面，没有经过引擎的提交规则闸`);
  }

  try {
    const result = await compile_excel(casesArg, out, { sentinel: !noSentinel });
    console.log(JSON.stringify(result, null, 2));
    return 0;
  } catch (exc: any) {
    if (exc instanceof CompileError) {
      console.log(JSON.stringify({ ok: false, cases: casesArg, error: exc.message }));
    } else {
      console.log(JSON.stringify({ ok: false, error: `${exc.constructor.name}: ${exc.message || exc}` }));
    }
    return 1;
  }
}

if (require.main === module) {
  main(process.argv.slice(2)).then((code) => process.exit(code));
}
