#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _SOURCE_KINDS, _step_field } from "./compile_excel";
import { case_fingerprints } from "../cex_client/fingerprints";

const REWORK_SCHEMA = "ist.excel.rework-record";
const INIT_KEY = "__init__";
const BASELINE_FULL = "case_fingerprints";
const BASELINE_NOTES: Record<string, string> = {
  [BASELINE_FULL]: "逐案全行指纹（每一步 + 出处，外加 init_commands），取自 run_results.json，即上一轮真上机的卷面",
  provenance_fingerprints: "旧回执没有 case_fingerprints：退回只比 check_point（E/F/G + 出处）的旧口径，配置步、观察命令和 init_commands 的改动这里看不出来",
  "provenance.json": "旧回执没有任何指纹：退回只比 provenance.json 里的 check_point，配置步、观察命令和 init_commands 的改动这里看不出来",
  none: "没有可信基线（回执里没有指纹，provenance.json 缺失或在上机之后被重写过）：上一轮 pass 的案无法证明未变，一律按变化处理",
};

export class GateInputError extends Error {}

function cpEntries(autoid: string, case_: any): any[] {
  const out: any[] = [];
  for (const s of case_.steps || []) {
    if (!s || typeof s !== "object" || String(_step_field(s, "e") || "").trim() !== "check_point") continue;
    const src = s.source || {};
    let kind = String(src.kind || "").trim().toLowerCase();
    let ref = String(src.ref || "").trim();
    if (!_SOURCE_KINDS.includes(kind) || !ref) {
      kind = "author-verbatim";
      ref = `mindmap:${autoid}`;
    }
    out.push({
      E: "check_point",
      F: String(_step_field(s, "f") || ""),
      G: String(_step_field(s, "g") || ""),
      source: { kind, ref },
    });
  }
  return out;
}

