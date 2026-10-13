// 规格一致性工件在客户端的机械打包（与 Python 端 cex_client/consistency.py 同一套口径）：
// 密封的重组结论 → verdict material → consistency_contract.json 覆盖层。
//
// 裁决本身不在这里做第二次：重组阶段按 [R11] 已让模型给每案下 ist.recompose-consistency
// 结论并密封，投影时引擎把引文盖章进契约卡。本模块把那枚密封结论机械打包成提交工件，
// 判据一律调 cex_core/engine 的同一批函数：resolve_consistency_evidence（引文按出处重解、
// cross_check 逐字节对合）、build/validate/write_consistency_contract、
// recompose_abandon_actionable（案内互斥的案级放弃先于材料推导，照引擎 submit 的顺序）。
//
// 与引擎的差别只在工件位置：没有服务端 dispatch 台账，accepted material 与回执摘要记在
// 客户端编写状态里，覆盖层落在 compile_outputs/<批>/cases/<autoid>/consistency_contract.json
// （客户端把该目录当引擎的 outputs_root 用）。引擎 validate_consistency_requirement 的
// complete 分支按服务端扁平布局核对覆盖层路径，与本批目录布局天然不同，客户端不接它。

import fs from "node:fs";
import path from "node:path";

import { ClientError } from "./errors";
import type { Workspace } from "./workspace";
import { writeFileSafely } from "./workspace";

// verdict 映射：重组结论（三值闭集）→ 材料 verdict（引擎闭集 {consistent, conflict}）。
// underdetermined 映射成 consistent：案继续编（缺的前置由编写阶段补步骤），
// 规格条文仍是它兑现断言的出处——它与规格并不互斥，只是程序还没说够。
export const VERDICT_MAP: Record<string, string> = {
  consistent: "consistent", underdetermined: "consistent", mutually_exclusive: "conflict",
};

export const STATUS_SEALED = "sealed";
export const STATUS_ABANDONED = "abandoned";
export const STATUS_PENDING = "pending_record";

// cex_consistency_record 接受的模型字段：draft 十键里除 schema/autoid 之外的部分，
// 外加卡上无结论时的 verdict。引文字段允许省略（引擎按 locator 盖章）；给了就得逐字对合。
const MODEL_KEYS = new Set(["verdict", "spec_locator", "case_locator", "incompatibility",
  "premises", "spec_clauses", "spec_quote", "case_quote"]);
const PREMISE_DRAFT_KEYS = ["origin", "locator", "text"] as const;

export type ConsistencyOutcome = Record<string, any>;

function _detail(code: string): string {
  // 把引擎的失败码翻译成这一层的确切出路（面向模型，英文）。
  const text = String(code || "");
  if (text.includes("clause")) {
    return "the spec_clauses do not tile the whole engine-stamped spec_quote (every "
      + "character, in order, no gaps): slice the cited span completely as "
      + "{text, disposition, reason} objects";
  }
  if (text.includes("text_field")) {
    return "every evidence field must be a non-empty string: spec_locator, case_locator, "
      + "incompatibility, and both quotes the engine stamps from them";
  }
  if (text.includes("premises_missing")) {
    return "cite the premises that carry the contradiction ({origin: spec|case, locator})";
  }
  if (text.includes("locator") || text.includes("drift")) {
    return "a locator does not resolve against the sealed sources, or the quote differs "
      + "from the engine-stamped bytes: re-read the bound spec file and the case source "
      + "and cite exact locators (spec:<file>:<line[-line]>, title, step:<n>, "
      + "expectation:<label>, orphan_note:<n>, defect:<ticket>:<id>:title|description)";
  }
  if (text.includes("identity") || text.includes("keys")) {
    return "the verdict draft must carry exactly the ten keys of the consistency material";
  }
  if (text.includes("conclusion_missing")) {
    return "this batch is bound to a governing spec, so every complete case needs the "
      + "case-vs-spec conclusion";
  }
  return "repair the exact reason cited in this violation";
}

function _pending(code: string): ConsistencyOutcome {
  const c = String(code || "consistency_verdict_missing");
  return { status: STATUS_PENDING, code: c, detail: _detail(c) };
}

function _abandoned(conclusion: any): ConsistencyOutcome {
  const c = conclusion && typeof conclusion === "object" ? conclusion : {};
  const evidence: Record<string, string> = {};
  for (const field of ["spec_locator", "spec_quote", "case_locator", "case_quote", "incompatibility"]) {
    evidence[field] = String(c[field] ?? "");
  }
  return {
    status: STATUS_ABANDONED, code: "case_abandoned_by_consistency", evidence,
    detail: "the recompose stage judged this case and its bound specification mutually "
      + `exclusive on two complete sources (spec ${JSON.stringify(evidence.spec_locator)}); `
      + "the case is abandoned at case level — no workbook, no question to a human; "
      + "nothing here is repairable by resubmitting",
  };
}

