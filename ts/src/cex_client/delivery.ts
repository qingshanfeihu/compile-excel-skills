// 交付面台账（issue #6 的 TS 端同构）：批目录里"谁没进卷、为什么"的产物。
// Python 端 `cex_client/delivery.py` 的模块说明有完整来龙去脉；这里是同一套规则：
// manifest.json（批身份）、engine_report.json（机读真理源）、delivery_report.md（总报告与
// 硬校验行）、unsuccessful_cases.md（未进卷案三段式叙事，仅有缺失时产）、facts.jsonl（最小
// 事实台账）。事件名只用 Python 端登记表（`cex_core/.../fact_events.py` 的 FACT_EVENTS，
// 332 名）里已有的三种：recompose_done、mechanical_case_submission_rejected、needs_decision。
// 引擎自己的 `facts.append_facts` 双端都调不动（惰性 import 的 routing_closed_sets 在转换
// 边界外）；写侧判据取可调用件拼装：Python 端走 `require_registered` 加 `idem_key`/`load_facts`
// 去重，TS 端的登记表镜像是一份滞后的快照（缺 `mechanical_case_submission_rejected`，历史
// 漂移，不在本修复范围），所以这里用客户端事件白名单把关——白名单三名字由测试钉住必须存在
// 于 Python 登记表；去重键取三种事件在 Python `idem_key` 里实际用到的形状。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { ClientError } from "./errors.js";
import { writeFileSafely, type Workspace } from "./workspace.js";

export const MANIFEST_SCHEMA = "cex.batch-manifest";
export const REPORT_SCHEMA = "cex.engine-report";
export const EV_RECOMPOSE_DONE = "recompose_done";
export const EV_SUBMISSION_REJECTED = "mechanical_case_submission_rejected";
export const EV_NEEDS_DECISION = "needs_decision";
const CLIENT_EVENTS: ReadonlySet<string> = new Set([
  EV_RECOMPOSE_DONE,
  EV_SUBMISSION_REJECTED,
  EV_NEEDS_DECISION,
]);

export const FACTS_NAME = "facts.jsonl";
export const MANIFEST_NAME = "manifest.json";
export const ENGINE_REPORT_NAME = "engine_report.json";
export const UNSUCCESSFUL_NAME = "unsuccessful_cases.md";
export const DELIVERY_REPORT_NAME = "delivery_report.md";

type Dict = Record<string, unknown>;