function canonical(value: any): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${canonical(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function shaOf(value: any): string {
  return crypto.createHash("sha256").update(canonical(value), "utf8").digest("hex");
}

function priorFingerprints(provPath: string): Record<string, string> {
  let prov: any;
  try {
    prov = JSON.parse(fs.readFileSync(provPath, "utf8"));
  } catch {
    return {};
  }
  const out: Record<string, string> = {};
  for (const [autoid, entries] of Object.entries((prov || {}).cases || {})) {
    if (Array.isArray(entries)) out[String(autoid)] = shaOf(entries);
  }
  return out;
}

function baseline(prior: any, runPath: string, provPath: string): [string, Record<string, string>] {
  for (const key of [BASELINE_FULL, "provenance_fingerprints"]) {
    const fps = prior[key];
    if (fps && typeof fps === "object" && Object.keys(fps).length) {
      const out: Record<string, string> = {};
      for (const [k, v] of Object.entries(fps)) out[String(k)] = String(v);
      return [key, out];
    }
  }
  if (fs.existsSync(provPath) && fs.statSync(provPath).mtimeMs <= fs.statSync(runPath).mtimeMs) {
    const fps = priorFingerprints(provPath);
    if (Object.keys(fps).length) return ["provenance.json", fps];
  }
  return ["none", {}];
}

function readJson(p: string, what: string): any {
  let data: any;
  try {
    data = JSON.parse(fs.readFileSync(p, "utf8"));
  } catch (e: any) {
    if (e && e.code === "ENOENT") throw new GateInputError(`${what} 不存在: ${p}`);
    throw new GateInputError(`${what} 不可读: ${e.message || e}`);
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new GateInputError(`${what} 顶层必须是 JSON 对象: ${p}`);
  }
  return data;
}

function violation(autoid: string, code: string, detail: string): any {
  return { autoid, code, detail };
}

function prevRecord(batchDir: string): any {
  try {
    const record = JSON.parse(fs.readFileSync(path.join(batchDir, "rework.json"), "utf8"));
    return record && typeof record === "object" ? record : {};
  } catch {
    return {};
  }
}

export function run_gate(batchDir: string, casesPath: string, opts: { force?: boolean; reason?: string } = {}): [number, any] {
  const force = Boolean(opts.force);
  const reason = (opts.reason || "").trim();
  if (force && !reason) {
    throw new GateInputError('--force 必须带 --reason "<理由>"：整批判废重来要记录在案');
  }
  const doc = readJson(casesPath, "cases");
  const newCases = doc.cases;
  if (!Array.isArray(newCases)) throw new GateInputError("cases JSON 缺少 cases 数组");
  const batch = String(doc.batch || "").trim();
  if (batch && batch !== path.basename(batchDir)) {
    throw new GateInputError(`cases.json 属于批次 ${JSON.stringify(batch)}，不是 --batch-dir 的 ${JSON.stringify(path.basename(batchDir))}`);
  }
  const newIds = newCases.map((c: any) => String((c && typeof c === "object" ? c.autoid : "") || ""));
  if (newIds.includes("") || newIds.length !== newCases.length) {
    throw new GateInputError("cases 里每个案都必须是带 autoid 的对象");
  }

  const runPath = path.join(batchDir, "run_results.json");
  const prev = prevRecord(batchDir);
  if (!fs.existsSync(runPath)) {
    const record = { schema: REWORK_SCHEMA, round: 1, first_round: true,
      prior_fail_set: [], redispatch_set: [], kept_pass: [],
      violations: [], forced: force, reason: reason || null,
      cases: casesPath };
    fs.mkdirSync(batchDir, { recursive: true });
    fs.writeFileSync(path.join(batchDir, "rework.json"), JSON.stringify(record, null, 1), "utf8");
    return [0, { ok: true, round: 1, first_round: true, violations: [], rework: path.join(batchDir, "rework.json") }];
  }

  const prior = readJson(runPath, "run_results.json");
  const priorVerdicts: Record<string, string> = {};
  for (const c of prior.cases || []) {
    if (c && typeof c === "object" && String(c.autoid || "")) {
      priorVerdicts[String(c.autoid)] = String(c.verdict || "");
    }
  }
  const priorFail = new Set(Object.entries(priorVerdicts).filter(([, v]) => v !== "pass").map(([a]) => a));
  const priorPass = new Set(Object.entries(priorVerdicts).filter(([, v]) => v === "pass").map(([a]) => a));

  const [mode, base] = baseline(prior, runPath, path.join(batchDir, "provenance.json"));
  let newFp: Record<string, string>;
  if (mode === BASELINE_FULL) {
    try {
      const fp = case_fingerprints(doc);
      newFp = {};
      for (const [k, v] of Object.entries(fp)) newFp[String(k)] = String(v);
    } catch (e: any) {
      throw new GateInputError(`算不出本轮卷面的指纹: ${e.message || e}`);
    }
  } else {
    newFp = {};
    newIds.forEach((aid: string, i: number) => {
      newFp[aid] = shaOf(cpEntries(aid, newCases[i]));
    });
  }

  const violations: any[] = [];
  for (const aid of newIds) {
    if (!(aid in priorVerdicts)) {
      violations.push(violation(aid, "case_not_in_prior_run",
        "上一轮没有这个案：重派集只能取自上一轮的 fail 集（新增用例是另一批的事）"));
      continue;
    }
    if (!priorPass.has(aid)) continue;
    const before = base[aid];
    if (before === undefined) {
      violations.push(violation(aid, "pass_baseline_missing",
        "上一轮 pass，但基线里没有它的指纹，证明不了卷面没变（pass 锁卷面）"));
    } else if (before !== newFp[aid]) {
      violations.push(violation(aid, "pass_case_changed",
        "上一轮 pass，本轮卷面变了（pass 锁卷面；确需重来用 --force --reason 整批判废）"));
    }
  }
  const newIdSet = new Set(newIds);
  const keptPass = [...priorPass].filter((a) => newIdSet.has(a)).sort();
  if (mode === BASELINE_FULL && base[INIT_KEY] !== newFp[INIT_KEY] && keptPass.length) {
    violations.push(violation(INIT_KEY, "init_commands_changed",
      `文件级 init_commands 变了：它在每个案之前重放，上一轮 pass 的 ${keptPass.length} 个案因此全部变了（pass 锁卷面）`));
  }
  for (const aid of [...priorPass].filter((a) => !newIdSet.has(a)).sort()) {
    violations.push(violation(aid, "pass_case_dropped",
      "上一轮 pass 的案不在本轮卷面上：已验证的案不能悄悄拿掉"));
  }

  const redispatch = [...priorFail].filter((a) => newIdSet.has(a)).sort();
  const changedFail = redispatch.filter((a) => base[a] === undefined || base[a] !== newFp[a]).sort();
  const unchangedFail = redispatch.filter((a) => !changedFail.includes(a)).sort();
  const droppedFail = [...priorFail].filter((a) => !newIdSet.has(a)).sort();

  if (force) for (const item of violations) item.overridden = true;
  const ok = force || violations.length === 0;
  const result: any = {
    ok,
    baseline: mode,
    baseline_note: BASELINE_NOTES[mode],
    prior_run: { task_id: prior.task_id, xlsx_sha256: prior.xlsx_sha256, finished: prior.finished },
    prior_fail: [...priorFail].sort(),
    redispatch,
    changed_fail: changedFail,
    unchanged_fail: unchangedFail,
    kept_pass: keptPass,
    dropped_fail: droppedFail,
    violations,
    forced: force,
    reason: reason || null,
  };
  if (!ok) {
    result.rework = null;
    result.note = "闸未通过，rework.json 没有写：只改上一轮失败的案；pass 案确需重来时用 --force --reason 整批判废，理由会记进 rework.json";
    return [1, result];
  }

  const priorTask = String(prior.task_id || "");
  const prevRoundRaw = String(prev.round ?? "0");
  const prevRound = /^\d+$/.test(prevRoundRaw) ? parseInt(prevRoundRaw, 10) : 0;
  const sameRound = Boolean(priorTask) && prev.prior_task_id === priorTask && prevRound > 0;
  const roundNo = sameRound ? prevRound : prevRound + 1;
  const record = {
    schema: REWORK_SCHEMA,
    round: roundNo,
    prior_task_id: priorTask || null,
    cases: casesPath,
    baseline: mode,
    prior_fail_set: result.prior_fail,
    redispatch_set: redispatch,
    changed_fail: changedFail,
    unchanged_fail: unchangedFail,
    kept_pass: keptPass,
    dropped_fail: droppedFail,
    violations,
    forced: force,
    reason: reason || null,
  };
  const recordPath = path.join(batchDir, "rework.json");
  fs.writeFileSync(recordPath, JSON.stringify(record, null, 1), "utf8");
  result.round = roundNo;
  result.rework = recordPath;
  return [0, result];
}

export function main(argv: string[]): number {
  let batchDirArg = "";
  let resultsArg = "";
  let casesArg = "";
  let force = false;
  let reason = "";
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--batch-dir") batchDirArg = argv[++i] || "";
    else if (a === "--results") resultsArg = argv[++i] || "";
    else if (a === "--cases" || a === "--rework") casesArg = argv[++i] || "";
    else if (a === "--force") force = true;
    else if (a === "--reason") reason = argv[++i] || "";
  }
  if ((!batchDirArg && !resultsArg) || !casesArg) {
    console.log(JSON.stringify({ ok: false, error: "usage: rework_gate (--batch-dir DIR | --results run_results.json) --cases cases.json [--force --reason R]" }));
    return 2;
  }
  let batchDir: string;
  if (resultsArg) {
    const results = path.resolve(resultsArg);
    if (path.basename(results) !== "run_results.json") {
      console.log(JSON.stringify({ ok: false, error: `--results 要给上一轮的 run_results.json，不是 ${path.basename(results)}` }));
      return 2;
    }
    batchDir = path.dirname(results);
  } else {
    batchDir = path.resolve(batchDirArg);
  }
  try {
    const [code, result] = run_gate(batchDir, path.resolve(casesArg), { force, reason });
    console.log(JSON.stringify(result, null, 1));
    return code;
  } catch (e: any) {
    if (e instanceof GateInputError) {
      console.log(JSON.stringify({ ok: false, error: e.message }));
      return 2;
    }
    throw e;
  }
}

if (require.main === module) {
  process.exit(main(process.argv.slice(2)));
}