function _cleanPremise(item: any): Record<string, any> {
  // 卡片结论里的 premises 可能带材料层字段（source_sha256）；draft 只认
  // {origin, locator, text}，逐键过滤，别把材料字段喂回 draft 闸。
  if (!item || typeof item !== "object") return {};
  const out: Record<string, any> = {};
  for (const key of PREMISE_DRAFT_KEYS) if (key in item) out[key] = item[key];
  return out;
}

export async function draftFromConclusion(aid: string, conclusion: Record<string, any>):
  Promise<[Record<string, any> | null, string]> {
  // 密封结论 → 十键 draft：丢 missing_preconditions/authored_conflict，缺的可选字段补 ''。
  const { _CONSISTENCY_DRAFT_SCHEMA } = await import("../cex_core/engine/case_compiler/mindmap_contract_projector.js");
  const verdict = VERDICT_MAP[String(conclusion.verdict ?? "")];
  if (verdict === undefined) return [null, "consistency_verdict_invalid"];
  const premises = conclusion.premises;
  const draft: Record<string, any> = {
    schema: _CONSISTENCY_DRAFT_SCHEMA, autoid: aid, verdict,
    spec_quote: String(conclusion.spec_quote ?? ""),
    case_quote: String(conclusion.case_quote ?? ""),
    spec_locator: String(conclusion.spec_locator ?? ""),
    case_locator: String(conclusion.case_locator ?? ""),
    incompatibility: String(conclusion.incompatibility ?? ""),
    premises: Array.isArray(premises) ? premises.map(_cleanPremise) : [],
    spec_clauses: conclusion.spec_clauses,
  };
  return [draft, ""];
}

export async function draftForRecord(aid: string, conclusion: any, model: any):
  Promise<[Record<string, any> | null, string]> {
  // cex_consistency_record 的入口整形：卡上有结论时 verdict 由映射强制（模型改不动，
  // 给了不一致的按 consistency_verdict_frozen 拒），卡上没有结论时才由模型补判
  // {consistent|conflict}。
  const { _CONSISTENCY_DRAFT_SCHEMA } = await import("../cex_core/engine/case_compiler/mindmap_contract_projector.js");
  if (!model || typeof model !== "object" || Array.isArray(model)) return [null, "record_must_be_object"];
  const extra = Object.keys(model).filter((k) => !MODEL_KEYS.has(k)).sort();
  if (extra.length) return [null, "record_keys_invalid: " + extra.join(", ")];
  let frozen: string | null = null;
  if (conclusion && typeof conclusion === "object") {
    frozen = VERDICT_MAP[String(conclusion.verdict ?? "")] ?? null;
    if (frozen === null) return [null, "consistency_verdict_invalid"];
  }
  const declared = String(model.verdict ?? "").trim();
  let verdict: string;
  if (frozen !== null) {
    if (declared && declared !== frozen) return [null, "consistency_verdict_frozen"];
    verdict = frozen;
  } else {
    if (declared !== "consistent" && declared !== "conflict") {
      return [null, "consistency_identity_or_verdict_invalid"];
    }
    verdict = declared;
  }
  const premises = model.premises;
  if (!Array.isArray(premises)) return [null, "consistency_conflict_premises_missing"];
  const draft = {
    schema: _CONSISTENCY_DRAFT_SCHEMA, autoid: aid, verdict,
    spec_quote: String(model.spec_quote ?? ""),
    case_quote: String(model.case_quote ?? ""),
    spec_locator: String(model.spec_locator ?? ""),
    case_locator: String(model.case_locator ?? ""),
    incompatibility: String(model.incompatibility ?? ""),
    premises: premises.map(_cleanPremise),
    spec_clauses: model.spec_clauses,
  };
  return [draft, ""];
}