export const timestamp = (): string => {
  const d = new Date();
  const p = (n: number): string => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(
    d.getMinutes(),
  )}:${p(d.getSeconds())}`;
};

const sha256Bytes = (raw: Buffer): string =>
  crypto.createHash("sha256").update(raw).digest("hex");

// 与 Python `idem_key` 在这三种名字上的形状一致：拒收带 occurrence_id 各占一行；
// recompose_done / needs_decision 按 (ev, aid) 去重（原版语义：每批一条回执、每案一条待裁）。
const idemKey = (fact: Dict): string => {
  const ev = String(fact.ev ?? "");
  const aid = String(fact.aid ?? "");
  if (ev === EV_SUBMISSION_REJECTED) {
    const occurrence = String(fact.occurrence_id ?? "");
    if (occurrence) return `${ev}\u0000${aid}\u0000${occurrence}`;
  }
  return `${ev}\u0000${aid}`;
};

// ── 词表（交付文件名中文标签，抽取来的 display_lexicon 的 TS 镜像）────────
const DELIVERY_FILE_LABEL_CN: Record<string, string> = {
  "case.xlsx": "case.xlsx",
  "delivery_report.md": "交付报告",
  "unsuccessful_cases.md": "未通过详报",
  "engine_report.json": "机读报告",
  "facts.jsonl": "事实流",
};
const deliveryFileLabelCn = (name: unknown): string => {
  const text = String(name ?? "").trim();
  return DELIVERY_FILE_LABEL_CN[text] ?? text;
};

// ── 事实台账 ────────────────────────────────────────────────────────────

export function appendFacts(
  ws: Workspace,
  batch: string,
  events: Dict[],
): void {
  const ledgerPath = path.join(batch, FACTS_NAME);
  fs.mkdirSync(batch, { recursive: true });
  for (const event of events) {
    if (!CLIENT_EVENTS.has(String(event.ev ?? ""))) {
      throw new ClientError(
        `delivery ledger writes only the three registered client events; got ev=${JSON.stringify(
          String(event.ev ?? ""),
        )}`,
      );
    }
  }
  const existing = new Set<string>();
  if (fs.existsSync(ledgerPath) && !fs.lstatSync(ledgerPath).isSymbolicLink()) {
    try {
      for (const line of fs
        .readFileSync(ledgerPath, "utf8")
        .split("\n")
        .filter((l) => l.trim())) {
        const fact = JSON.parse(line) as Dict;
        if (fact && typeof fact === "object") existing.add(idemKey(fact));
      }
    } catch {
      // 读不出旧账不挡新账（与 Python 端同一手性）
    }
  }
  if (fs.existsSync(ledgerPath) && fs.lstatSync(ledgerPath).isSymbolicLink()) {
    throw new ClientError(`${ledgerPath} is a symlink; refusing to write the fact ledger through it`);
  }
  // recompose_done 不走去重（与 Python 端同一决定）：幂等键 (ev, aid) 是"一批一条"的设计，
  // 而客户端判据裁定会重发布，`_latest_recompose` 从尾往前找最新一条，被旧回执顶住就是错账。
  const fresh = events.filter(
    (event) => String(event.ev ?? "") === EV_RECOMPOSE_DONE || !existing.has(idemKey(event)),
  );
  if (!fresh.length) return;
  const fd = fs.openSync(
    ledgerPath,
    fs.constants.O_WRONLY |
      fs.constants.O_APPEND |
      fs.constants.O_CREAT |
      (fs.constants.O_NOFOLLOW ?? 0),
    0o600,
  );
  try {
    for (const event of fresh) {
      fs.writeSync(fd, JSON.stringify(canonicalOrder(event), null, 0) + "\n");
    }
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
}

const canonicalOrder = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(canonicalOrder);
  if (value && typeof value === "object") {
    const out: Dict = {};
    for (const key of Object.keys(value as Dict).sort()) {
      out[key] = canonicalOrder((value as Dict)[key]);
    }
    return out;
  }
  return value;
};

export const rejectionEvent = (
  outName: string,
  aid: string,
  attempt: number,
  violations: Dict[],
): Dict => ({
  ev: EV_SUBMISSION_REJECTED,
  ts: timestamp(),
  out_name: outName,
  aid,
  dispatch_id: "cex_client",
  attempt: Number(attempt) | 0,
  occurrence_id: crypto.randomUUID().replace(/-/g, ""),
  violations: violations.filter((v) => v && typeof v === "object").map((v) => ({ ...v })),
});

export const decisionEvent = (outName: string, aid: string, claims: string[]): Dict => ({
  ev: EV_NEEDS_DECISION,
  ts: timestamp(),
  out_name: outName,
  aid,
  claims: claims.map(String),
});

export const recomposeDoneEvent = (outName: string, receipt: Dict): Dict => ({
  ...receipt,
  ts: timestamp(),
  out_name: outName,
});

// ── 构建 ────────────────────────────────────────────────────────────────

export function buildManifest(state: Dict, batchManifest?: Dict | null): Dict {
  const receipt = (state.receipt as Dict) ?? {};
  const bm = batchManifest ?? {};
  const manifest: Dict = {
    schema: MANIFEST_SCHEMA,
    name: state.out_name,
    batch: state.out_name,
    generated_by: "cex_client",
    source_sha256: receipt.mindmap_source_sha256,
    machine_mindmap_sha256: receipt.machine_mindmap_sha256,
    governing_spec_status: receipt.governing_spec_status,
    governing_spec: receipt.governing_spec,
    governing_spec_sha256: receipt.governing_spec_sha256,
    defect_spec_status: receipt.defect_spec_status,
    written_autoids: [...((receipt.written_autoids as string[]) ?? [])],
    abandoned_autoids: [...((receipt.abandoned_autoids as string[]) ?? [])],
    contract_sha256_by_autoid: {
      ...((receipt.contract_sha256_by_autoid as Record<string, string>) ?? {}),
    },
    disclosure_sha256: receipt.disclosure_sha256,
  };
  for (const key of ["total", "bucket_counts", "source_status_counts", "typed_pending", "typed_ready", "groups"]) {
    if (key in bm) manifest[key] = bm[key];
  }
  return manifest;
}

export function buildEngineReport(state: Dict, emitOut: Dict, artifactShas: Record<string, string>): Dict {
  const receipt = (state.receipt as Dict) ?? {};
  const sealed = (state.sealed as Record<string, Dict>) ?? {};
  const submissions = (state.submissions as Record<string, Dict>) ?? {};
  const written = ((receipt.written_autoids as string[]) ?? []).map(String);
  const emitted = ((emitOut.emitted_autoids as string[]) ?? []).map(String);
  const missing = new Set(((emitOut.not_sealed_autoids as string[]) ?? []).map(String));
  const drifted: Record<string, string> = {};
  for (const d of (emitOut.not_emitted as Dict[]) ?? []) {
    drifted[String(d.autoid)] = String(d.reason);
  }
  const abandoned = ((receipt.abandoned_autoids as string[]) ?? []).map(String);
  const cases: Record<string, Dict> = {};
  for (const aid of written) {
    const last = (submissions[aid] as Dict) ?? {};
    const entry: Dict = {
      contract_sha256: (receipt.contract_sha256_by_autoid as Record<string, string>)?.[aid],
      status: emitted.includes(aid) ? "delivered" : "not_sealed",
    };
    if (Object.keys(last).length) {
      entry.last_submission = { at: last.at, status: last.status, violations: last.violations };
    }
    if (emitted.includes(aid)) {
      entry.mechanical_case_sha256 = sealed[aid]?.mechanical_case_sha256;
    } else if (aid in drifted) {
      entry.status = "sealed_file_replaced";
      entry.reason = drifted[aid];
    } else if (missing.has(aid)) {
      const status = String(last.status ?? "");
      entry.status = status === "rejected" || status === "needs_user_decision" ? status : "not_submitted";
    }
    cases[aid] = entry;
  }
  for (const aid of abandoned) cases[aid] = { status: "abandoned" };
  const notDelivered = written
    .filter((aid) => cases[aid].status !== "delivered")
    .sort();
  const count = (status: string): number =>
    written.filter((aid) => cases[aid].status === status).length;
  const totals = {
    contracted: written.length,
    delivered: emitted.length,
    not_sealed: missing.size,
    sealed_file_replaced: Object.keys(drifted).length,
    abandoned: abandoned.length,
    rejected_last: count("rejected"),
    needs_user_decision: count("needs_user_decision"),
    not_submitted: count("not_submitted"),
  };
  return {
    schema: REPORT_SCHEMA,
    batch: state.out_name,
    at: timestamp(),
    generated_by: "cex_client",
    totals,
    hard_check_contracted_equals_delivered: totals.contracted === totals.delivered,
    cases,
    not_delivered_autoids: notDelivered,
    verify: emitOut.verify,
    artifacts: { "case.xlsx": emitOut.xlsx, "cases.json": emitOut.cases_json, ...artifactShas },
  };
}

// ── 常见拒收码的出路（闸的硬拒码是开放集，落到兜底一句；与 Python 表同步）──
const CODE_GUIDANCE: Record<string, string> = {
  consistency_stage_unavailable:
    "本案绑定了管辖规格书：用 spec='none' 重新 prepare，或在支持规格判定的环境编译（issue #10）。",
  frozen_contract_drift: "契约卡在发布后变了：重跑 cex_author_prepare 读新卡，按新卡重提交本案。",
  contracts_republished: "提交期间卡被重发布：读新卡重提交本案。",
  autoid_not_dispatched: "该案号不在本批契约名单里：核对批名，或先 cex_author_prepare。",
  self_reported_seal: "去掉自带 seal 字段重提交：封印由引擎在闸后铸造。",
  payload_invalid_json: "按契约卡语言重写机械用例 JSON 后重提交。",
  not_an_object: "mechanical_case 必须是一个 JSON 对象，修正后重提交。",
  ssl_cert_load_invalid: "块规范化失败：按 references/authoring.md 的块语言修正后重提交。",
  gate_uncomputable: "机械用例无法过闸（结构问题）：按 detail 修正主体后重提交。",
};
const DEFAULT_GUIDANCE = "按上面逐条 violations 修正机械用例，用 cex_author_submit_case 重提交本案。";

const violationsLines = (violations: unknown): string[] => {
  const lines: string[] = [];
  for (const item of (violations as Dict[]) ?? []) {
    if (!item || typeof item !== "object") continue;
    lines.push(
      `- 闸 \`${String(item.gate ?? "")}\` · 码 \`${String(item.code ?? "")}\` · 位 \`${String(
        item.locus ?? "",
      )}\`：${String(item.detail ?? "")}`,
    );
  }
  return lines;
};

