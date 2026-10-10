import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { ClientError } from "./errors.js";
import { Workspace, writeFileSafely } from "./workspace.js";
import { callTool, lease, leaseArgs, rememberTask, taskRecord, newerSubmissions } from "./gateway.js";
import { entryPath } from "./bundle.js";
import { caseFingerprints, canonicalJson } from "./fingerprints.js";

export const RESULT_SCHEMA = "ist.excel.device-run-result";
export const MAX_XLSX_BYTES = 32 * 1024 * 1024;
export const SENTINEL_AUTOID = "999999999999999";
const _AUTOID_RE = /^\d{12,24}$/;
export const RUNNER_LOST =
  "the gateway reports the run as lost: its runner exited without recording an end (gateway restart, OOM or an operator kill), so this run has no verdicts; resubmit the workbook";
export const EVIDENCE_DIR = "evidence";

const _G_LAYER_MARKERS = [
  "% invalid", "% unrecognized", "% unknown", "% error",
  "syntax error", "invalid input", "command not found",
];
const _TRANSIENT_MARKERS = [
  "timeout", "timed out", "read_until", "connection reset",
  "connection closed", "device_busy", "traceback", "not reachable",
];

const _FAIL_HEAD_RE = /#### Fail Num \d+: fail to find .* in:\s*$/;
const _FAIL_CONTEXT_LINES = 8;
const _RETURN_TAIL_CHARS = 600;

export function failedChecks(log: string): string[] {
  const lines = (log ?? "").split("\n");
  const out: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (!_FAIL_HEAD_RE.test(lines[i])) continue;
    const block = [lines[i].trim()];
    for (const follow of lines.slice(i + 1, i + 1 + _FAIL_CONTEXT_LINES)) {
      if (follow.includes("####")) break;
      if (follow.trim()) block.push(follow.trim());
    }
    out.push(block.join("\n"));
  }
  return out;
}

const _LOG_STAMP_RE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} /;