export async function landMaterial(opts: {
  aid: string; draft: Record<string, any>; card: Record<string, any>; cardSha256: string;
  mmCase: Record<string, any>; mindmapText: string; specName: string | null;
  specText: string | null; defectReceipt: Record<string, any> | null; caseRoot: string;
}): Promise<ConsistencyOutcome> {
  // draft →（引擎复核）accepted material →（引擎铸造与核验）覆盖层落盘。三态返回，
  // 不抛引擎异常；要存的凭据是 accepted 那份材料（引文与 source_sha256 都是引擎重解过的
  // 字节），不是 draft。
  const { resolve_consistency_evidence } = await import("../cex_core/engine/case_compiler/mindmap_contract_projector.js");
  const { build_consistency_contract, consistency_material_receipt_sha256,
    validate_consistency_contract, write_consistency_contract } =
    await import("../cex_core/engine/case_compiler/consistency_contract.js");
  const { aid, draft, card, cardSha256, mmCase, mindmapText, specName, specText,
    defectReceipt, caseRoot } = opts;
  const [state, reason, accepted] = resolve_consistency_evidence(mmCase, draft, {
    mindmap_text: mindmapText, governing_spec: specName, spec_text: specText,
    defect_spec_receipt: defectReceipt,
  });
  if (state === "invalid") return _pending(String(reason));
  if (!accepted || typeof accepted !== "object") return _pending("consistency_verdict_missing");
  if (state === "conflict") return _abandoned(accepted);
  if (state !== "consistent") return _pending("consistency_identity_or_verdict_invalid");
  let overlay: Record<string, any>;
  try {
    overlay = build_consistency_contract({ autoid: aid, base_contract: card,
      base_contract_sha256: cardSha256, accepted_material: accepted, machine_case: mmCase });
  } catch (exc) {
    return _pending(`consistency_contract_invalid: ${exc}`);
  }
  const receipt = consistency_material_receipt_sha256(accepted);
  const error = validate_consistency_contract(overlay, { base_contract: card,
    base_contract_sha256: cardSha256, accepted_material: accepted,
    consistency_receipt_sha256: receipt, machine_case: mmCase });
  if (error) return _pending(`consistency_contract_invalid: ${error}`);
  let overlaySha: string;
  try {
    // 引擎自己的落盘（canonical bytes、0600、原子）：别经 write_json_atomic，
    // 换个序列化就等于换一个 sha。
    [, overlaySha] = write_consistency_contract(caseRoot, overlay);
  } catch (exc) {
    throw new ClientError(`the consistency overlay for ${aid} cannot be written: ${exc}`);
  }
  const endorsement = overlay.spec_endorsement;
  return { status: STATUS_SEALED, material: accepted, receipt_sha256: receipt,
    overlay_sha256: overlaySha,
    scope: (endorsement && endorsement.scope) || { kind: "case" } };
}

export async function deriveFromConclusion(opts: {
  aid: string; card: Record<string, any>; cardSha256: string; mmCase: Record<string, any>;
  mindmapText: string; specName: string | null; specText: string | null;
  defectReceipt: Record<string, any> | null; caseRoot: string;
}): Promise<ConsistencyOutcome> {
  // 密封卡结论 → 提交工件的默认路（prepare 用）。案内互斥先按引擎的放弃判据定案，
  // 再谈材料能不能铸出来——顺序照引擎 submit。
  const { recompose_abandon_actionable } = await import("../cex_core/engine/ist_core/tools/device/mechanical_case_submit_tool.js");
  const { aid, card } = opts;
  const conclusion = card.consistency;
  if (conclusion && typeof conclusion === "object"
      && recompose_abandon_actionable(card, { spec_surface_present: true })) {
    return _abandoned(conclusion);
  }
  if (!conclusion || typeof conclusion !== "object") {
    const outcome = _pending("consistency_conclusion_missing");
    outcome.fixed_verdict = null;
    return outcome;
  }
  const [draft, error] = await draftFromConclusion(aid, conclusion);
  if (draft === null) {
    const outcome = _pending(error);
    outcome.fixed_verdict = null;
    return outcome;
  }
  const outcome = await landMaterial({ ...opts, draft });
  outcome.fixed_verdict = draft.verdict;
  return outcome;
}

export async function recordMaterial(opts: {
  aid: string; conclusion: any; model: any; card: Record<string, any>; cardSha256: string;
  mmCase: Record<string, any>; mindmapText: string; specName: string | null;
  specText: string | null; defectReceipt: Record<string, any> | null; caseRoot: string;
}): Promise<ConsistencyOutcome> {
  // cex_consistency_record 的推导：模型补包证据，verdict 冻结规则见 draftForRecord。
  const { aid, conclusion, model } = opts;
  const [draft, error] = await draftForRecord(aid, conclusion, model);
  if (draft === null) {
    const outcome = _pending(error);
    outcome.record_error = error;
    return outcome;
  }
  const outcome = await landMaterial({ ...opts, draft });
  outcome.fixed_verdict = draft.verdict;
  return outcome;
}

export async function overlayPath(caseRoot: string, aid: string): Promise<string> {
  const { consistency_contract_path } = await import("../cex_core/engine/case_compiler/consistency_contract.js");
  return consistency_contract_path(caseRoot, aid);
}