// ── 叙事渲染（三段式：时间线 / 机理引文 / 修复方案）──────────────────────

export function renderUnsuccessfulMd(report: Dict, manifest: Dict, titles: Record<string, string>): string {
  const batch = String(report.batch ?? "");
  const bad = ((report.not_delivered_autoids as string[]) ?? []).map(String).sort();
  const now = new Date();
  const p = (n: number): string => String(n).padStart(2, "0");
  const lines = [
    `# 未通过用例详报 — ${batch}`,
    `> 生成 ${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())} ${p(
      now.getHours(),
    )}:${p(now.getMinutes())} · 共 ${bad.length} 个 · 客户端交付台账（机读真理源见 \`${deliveryFileLabelCn(
      ENGINE_REPORT_NAME,
    )}\` \`${ENGINE_REPORT_NAME}\`）`,
    "",
  ];
  const cases = (report.cases as Record<string, Dict>) ?? {};
  const contracts = (manifest.contract_sha256_by_autoid as Record<string, string>) ?? {};
  for (const aid of bad) {
    const entry = (cases[aid] as Dict) ?? {};
    const status = String(entry.status ?? "");
    lines.push(`## ${aid} — ${titles[aid] ?? "(无标题)"}`);
    lines.push(`\n**状态**：${status}`);
    lines.push("\n### 时间线");
    const cardSha = String(contracts[aid] ?? "");
    lines.push(
      `- 投影发布：契约卡 \`contracts/${aid}.json\`${
        cardSha ? `（sha256 \`${cardSha.slice(0, 16)}…\`）` : ""
      }`,
    );
    const last = (entry.last_submission as Dict) ?? {};
    if (last.at) {
      lines.push(`- 最后一次提交 ${String(last.at)}：${String(last.status ?? "?")}`);
    } else {
      lines.push("- 最后一次提交：无记录（本案从未提交过机械用例）");
    }
    if (status === "sealed_file_replaced") {
      lines.push(`- 出件核对：${String(entry.reason ?? "封存文件与封存记录不符")}`);
    }
    lines.push("\n### 机理引文");
    const cited = violationsLines(last.violations);
    if (cited.length) {
      lines.push(...cited);
    } else if (status === "abandoned") {
      lines.push("- 投影期放弃（recompose abandon），本批不编写此案。");
    } else if (entry.reason) {
      lines.push(`- ${String(entry.reason)}`);
    } else {
      lines.push("- 无提交违规记录：案还没封进来（未提交或提交从未到过闸）。");
    }
    lines.push("\n### 修复方案");
    const codes = new Set(
      ((last.violations as Dict[]) ?? []).map((v) => String(v?.code ?? "")).filter(Boolean),
    );
    if (status === "sealed_file_replaced") {
      lines.push("- 封存文件被别的批覆盖或手改过：按当前契约卡重新提交本案，再 cex_author_emit。");
    } else if (status === "abandoned") {
      lines.push("- 无需修复：这是投影阶段的放弃案；要收编它得回到重组阶段。");
    } else {
      const guidance = [...codes].sort().map((code) => CODE_GUIDANCE[code]).filter(Boolean);
      if (guidance.length) lines.push(...guidance.map((g) => `- ${g}`));
      else lines.push(`- ${DEFAULT_GUIDANCE}`);
    }
    lines.push("");
  }
  return lines.join("\n") + "\n";
}

export function renderDeliveryMd(report: Dict, manifest: Dict, produced: Record<string, string>): string {
  const totals = (report.totals as Dict) ?? {};
  const passed = Boolean(report.hard_check_contracted_equals_delivered);
  const lines = [
    `# 交付报告 — ${String(report.batch ?? "")}`,
    `> 生成 ${String(report.at ?? "")} · 客户端交付台账（编排层在转换边界之外，本报告的判定与点名以状态与提交台账为准）`,
    "",
    "## 硬校验",
    `- contracted ${Number(totals.contracted ?? 0)} == delivered ${Number(
      totals.delivered ?? 0,
    )} → **${passed ? "通过" : "不通过"}**`,
    "",
  ];
  if (!passed) {
    lines.push(
      `**本卷不可作为完整交付使用**：以下案没有进卷，逐案叙事见 \`${deliveryFileLabelCn(
        UNSUCCESSFUL_NAME,
      )}\` \`${UNSUCCESSFUL_NAME}\`。`,
    );
    for (const aid of (report.not_delivered_autoids as string[]) ?? []) {
      const status = String(((report.cases as Record<string, Dict>)?.[aid] ?? {}).status ?? "?");
      lines.push(`- \`${aid}\`：${status}`);
    }
    lines.push("");
  }
  lines.push(
    "## 计数",
    `- 契约案 ${Number(totals.contracted ?? 0)} · 进卷 ${Number(totals.delivered ?? 0)} · 未封存 ${Number(
      totals.not_sealed ?? 0,
    )} · 封存文件被换 ${Number(totals.sealed_file_replaced ?? 0)} · 拒收 ${Number(
      totals.rejected_last ?? 0,
    )} · 待裁决 ${Number(totals.needs_user_decision ?? 0)} · 未提交 ${Number(
      totals.not_submitted ?? 0,
    )} · 放弃 ${Number(totals.abandoned ?? 0)}`,
    "",
    "## 交付文件",
  );
  for (const name of ["case.xlsx", "cases.json", ENGINE_REPORT_NAME, MANIFEST_NAME, UNSUCCESSFUL_NAME, DELIVERY_REPORT_NAME, FACTS_NAME]) {
    if (name in produced) lines.push(`- \`${name}\` — ${deliveryFileLabelCn(name)}`);
  }
  const verify = (report.verify as Dict) ?? {};
  lines.push("", "## 卷面核验", `- verify_batch：pass ${String(verify.pass ?? 0)} / fail ${String(verify.fail ?? 0)}`);
  for (const failure of ((verify.failures as unknown[]) ?? []).slice(0, 10)) {
    lines.push(`  - ${String(failure)}`);
  }
  lines.push("");
  return lines.join("\n") + "\n";
}