export function checkSummary(block: string): string {
  const lines = (block ?? "").split("\n").map((ln) => ln.replace(_LOG_STAMP_RE, "").trim()).filter(Boolean);
  if (!lines.length) return "";
  const head = lines[0].replace(/^#### Fail Num \d+: /, "");
  return lines.length > 1 ? `${head} → ${lines[lines.length - 1]}` : head;
}

const _VERDICT_BANNER_RE = /^#{10,}\s+(PASS|FAIL)\s+#{10,}$/;
const _FAILED_COUNT_RE = /^#{5,}\s+The failed check point num:\s*(\d+)\s+#{4,}$/;
const _PASSED_COUNT_RE = /^#{5,}\s+The passed check point num:\s*(\d+)\s+#{4,}$/;

export function frameworkVerdict(log: string, autoid: string): "pass" | "fail" | null {
  const lines = (log ?? "").split("\n").map((ln) => ln.replace(_LOG_STAMP_RE, "").trim()).filter(Boolean);
  const endRe = new RegExp(`^#{7}\\s+end case:\\s*${autoid.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);
  const ends = lines.map((ln, i) => (endRe.test(ln) ? i : -1)).filter((i) => i >= 0);
  if (ends.length !== 1 || ends[0] === 0) return null;
  const end = ends[0];
  const banner = lines[end - 1].match(_VERDICT_BANNER_RE);
  if (!banner || lines.slice(0, end - 1).some((ln) => _VERDICT_BANNER_RE.test(ln))) return null;
  const verdict = banner[1].toLowerCase() as "pass" | "fail";
  if (verdict === "pass") {
    const failed = lines.slice(0, end - 1).map((ln) => ln.match(_FAILED_COUNT_RE)).filter(Boolean).map((m) => parseInt(m![1], 10));
    const passed = lines.slice(0, end - 1).map((ln) => ln.match(_PASSED_COUNT_RE)).filter(Boolean).map((m) => parseInt(m![1], 10));
    if (failed.length > 1 || passed.length > 1 || failed.some((f) => f > 0) || (passed.length && passed[0] <= 0)) {
      return null;
    }
  }
  return verdict;
}

const MAX_FAILURE_ECHO_LINES = 8;
const _FRAME_ANNOTATION_RE = /^#{3,}/;
const _FRAME_STEP_RE = /^#{5,}\s/;
const _FRAME_HOST_PROMPT_RE = /^[A-Za-z][\w.\-]*[#$](?:\s|$)/;
const _FRAME_SEGMENT_RE = /^(?:=== .+ ===|\[[^\]]*\])$/;
const _FRAME_SEND_RE = /^\S+ - sends command in (?:config|enable): (.*)$/;
const _FRAME_TRIGGER_RE = /^\S+ executes command: (.*)$/;
const _FRAME_PROMPT_RE = /^APV(?:\(config\))?#(.*)$/;
const _ASSERTION_SUMMARY_RE = /^#{3,}\s*(?:Success|Fail)\s+Num\s+\d+\s*:\s*(successed|fail)\s+to\s+find\s*:?\s*(.*?)(?:\s+in\s*:\s*)?$/;

export function failureEchoLines(log: string, markers: string[]): string[] {
  if (!markers.length) return [];
  const hits = (log ?? "").split("\n").filter((ln) => markers.some((m) => ln.includes(m))).map((ln) => ln.trim());
  return hits.slice(0, MAX_FAILURE_ECHO_LINES);
}

function _echoFrames(text: string): [string[], string][] {
  const frames: [string[], string][] = [];
  let cur: string[] = [];
  let head = false;
  const flush = () => {
    if (!cur.length) return;
    const body = cur.slice(head ? 1 : 0).filter((ln) => !_FRAME_ANNOTATION_RE.test(ln)).join("\n");
    frames.push([[...cur], body]);
  };
  for (const raw of (text ?? "").split("\n")) {
    const line = raw.replace(_LOG_STAMP_RE, "").replace(/\s+$/, "");
    if (_FRAME_SEND_RE.test(line) || _FRAME_TRIGGER_RE.test(line) || _FRAME_STEP_RE.test(line) ||
        _FRAME_PROMPT_RE.test(line) || _FRAME_HOST_PROMPT_RE.test(line) || _FRAME_SEGMENT_RE.test(line)) {
      flush();
      cur = [line];
      head = true;
      continue;
    }
    cur.push(line);
  }
  flush();
  return frames;
}

export function failureEchoExpected(lines: string[], patterns: [string, string][], log: string): boolean {
  if (!lines.length || !patterns.length) return false;
  const covered = (text: string): boolean => {
    for (const [method, pattern] of patterns) {
      let matched = false;
      try {
        matched = method === "abs_found" ? text.includes(pattern) : new RegExp(pattern, "s").test(text);
      } catch {
        matched = false;
      }
      if (matched) return true;
    }
    return false;
  };
  const frames = log ? _echoFrames(log) : [];
  const occurrences: Record<string, number> = {};
  for (const line of lines) {
    const probe = line.replace(_LOG_STAMP_RE, "").trim();
    const summary = probe.match(_ASSERTION_SUMMARY_RE);
    if (summary) {
      const verdict = summary[1];
      const summaryPattern = summary[2].trim();
      if (verdict === "successed" && summaryPattern &&
          patterns.some(([m, p]) => (m === "found" || m === "abs_found") && p === summaryPattern)) {
        continue;
      }
      return false;
    }
    const hits = frames.flatMap(([rawLines, body]) =>
      rawLines.filter((raw) => raw.trim() === probe).map((raw) => [body, _FRAME_ANNOTATION_RE.test(raw)] as [string, boolean]));
    const occurrence = occurrences[probe] ?? 0;
    occurrences[probe] = occurrence + 1;
    if (frames.length && occurrence >= hits.length) return false;
    const [frameBody, matchedAnnotation] = hits[occurrence] ?? ["", false];
    if (frameBody) {
      if (covered(frameBody)) continue;
      return false;
    }
    if (frames.length && matchedAnnotation) return false;
    if (covered(probe || line)) continue;
    return false;
  }
  return true;
}

export function failureMarkers(ws: Workspace): string[] | null {
  try {
    const p = entryPath(ws, "projections", "domain_grammar");
    const grammar = p ? JSON.parse(fs.readFileSync(p, "utf8")) : null;
    const patterns = (grammar?.exec_failure_markers as Record<string, unknown> | undefined)?.patterns;
    if (!Array.isArray(patterns)) return null;
    return patterns.map(String).filter(Boolean);
  } catch {
    return null;
  }
}

export async function workbookFacts(data: Buffer): Promise<{ assertion_patterns: Record<string, string[][]>; sentinel: boolean }> {
  const { resolve_execution_sheet } = await import("../cex_core/ist_emit/excel_contract.js");
  const patterns: Record<string, string[][]> = {};
  let sentinel = false;
  const wb = new (await import("exceljs")).default.Workbook();
  await wb.xlsx.load(Buffer.from(data) as unknown as any);
  const [sheet, layout] = resolve_execution_sheet(wb, { allow_legacy: false });
  let current = "";
  for (let rowNo = layout.data_start; rowNo <= sheet.rowCount; rowNo++) {
    const values = sheet.getRow(rowNo).values as unknown[];
    const cells = Array.from({ length: 9 }, (_, i) => String(values[i + 1] ?? "").trim());
    if (cells[0] === SENTINEL_AUTOID) {
      sentinel = true;
      current = "";
      continue;
    }
    if (_AUTOID_RE.test(cells[0])) {
      current = cells[0];
      patterns[current] = patterns[current] ?? [];
    }
    if (current && cells[4] === "check_point" && ["found", "abs_found"].includes(cells[5]) && cells[6]) {
      patterns[current].push([cells[5], cells[6]]);
    }
  }
  return { assertion_patterns: patterns, sentinel };
}

export function provenanceFingerprints(provPath: string): Record<string, string> {
  let prov: Record<string, unknown>;
  try {
    prov = JSON.parse(fs.readFileSync(provPath, "utf8"));
  } catch {
    return {};
  }
  const out: Record<string, string> = {};
  for (const [autoid, entries] of Object.entries((prov.cases as Record<string, unknown>) ?? {})) {
    if (Array.isArray(entries)) {
      out[autoid] = crypto.createHash("sha256").update(canonicalJson(entries), "utf8").digest("hex");
    }
  }
  return out;
}

export function attributeFail(detailTail: string): Record<string, string> {
  const text = (detailTail ?? "").toLowerCase();
  for (const marker of _G_LAYER_MARKERS) {
    if (text.includes(marker)) {
      return { layer: "G", evidence: marker, note: "命令/语法层——回显含 CLI 错误标记" };
    }
  }
  for (const marker of _TRANSIENT_MARKERS) {
    if (text.includes(marker)) {
      return { layer: "transient?", evidence: marker, note: "疑似瞬态（超时/连接/忙）——同签名复发则非瞬态，不升格" };
    }
  }
  return { layer: "undetermined", evidence: "", note: "机械标记无法裁决，需会话按 detail_tail 语义归因（E/V/产品缺陷）" };
}

function _now(): string {
  return new Date().toISOString().slice(0, 19).replace("T", " ");
}

export function casesFingerprints(casesPath: string): Record<string, string> {
  let doc: unknown;
  try {
    doc = JSON.parse(fs.readFileSync(casesPath, "utf8"));
  } catch {
    return {};
  }
  return typeof doc === "object" && doc !== null ? caseFingerprints(doc as Record<string, unknown>) : {};
}

export function resolveXlsx(ws: Workspace, xlsx: string): string {
  let p = path.resolve(String(xlsx ?? ""));
  if (!path.isAbsolute(p)) {
    p = path.resolve(ws.root, p);
  }
  if (!p.startsWith(path.resolve(ws.root) + path.sep) || !fs.existsSync(p)) {
    throw new ClientError("xlsx must be an existing file inside the workspace");
  }
  if (fs.statSync(p).size > MAX_XLSX_BYTES) {
    throw new ClientError("workbook is larger than the gateway accepts");
  }
  return p;
}

export async function submit(ws: Workspace, xlsx: string, module?: string): Promise<Record<string, unknown>> {
  const p = resolveXlsx(ws, xlsx);
  const data = fs.readFileSync(p);
  const args: Record<string, unknown> = {
    ...leaseArgs(ws),
    xlsx_b64: data.toString("base64"),
  };
  if (module) args.module = module;
  const out = await callTool(ws, "case_submit", args);
  if (out.ok) {
    const localSha = crypto.createHash("sha256").update(data).digest("hex");
    if (out.sha256 !== localSha) {
      throw new ClientError("gateway staged a different workbook than the one sent");
    }
    let facts: Record<string, unknown> = {};
    try {
      facts = await workbookFacts(data);
    } catch {}
    rememberTask(ws, String(out.task_id), {
      xlsx: path.relative(ws.root, p).split(path.sep).join("/"),
      sha256: localSha,
      submitted_at: _now(),
      case_ids: out.case_ids ?? [],
      ...(out.submit_autoid ? { submit_autoid: out.submit_autoid } : {}),
      ...(out.module ? { module: out.module } : {}),
      ...facts,
      provenance_fp: provenanceFingerprints(path.join(path.dirname(p), "provenance.json")),
      case_fingerprints: casesFingerprints(path.join(path.dirname(p), "cases.json")),
    });
  }
  return out;
}

export async function status(ws: Workspace, taskId: string): Promise<Record<string, unknown>> {
  return callTool(ws, "case_status", { task_id: taskId });
}

function _submittedPatterns(ws: Workspace, record: Record<string, unknown>): Record<string, string[][]> | null {
  if (typeof record.assertion_patterns === "object" && record.assertion_patterns !== null) {
    return record.assertion_patterns as Record<string, string[][]>;
  }
  try {
    const data = fs.readFileSync(path.join(ws.root, String(record.xlsx ?? "")));
    if (record.xlsx && crypto.createHash("sha256").update(data).digest("hex") === record.sha256) {
      return (workbookFacts(data) as unknown as { assertion_patterns: Record<string, string[][]> }).assertion_patterns;
    }
  } catch {}
  return null;
}

export function caseEntry(
  case_: Record<string, unknown>,
  markers: string[] | null,
  patterns: Record<string, string[][]>,
): Record<string, unknown> {
  const autoid = String(case_.case_id);
  const recorded = String(case_.result ?? "").toLowerCase();
  const log = case_.log_stale ? "" : String(case_.log ?? "");
  const entry: Record<string, unknown> = { autoid };
  let reason: string | null = null;
  let verdict: string;
  if (recorded === "pass" || recorded === "fail") {
    const closing = frameworkVerdict(log, autoid);
    if (closing === recorded) {
      verdict = recorded;
    } else if (closing === null) {
      verdict = "broken";
      reason = `结果库记的是 ${recorded}，但本案日志里没有框架的收尾（PASS/FAIL 横幅紧跟 end case）：这一轮停在了本案里（超时被杀、崩溃或收尾时登不上设备），库里那行是本案开跑时写下的占位值（上一个案的结果），不是本案的判定`;
    } else {
      verdict = "broken";
      reason = `结果库记的是 ${recorded}，本案日志里框架收尾判的是 ${closing}，两边对不上`;
    }
  } else {
    verdict = "not_run";
  }
  if (verdict === "pass" && markers) {
    const echo = failureEchoLines(log, markers);
    const expected = (patterns[autoid] ?? []).filter((p): p is string[] => Array.isArray(p) && p.length === 2).map((p) => [String(p[0]), String(p[1])] as [string, string]);
    if (echo.length && !failureEchoExpected(echo, expected, log)) {
      verdict = "broken";
      reason = "框架判 pass，但本案日志里有执行失败回显，而本案的断言并不在等它：多半某条配置没生效、断言空真通过";
      entry.failure_echo = echo;
    }
  }
  entry.verdict = verdict;
  if (recorded && recorded !== verdict) {
    entry.recorded_result = recorded;
  }
  if (reason) entry.broken_reason = reason;
  if (verdict !== "pass") {
    entry.detail_tail = log;
    entry.failed_checks = failedChecks(log);
    if (case_.log_stale) {
      entry.note = "框架日志早于本次投递（上一轮残留），不作本次证据";
    }
    entry.attribution = attributeFail(log);
  }
  return entry;
}

const _SESSION_NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,120}\.txt$/;

export function writeSessions(
  ws: Workspace,
  batchDir: string,
  taskId: string,
  autoid: string,
  sessions: unknown,
): Record<string, string> {
  const written: Record<string, string> = {};
  if (typeof sessions !== "object" || sessions === null) return written;
  for (const [name, text] of Object.entries(sessions as Record<string, unknown>)) {
    if (!_SESSION_NAME_RE.test(name) || typeof text !== "string") continue;
    const p = path.join(batchDir, EVIDENCE_DIR, taskId, autoid, name);
    writeFileSafely(ws.root, p, Buffer.from(text, "utf8"));
    written[name] = path.relative(ws.root, p).split(path.sep).join("/");
  }
  return written;
}

export async function results(ws: Workspace, taskId: string): Promise<Record<string, unknown>> {
  const out = await callTool(ws, "case_results", { task_id: taskId });
  if (!out.ok || out.channel === "not_completed" || out.channel === "runner_lost") {
    return out;
  }
  const record = taskRecord(ws, taskId) ?? {};
  const markers = failureMarkers(ws);
  const patterns = _submittedPatterns(ws, record);
  let scanNote: string | null = null;
  if (markers === null) {
    scanNote = "数据包里读不到执行失败回显规则（domain_grammar.exec_failure_markers），pass 案没有扫空真";
  } else if (patterns === null) {
    scanNote = "不知道这次投递的断言（工作簿投递后改过），pass 案没有扫空真";
  }
  const batchDir = record.xlsx ? path.dirname(path.join(ws.root, String(record.xlsx))) : null;
  const cases = [];
  for (const case_ of (out.cases as Record<string, unknown>[]) ?? []) {
    const entry = caseEntry(case_, scanNote ? null : markers, patterns ?? {});
    if (batchDir !== null && case_.sessions) {
      entry.sessions = writeSessions(ws, batchDir, taskId, String(entry.autoid), case_.sessions);
    }
    cases.push(entry);
  }
  const verdicts = cases.map((c) => String(c.verdict));
  const totals = {
    cases: verdicts.length,
    pass: verdicts.filter((v) => v === "pass").length,
    fail: verdicts.filter((v) => v === "fail").length,
    broken: verdicts.filter((v) => v === "broken").length,
    not_run: verdicts.filter((v) => !["pass", "fail", "broken"].includes(v)).length,
  };
  let written: string | null = null;
  let note: string | null = null;
  const newer = record.xlsx ? newerSubmissions(ws, taskId) : [];
  if (record.xlsx && newer.length) {
    note = `${record.xlsx} was submitted again after this run (task ${newer[newer.length - 1]}); these are the older run's results, so the batch receipt was not overwritten`;
  } else if (record.xlsx) {
    const xlsx = path.join(ws.root, String(record.xlsx));
    const result: Record<string, unknown> = {
      schema: RESULT_SCHEMA,
      xlsx: record.xlsx,
      xlsx_sha256: out.xlsx_sha256,
      batch: path.basename(path.dirname(xlsx)),
      task_id: taskId,
      result_channel: out.channel,
      rc: out.rc,
      run_dir: out.run_dir,
      submit_autoid: out.submit_autoid ?? record.submit_autoid,
      module: out.module ?? record.module,
      report_dir: out.report_dir,
      sentinel: record.sentinel,
      failure_echo_scan: scanNote ?? "on",
      submitted: record.submitted_at,
      finished: _now(),
      cases,
      totals,
    };
    if (record.provenance_fp) result.provenance_fingerprints = record.provenance_fp;
    if (record.case_fingerprints) result.case_fingerprints = record.case_fingerprints;
    writeReceipts(result, path.dirname(xlsx), ws.root);
    written = path.relative(ws.root, path.join(path.dirname(xlsx), "run_receipt.md")).split(path.sep).join("/");
  }
  const compact = cases.map((c) => {
    const tail = c.detail_tail ? String(c.detail_tail).slice(-_RETURN_TAIL_CHARS) : c.detail_tail;
    return { ...c, detail_tail: tail };
  });
  const reply: Record<string, unknown> = { ...out, totals, cases: compact, receipt: written };
  if (note) reply.note = note;
  return reply;
}

export function writeReceipts(result: Record<string, unknown>, outDir: string, root?: string): void {
  const r = root ?? outDir;
  const put = (name: string, text: string) => {
    writeFileSafely(r, path.join(outDir, name), Buffer.from(text, "utf8"));
  };
  put("run_results.json", JSON.stringify(result, null, 1));
  const t = result.totals as Record<string, number>;
  const rc = result.rc;
  const lines = [
    "# 上机回执（run_receipt）",
    "",
    `- batch: \`${result.batch}\``,
    `- xlsx: \`${result.xlsx}\` (sha256 \`${String(result.xlsx_sha256 ?? "").slice(0, 16)}…\`)`,
    `- task_id: \`${result.task_id ?? ""}\``,
    `- 时间: ${result.submitted} → ${result.finished}`,
    `- 总数: ${t.cases} · pass ${t.pass} · fail ${t.fail} · broken ${t.broken ?? 0} · not_run ${t.not_run}`,
    `- result channel: ${result.result_channel} · 框架进程退出码 rc: ${rc}`,
  ];
  if (result.submit_autoid || result.run_dir) {
    lines.push(`- 跳板机上：落位 \`ist_staging_${result.module ?? "?"}/${result.submit_autoid ?? "?"}\`，报告目录 \`${result.report_dir ?? "report/" + result.run_dir}\``);
  }
  if (rc !== 0 && rc !== null && rc !== undefined) {
    lines.push(`- 注意：框架进程退出码 ${rc} 不是 0，这一轮没有正常跑完（崩溃或被杀）：没有收尾的案判 broken，没开跑的案是 not_run`);
  }
  if (result.failure_echo_scan !== null && result.failure_echo_scan !== "on") {
    lines.push(`- 注意：${result.failure_echo_scan}`);
  }
  if (result.sentinel) {
    lines.push("- 卷尾的 `999999999999999` 是出件时垫的哨兵案，不计入总数；原始日志末尾它的 FAIL 横幅不代表任何用例失败");
  }
  lines.push("", "| autoid | 判定 | 证据摘录 |", "|---|---|---|");
  for (const case_ of (result.cases as Record<string, unknown>[])) {
    const checks = (case_.failed_checks as string[]) ?? [];
    let evidence: string;
    if (case_.broken_reason) {
      const echo = ((case_.failure_echo as string[]) ?? [""])[0];
      evidence = String(case_.broken_reason) + (echo ? ` ⏎ ${echo}` : "");
    } else {
      evidence = checks.length ? checkSummary(checks[0]) : String(case_.detail_tail ?? "").slice(-160);
    }
    let noteText = (evidence || String(case_.note ?? "")).replace(/\n/g, " ⏎ ").slice(0, 240);
    const layer = (case_.attribution as Record<string, unknown> | undefined)?.layer;
    if (layer) noteText = `[${layer}] ${noteText}`;
    if (case_.sessions) {
      noteText += " · 会话转储：" + Object.values(case_.sessions as Record<string, string>).map((p) => `\`${p}\``).join("、");
    }
    lines.push(`| ${case_.autoid} | ${case_.verdict} | ${noteText || "-"} |`);
  }
  put("run_receipt.md", lines.join("\n") + "\n");
}

export async function runAndWait(
  ws: Workspace,
  xlsx: string,
  { module, pollS = 10, maxS = 2400, heartbeatS = 300 }: {
    module?: string;
    pollS?: number;
    maxS?: number;
    heartbeatS?: number;
  } = {},
): Promise<Record<string, unknown>> {
  const submitted = await submit(ws, xlsx, module);
  if (!submitted.ok) return submitted;
  const taskId = String(submitted.task_id);
  const deadline = Date.now() / 1000 + maxS;
  let lastBeat = Date.now() / 1000;
  while (Date.now() / 1000 < deadline) {
    const state = await status(ws, taskId);
    if (state.state === "done") {
      return { ...(await results(ws, taskId)), task_id: taskId };
    }
    if (state.state === "lost") {
      return { ok: false, task_id: taskId, state: "lost", error: RUNNER_LOST };
    }
    if (Date.now() / 1000 - lastBeat > heartbeatS) {
      await lease(ws, "heartbeat");
      lastBeat = Date.now() / 1000;
    }
    await new Promise((r) => setTimeout(r, pollS * 1000));
  }
  return { ok: false, task_id: taskId, error: `run did not finish within ${maxS}s; poll cex_case_status later` };
}