export async function loadAndVerify(opts: {
  aid: string; record: Record<string, any>; card: Record<string, any>; cardSha256: string;
  mmCase: Record<string, any>; caseRoot: string;
}): Promise<[Record<string, any> | null, string, string]> {
  // 提交期重核（照引擎 submit 的台账核对位）：盘上覆盖层 ↔ 状态里存的 accepted material
  // ↔ 冻结的契约卡 ↔ 密封的机械案，四方对合才放行。
  const { load_consistency_contract, validate_consistency_contract } =
    await import("../cex_core/engine/case_compiler/consistency_contract.js");
  const { aid, record, card, cardSha256, mmCase, caseRoot } = opts;
  const material = record.material;
  if (!material || typeof material !== "object" || !String(record.receipt_sha256 ?? "")) {
    return [null, "", "consistency_verdict_missing: the authoring state carries no accepted material"];
  }
  let overlay: Record<string, any>, overlaySha: string;
  try {
    [overlay, overlaySha] = load_consistency_contract(await overlayPath(caseRoot, aid));
  } catch (exc) {
    return [null, "", `consistency_contract_invalid: ${exc}`];
  }
  if (overlaySha !== String(record.overlay_sha256 ?? "")) {
    return [null, overlaySha, "consistency_contract_invalid: the overlay on disk hashes to "
      + `${overlaySha.slice(0, 12)}, not the ${String(record.overlay_sha256 ?? "").slice(0, 12)} `
      + "recorded when it was sealed"];
  }
  const error = validate_consistency_contract(overlay, { base_contract: card,
    base_contract_sha256: cardSha256, accepted_material: material,
    consistency_receipt_sha256: String(record.receipt_sha256), machine_case: mmCase });
  if (error) return [null, overlaySha, `consistency_contract_invalid: ${error}`];
  return [overlay, overlaySha, ""];
}

export async function intentBinding(record: Record<string, any>, opts: {
  overlay: string; projectRoot: string;
}): Promise<Record<string, any>> {
  // sealed 案写进 intent.json 的绑定字段（客户端布局的路径相对工作区根记；
  // 引擎 complete 分支按服务端扁平布局核对，客户端不接，见模块头注释）。
  return {
    consistency_binding_status: "complete",
    consistency_contract_path: path.relative(opts.projectRoot, opts.overlay).split(path.sep).join("/"),
    consistency_contract_sha256: record.overlay_sha256,
    consistency_receipt_sha256: record.receipt_sha256,
  };
}

export const LEGAL_FORM = {
  keys: ["spec_locator (string)", "case_locator (string)", "incompatibility (one sentence)",
    "premises [{origin: 'spec'|'case', locator}] (quote bytes optional)",
    "spec_clauses [{text, disposition, reason}] tiling the whole stamped spec_quote with no gaps"],
  note: "pass this object as cex_consistency_record's material; the engine re-resolves "
    + "every locator from the sealed sources and rejects drifted quotes",
};

export function writeBrief(ws: Workspace, batch: string, aid: string, outName: string,
  record: Record<string, any>, opts: {
    conclusion: any; specName: string | null; specPath: string | null; caseAtoms: any;
  }): string {
  // pending_record 案的单案 brief：卡上（可能残缺的）结论、固定 verdict 与本案可用的出处
  // 原子，供模型照着补包。
  const target = path.join(batch, "consistency_briefs", `${aid}.json`);
  const payload = {
    schema: "cex.consistency-brief", autoid: aid, out_name: outName,
    reason_code: record.code ?? "", detail: record.detail ?? "",
    fixed_verdict: record.fixed_verdict,
    verdict_note: record.fixed_verdict !== null && record.fixed_verdict !== undefined
      ? "omit verdict — the sealed conclusion fixes it"
      : "no sealed conclusion on this card: give verdict 'consistent' or 'conflict', "
        + "judged against the sealed sources",
    governing_spec: { name: opts.specName, path: opts.specPath },
    case_source_atoms: opts.caseAtoms,
    conclusion: opts.conclusion,
    legal_form: LEGAL_FORM,
  };
  writeFileSafely(ws.root, target, Buffer.from(JSON.stringify(payload, null, 1), "utf8"));
  return target;
}

export function dropBrief(batch: string, aid: string): void {
  const p = path.join(batch, "consistency_briefs", `${aid}.json`);
  if (fs.existsSync(p) && fs.statSync(p).isFile()) fs.unlinkSync(p);
}

export async function sourceAtoms(mindmapText: string, aid: string): Promise<any> {
  const { consistency_source_atoms_for_brief } =
    await import("../cex_core/engine/case_compiler/mindmap_contract_projector.js");
  return consistency_source_atoms_for_brief(mindmapText)[aid] ?? {};
}