// ── 落盘 ────────────────────────────────────────────────────────────────

export function writeReports(
  ws: Workspace,
  state: Dict,
  batch: string,
  emitOut: Dict,
): Record<string, string> {
  const artifactShas: Record<string, string> = {};
  for (const [name, key] of [
    ["case.xlsx", "xlsx"],
    ["cases.json", "cases_json"],
  ] as const) {
    const p = emitOut[key];
    if (typeof p === "string" && fs.existsSync(p) && fs.statSync(p).isFile()) {
      artifactShas[`${name}.sha256`] = sha256Bytes(fs.readFileSync(p));
    }
  }
  let batchManifest: Dict | null = null;
  const bmPath = path.join(batch, "batch_manifest.json");
  if (fs.existsSync(bmPath)) {
    try {
      batchManifest = JSON.parse(fs.readFileSync(bmPath, "utf8")) as Dict;
    } catch {
      batchManifest = null;
    }
  }
  const manifest = buildManifest(state, batchManifest);
  const report = buildEngineReport(state, emitOut, artifactShas);
  const produced: Record<string, string> = {};
  for (const name of ["case.xlsx", "cases.json", FACTS_NAME]) {
    if (fs.existsSync(path.join(batch, name)) && !fs.lstatSync(path.join(batch, name)).isSymbolicLink()) {
      produced[name] = path.join(batch, name);
    }
  }
  const titles: Record<string, string> = {};
  for (const aid of (report.not_delivered_autoids as string[]) ?? []) {
    const intent = path.join(batch, "cases", String(aid), "intent.json");
    if (fs.existsSync(intent)) {
      try {
        titles[String(aid)] = String(
          (JSON.parse(fs.readFileSync(intent, "utf8")) as Dict).title ?? "",
        );
      } catch {
        /* 读不动标题不挡报告 */
      }
    }
  }
  const writes: [string, string][] = [];
  if ((report.not_delivered_autoids as string[])?.length) {
    writes.push([UNSUCCESSFUL_NAME, renderUnsuccessfulMd(report, manifest, titles)]);
  }
  writes.push([
    ENGINE_REPORT_NAME,
    JSON.stringify(canonicalOrder(report), null, 1),
  ]);
  writes.push([MANIFEST_NAME, JSON.stringify(canonicalOrder(manifest), null, 1)]);
  for (const [name, text] of writes) {
    const target = path.join(batch, name);
    writeFileSafely(ws.root, target, Buffer.from(text, "utf8"));
    produced[name] = target;
  }
  produced[DELIVERY_REPORT_NAME] = path.join(batch, DELIVERY_REPORT_NAME);
  writeFileSafely(
    ws.root,
    path.join(batch, DELIVERY_REPORT_NAME),
    Buffer.from(renderDeliveryMd(report, manifest, produced), "utf8"),
  );
  return produced;
}
