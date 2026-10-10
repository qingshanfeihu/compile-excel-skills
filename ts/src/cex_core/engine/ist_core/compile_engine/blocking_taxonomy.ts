import { product_expected_source_is_valid } from "../../case_compiler/provenance_ir";
import * as _L from "../display_lexicon";
import { SCENARIO2_REASON_CODE, active_execution_terminal, scenario2_abandon_active } from "./views";
import { _decision_resolves_question, _fact_sha256, _object_sha256, _structured_claims } from "./terminal_credentials";

export const SCHEMA_CARD = "ist.compile.blocking_card";
export const B_SPEC_CASE = "spec_case_conflict";
export const B_XML_CONFLICT = "xml_conflict_pending";
export const B_MANUAL_ERROR = "manual_error";
export const B_DEVICE_MANUAL = "device_and_manual_error";
export const B_DEVICE_DEFECT = "device_defect";
export const B_ENV_UNMET = "environment_unmet";
export const B_EXECUTION_INFRA = "execution_infrastructure_blocked";
export const B_EXCEL_FN = "excel_function_gap";
export const B_AUTHORITY_CONFLICT = "authority_conflict";
export const B_AUTHORING_UNATTRIBUTED = "authoring_stop_unattributed";
export const B_CONTRA_UNATTRIBUTED = "verdict_contradiction_unresolved";
export const B_AUTHORITY_UNVERIFIED = "authority_chain_unverified";
export const B_UNRECOGNIZED_ROUTING = "unrecognized_routing_value";
export const B_ARTIFACT_UNVERIFIABLE = "case_artifact_identity_unverifiable";
export const BLOCKING_CLASSES = [
  B_SPEC_CASE,
  B_XML_CONFLICT,
  B_MANUAL_ERROR,
  B_DEVICE_MANUAL,
  B_DEVICE_DEFECT,
  B_ENV_UNMET,
  B_EXECUTION_INFRA,
  B_EXCEL_FN,
  B_AUTHORITY_CONFLICT,
  B_AUTHORING_UNATTRIBUTED,
  B_CONTRA_UNATTRIBUTED,
  B_AUTHORITY_UNVERIFIED,
  B_UNRECOGNIZED_ROUTING,
  B_ARTIFACT_UNVERIFIABLE,
] as const;
export const B_UNCLASSIFIED = "unclassified_blocking";
export const NOT_OBJECTIVE = "not_objective_blocking";
export const A_SPEC_CASE_CONFLICT = "abandoned_spec_case_conflict";
export const A_SPEC_PRESENT_CASE_INCOMPLETE = "abandoned_spec_present_case_incomplete";
export const A_INCOMPLETE_CASE = "abandoned_incomplete_case";
export const A_ROUND_CAP = "abandoned_round_cap";
export const A_NO_CLI_EQUIVALENT = "abandoned_no_cli_equivalent";
export const A_ENV_PREREQ_GAP = "abandoned_environment_prerequisite_gap";
export const A_AUTHOR_DEFINITION_GAP = "abandoned_author_definition_gap";
export const A_BATCH_USER_ABANDON = "abandoned_batch_user_abandon";
export const ABANDON_CLASSES = [
  A_SPEC_CASE_CONFLICT,
  A_SPEC_PRESENT_CASE_INCOMPLETE,
  A_INCOMPLETE_CASE,
  A_ROUND_CAP,
  A_NO_CLI_EQUIVALENT,
  A_ENV_PREREQ_GAP,
  A_AUTHOR_DEFINITION_GAP,
  A_BATCH_USER_ABANDON,
] as const;
export const ABANDON_CN: Record<string, string> = {
  [A_SPEC_CASE_CONFLICT]: "放弃：规格书与人工脑图不一致",
  [A_SPEC_PRESENT_CASE_INCOMPLETE]: "放弃：规格书有表态、人工脑图缺项",
  [A_INCOMPLETE_CASE]: "放弃：人工脑图不完整",
  [A_ROUND_CAP]: "放弃：编译轮次已用尽",
  [A_NO_CLI_EQUIVALENT]: "放弃：自动化平台没有等价的 CLI 观测方式",
  [A_ENV_PREREQ_GAP]: "放弃：测试环境不具备编写条件",
  [A_AUTHOR_DEFINITION_GAP]: "放弃：通过标准欠定，需作者补充定义",
  [A_BATCH_USER_ABANDON]: "放弃：用户选择整批放弃",
};
export const ABANDON_REASON_ZH: Record<string, string> = {
  [A_SPEC_CASE_CONFLICT]: "规格书和人工脑图对同一条判据各说各的，两侧都完整但对不上。这次不编机械用例、不入库。",
  [A_SPEC_PRESENT_CASE_INCOMPLETE]: "规格书对这条人工脑图有明确说法，但人工脑图缺描述、步骤或预期，还编不出来。缺的是人工脑图本身，编译期补不上。这次不编机械用例、不入库。",
  [A_INCOMPLETE_CASE]: "人工脑图和规格书都没给出能编的判据，缺口是真的。缺的是输入本身。这次不编机械用例、不入库。",
  [A_ROUND_CAP]: "来源冲突挡住过，改完再编，轮次用尽。这次不编机械用例、不入库。",
  [A_NO_CLI_EQUIVALENT]: "这条人工脑图要用后台或非 CLI 的观察方式，自动化这边找不到同等的 CLI 写法，编不成机械用例。这次不编机械用例、不入库。",
  [A_ENV_PREREQ_GAP]: "你的人工脑图没问题。是测试环境缺编写前提：作者指定的部署值不在这台设备的任何可达子网，或这步被共享设备运行纪律禁了。环境不变，再跑还是这样。这次不编机械用例、不入库。",
  [A_AUTHOR_DEFINITION_GAP]: "通过标准欠定：读得懂要验什么，但从人工脑图、规格书和其它带身份来源推不出能判定的预期。缺的定义只有作者或规格书能补，引擎不猜，也不拿设备观测当预期。输入不变，再跑还是这样。这次不编机械用例、不入库。",
  [A_BATCH_USER_ABANDON]: "情景③④的来源冲突已经在同一面板问过，你选了放弃。整批这次都不编机械用例、不入库，输入不变就不再问。",
};
export const ABANDON_USER_ACTION_ZH: Record<string, string> = {
  [A_SPEC_CASE_CONFLICT]: "这次不编机械用例。修正人工脑图或规格书使两侧一致后，请用新的批名重新编译。",
  [A_SPEC_PRESENT_CASE_INCOMPLETE]: "这次不编机械用例。补齐人工脑图缺少的描述、步骤或预期后，请用新的批名重新编译。",
  [A_INCOMPLETE_CASE]: "这次不编机械用例。在人工脑图或规格书里补上可编译的判据后，请用新的批名重新编译。",
  [A_NO_CLI_EQUIVALENT]: "这次不编机械用例：这条人工脑图要求的后台或非 CLI 观测方式在自动化平台上没有等价的 CLI 实现。把人工脑图改写成可用 CLI 观测的形式后，请用新的批名重新编译。",
  [A_ENV_PREREQ_GAP]: "这次不编机械用例：测试环境不具备编写条件。请先处理本案记录的环境限制，或使用具备条件的测试设备，再用新的批名重新编译。",
  [A_AUTHOR_DEFINITION_GAP]: "这次不编机械用例：通过标准欠定。人工脑图与规格书都没有把预期定义到可编译的程度。请按报告里编写侧逐字列出的缺口，在人工脑图或管辖规格书里补充对应定义（如部署映射、监听地址/端口、查询前提，或把「正常响应」这类判词写成可判定的输出标准），再用新的批名重新编译。",
  [A_BATCH_USER_ABANDON]: "整批已按你的选择放弃，本轮绑定输入不变时不会重问。若要重新编译，请先修改人工脑图、能力 XML 或管辖规格书，再用新的批名发起。",
};
export const AUTHOR_GAP_VARIANT = "gap";
export const AUTHOR_CONFLICT_VARIANT = "conflict";

export function is_abandon_class(token: string): boolean {
  return ABANDON_CLASSES.includes(String(token ?? "") as any);
}

export const LEGACY_CLASS_MAP: Record<string, string> = {
  topology_change: B_ENV_UNMET,
  device_investment: B_ENV_UNMET,
  product_defect_blocking: B_DEVICE_DEFECT,
  manual_issue: B_MANUAL_ERROR,
  mindmap_issue: B_SPEC_CASE,
  excel_function_gap: B_EXCEL_FN,
};

export function canonical_class(token: string): string {
  const t = String(token ?? "");
  if (BLOCKING_CLASSES.includes(t as any) || ABANDON_CLASSES.includes(t as any) || [B_UNCLASSIFIED, NOT_OBJECTIVE].includes(t)) {
    return t;
  }
  return LEGACY_CLASS_MAP[t] ?? B_UNCLASSIFIED;
}

export const BLOCKING_CN: Record<string, string> = {
  [B_CONTRA_UNATTRIBUTED]: "判决矛盾未消解（责任未核）",
  [B_AUTHORITY_UNVERIFIED]: "期望值来源链未记清（待裁决）",
  [B_UNRECOGNIZED_ROUTING]: "路由值未登记（待裁决）",
  [B_ARTIFACT_UNVERIFIABLE]: "个案产物身份不可核（待裁决）",
  [B_AUTHORITY_CONFLICT]: "来源声明冲突",
  [B_SPEC_CASE]: "脑图问题(与规格书冲突或判据待厘清)",
  [B_XML_CONFLICT]: "能力注册表与来源声明冲突(待仲裁)",
  [B_MANUAL_ERROR]: "人工脑图与手册声明冲突(待仲裁)",
  [B_DEVICE_MANUAL]: "手册声明、人工脑图与设备行为多源冲突",
  [B_DEVICE_DEFECT]: "声明与设备行为冲突(待仲裁)",
  [B_ENV_UNMET]: "环境不满足(需开通道，非人工脑图问题)",
  [B_EXECUTION_INFRA]: "执行基础设施阻塞(下发/结果回收未闭合)",
  [B_EXCEL_FN]: "引擎能力不足(自动化函数表达不了)",
  [B_AUTHORING_UNATTRIBUTED]: "编写未以引擎可核的结果结束(责任未核)",
  [B_UNCLASSIFIED]: "引擎缺陷(未落入冲突处置闭集)",
  ...ABANDON_CN,
};

export const OVERRIDE_TOKEN_PREFIX = "override:";
export const OVERRIDE_DECISION_SCHEMA = "ist.delta.blocking-override";

function _override_class_from_token(token: string): string {
  const text = String(token ?? "");
  if (!text.startsWith(OVERRIDE_TOKEN_PREFIX)) return "";
  const raw = text.slice(OVERRIDE_TOKEN_PREFIX.length);
  if (BLOCKING_CLASSES.includes(raw as any) || ABANDON_CLASSES.includes(raw as any)) return raw;
  return LEGACY_CLASS_MAP[raw] ?? "";
}

function _override_token_sha256(blocking_class: string): string {
  return _object_sha256({ schema: OVERRIDE_DECISION_SCHEMA, override_class: blocking_class, token: `${OVERRIDE_TOKEN_PREFIX}${blocking_class}` });
}

export function project_override_decision(token: string): Record<string, string> {
  const blocking_class = _override_class_from_token(token);
  if (!blocking_class) return {};
  return { override_schema: OVERRIDE_DECISION_SCHEMA, override_class: blocking_class, override_token_sha256: _override_token_sha256(blocking_class) };
}

function _override_class_from_decision(fact: Record<string, any>): [string, string] {
  const token = String(fact.token ?? "");
  const legacy_class = _override_class_from_token(token);
  if (legacy_class) return [legacy_class, "token"];
  const blocking_class = String(fact.override_class ?? "");
  if (token !== "****" || fact.override_schema !== OVERRIDE_DECISION_SCHEMA || !BLOCKING_CLASSES.includes(blocking_class as any) || !ABANDON_CLASSES.includes(blocking_class as any) || fact.override_token_sha256 !== _override_token_sha256(blocking_class)) {
    return ["", ""];
  }
  return [blocking_class, "override_class"];
}

export const FACTOR_ZH: Record<string, string> = {
  [B_AUTHORITY_UNVERIFIED]: "交付卷身份一致、设备已通过；该案部分断言的期望值来源链未记清。不可证不等于引擎可证，本案转入待裁决，不随卷交付。",
  [B_UNRECOGNIZED_ROUTING]: "引擎遇到登记表里没有的路由值，不能折叠成默认出口，本案转入待裁决。",
  [B_ARTIFACT_UNVERIFIABLE]: "交卷审计核不到个案产物身份，本案转入待裁决，不随卷交付。",
  [B_AUTHORITY_CONFLICT]: "当前产物与交付身份已核验，来源声明仍有未解决的冲突；具体依据见权威对齐记录。",
  [B_SPEC_CASE]: "人工脑图与管辖规格书冲突,或验证判据在两侧都缺席,需要作者厘清",
  [B_XML_CONFLICT]: "规格书或人工脑图声明与版本化能力注册表不一致,当前不选胜",
  [B_MANUAL_ERROR]: "手册声明与规格书或人工脑图声明不一致,当前不选胜",
  [B_DEVICE_MANUAL]: "手册声明、人工脑图与设备行为形成多方冲突,需要绑定身份后仲裁",
  [B_DEVICE_DEFECT]: "文档/人工脑图声明与同一 artifact 的设备行为不一致,仅形成待仲裁候选",
  [B_ENV_UNMET]: "你的人工脑图没问题。是当前自动化环境缺它需要的通道/拓扑/网段/统计面，要先把环境开出来才能跑，改人工脑图没有用",
  [B_EXECUTION_INFRA]: "本轮下发或结果回收通道未闭合；卷面没有因此被判为 IST-Core 产物缺陷。只阻塞受影响用例，批内兄弟用例继续",
  [B_EXCEL_FN]: "你的人工脑图没问题。是引擎现有的自动化函数表达不了这个验证方式，属引擎能力缺口，已进工程处置候选单",
  [B_AUTHORING_UNATTRIBUTED]: "你的人工脑图没问题。这一案的编写没有以引擎可核的结果结束，账上的记录不足以判定是模型、引擎还是环境的问题，所以不给任何一方定责。原始记录与出处链已保留，同参续跑可以重入这一案",
  [B_CONTRA_UNATTRIBUTED]: _L.CONTRADICTION_PAUSE_UNCLOSED_CN,
  [B_UNCLASSIFIED]: "这一条卡住不是你的人工脑图的问题。它没有落进任何一类来源冲突(规格书×人工脑图、人工脑图×命令树、文档×设备行为、上机结果×预期),说明卡点在引擎自己。已进工程处置候选单,你的人工脑图不受影响",
  [A_SPEC_CASE_CONFLICT]: ABANDON_REASON_ZH[A_SPEC_CASE_CONFLICT],
  [A_SPEC_PRESENT_CASE_INCOMPLETE]: ABANDON_REASON_ZH[A_SPEC_PRESENT_CASE_INCOMPLETE],
  [A_INCOMPLETE_CASE]: ABANDON_REASON_ZH[A_INCOMPLETE_CASE],
  [A_ROUND_CAP]: ABANDON_REASON_ZH[A_ROUND_CAP],
  [A_NO_CLI_EQUIVALENT]: ABANDON_REASON_ZH[A_NO_CLI_EQUIVALENT],
  [A_ENV_PREREQ_GAP]: ABANDON_REASON_ZH[A_ENV_PREREQ_GAP],
  [A_AUTHOR_DEFINITION_GAP]: ABANDON_REASON_ZH[A_AUTHOR_DEFINITION_GAP],
  [A_BATCH_USER_ABANDON]: ABANDON_REASON_ZH[A_BATCH_USER_ABANDON],
};

export const OPTIONS_ZH: Record<string, string[]> = {
  [B_CONTRA_UNATTRIBUTED]: [],
  [B_AUTHORITY_UNVERIFIED]: ["核对期望值来源链后按身份重入"],
  [B_UNRECOGNIZED_ROUTING]: ["把未登记的路由值交给引擎维护者处理后按身份重入"],
  [B_ARTIFACT_UNVERIFIABLE]: ["核对个案产物身份后按身份重入"],
  [B_AUTHORITY_CONFLICT]: ["修正冲突来源后重新发起编写"],
  [B_SPEC_CASE]: ["改描述", "改过程", "改预期", "挂起"],
  [B_XML_CONFLICT]: ["以设备命令树为准,换等价命令重编", "保留人工脑图命令,冲突案不编机械用例", "放弃本次生成"],
  [B_EXECUTION_INFRA]: ["恢复下发/结果回收基础设施后重新发起本案"],
  [B_AUTHORING_UNATTRIBUTED]: _L.UNATTRIBUTED_AUTHORING_STOP_USER_OPTIONS_CN,
  [A_SPEC_CASE_CONFLICT]: ["放弃本次生成"],
  [A_SPEC_PRESENT_CASE_INCOMPLETE]: ["放弃本次生成"],
  [A_INCOMPLETE_CASE]: ["放弃本次生成"],
  [A_ROUND_CAP]: ["放弃本次生成"],
  [A_NO_CLI_EQUIVALENT]: ["放弃本次生成"],
  [A_ENV_PREREQ_GAP]: ["放弃本次生成"],
  [A_AUTHOR_DEFINITION_GAP]: ["放弃本次生成"],
  [A_BATCH_USER_ABANDON]: ["放弃整批"],
};

const _VARIANT_TEXTS: Record<string, Record<string, string>> = {
  [AUTHOR_GAP_VARIANT]: { declaration_label: "作者需补充定义的具体缺口（编写侧原文）", reason_lead: "通过标准欠定：" },
  [AUTHOR_CONFLICT_VARIANT]: {
    class_cn: "放弃：人工脑图两处说法互斥，需作者定这条验哪一个",
    reason: "人工脑图自己两处说法对不上：标题或所在分组说这条要验的行为，与某个步骤实际配置的行为不是同一个，而预期只在其中一种下成立。定义不缺，是打架——没有哪一条预期能同时兑现，上机也只能否掉其中一边，引擎不替你选。输入不变，再跑还是这样。这次不编机械用例、不入库。",
    user_action: "这次不编机械用例：人工脑图两处说法互斥。请按报告里编写侧逐字列出的分歧，定这条用例要考察哪一边，把另一处改成与它一致（改标题/分组，或改那个步骤），再用新的批名重新编译。",
    declaration_label: "作者需决定的具体分歧（编写侧原文）",
    reason_lead: "人工脑图两处说法互斥：",
  },
};
_VARIANT_TEXTS[AUTHOR_CONFLICT_VARIANT].factor = _VARIANT_TEXTS[AUTHOR_CONFLICT_VARIANT].reason;

const _CLASS_TEXTS: Record<string, [Record<string, string>, string]> = {
  class_cn: [BLOCKING_CN, "待归类(信号不足)"],
  reason: [ABANDON_REASON_ZH, ""],
  user_action: [ABANDON_USER_ACTION_ZH, ""],
  factor: [FACTOR_ZH, FACTOR_ZH[B_UNCLASSIFIED]],
};

export function variant_text(field: string, opts: { cls?: string; variant?: string } = {}): string {
  const cls = opts.cls ?? A_AUTHOR_DEFINITION_GAP;
  const variant = opts.variant ?? "";
  if (String(cls) === A_AUTHOR_DEFINITION_GAP) {
    const key = variant in _VARIANT_TEXTS ? variant : AUTHOR_GAP_VARIANT;
    const text = _VARIANT_TEXTS[key][field];
    if (text !== undefined) return text;
  }
  const [table, fallback] = _CLASS_TEXTS[field];
  return table[String(cls)] ?? fallback;
}

export const MINDMAP_CLAIM_KINDS = new Set([
  "absolute_position",
  "rotation_order",
  "new_member_last",
  "new_member_participates",
  "weight_ratio",
  "distribution",
  "relation_same",
  "relation_diff",
  "cross_client_landing",
  "missing_teardown",
  "sequence_periodicity",
]);
export const DEVICE_CLAIM_KINDS = new Set(["forbidden_mechanism"]);
export const MANUAL_CLAIM_KINDS = new Set(["command_existence"]);
const _ND_QID_RE = /^nd:\d+:\d+:(?<kinds>[a-z_]+(?:\+[a-z_]+)*)(?::delta:(?<delta>[^:]+))?$/;
const _SELF_CLASSIFYING_TERMINALS = new Set(["delivered", "device_defect", "authoring_failure"]);
const _NOT_OBJECTIVE_DISPOSITIONS = new Set(["env_blocked", "engineering_fault", "rerun_isolated", "fixed", "reflow", "ist_core_defect"]);

function _basis_entry(fact: Record<string, any>, field: string, value: string): Record<string, any> {
  return { ev: String(fact.ev ?? ""), sha256: _fact_sha256(fact), field, value };
}

function _xml_precedent_basis(claim: Record<string, any>): Record<string, any> | null {
  const xml_basis = claim.xml_basis;
  const precedents = claim.precedent_device_passes;
  if (typeof xml_basis !== "object" || xml_basis === null || !Array.isArray(precedents)) return null;
  const current_build = String(xml_basis.build ?? "").trim();
  const verified = precedents
    .filter((item: any) => typeof item === "object" && item !== null && item.verification === "device_delivery_pass" && String(item.build ?? "").trim() && String(item.oid ?? "").trim())
    .map((item: any) => ({
      build: String(item.build ?? "").trim(),
      oid: String(item.oid ?? "").trim(),
      source_filename: String(item.source_filename ?? "").trim(),
      registry_sha256: String(item.registry_sha256 ?? "").trim(),
    }));
  if (verified.length === 0) return null;
  const cross_build = verified.filter((item) => item.build !== current_build);
  const details = {
    command: String(claim.command ?? ""),
    current_build: current_build || "?",
    xml_source_filename: String(xml_basis.source_filename ?? ""),
    xml_source_sha256: String(xml_basis.source_sha256 ?? ""),
    requested_node_path: xml_basis.requested_node_path,
    nearest_node_paths: (xml_basis.nearest_node_paths ?? []).filter((value: any) => String(value)),
    precedents: cross_build.length ? cross_build : verified,
  };
  const field = cross_build.length ? "version_difference" : "xml_projection_anomaly";
  return {
    ev: "needs_decision_ledger",
    sha256: _fact_sha256({ claim }),
    field,
    value: `precedent_builds=${details.precedents.map((item) => item.build).join(",")};current_build=${details.current_build};command=${details.command}`,
    details,
  };
}

function _ledger_mechanical_flags(raw: any): Record<string, Record<string, boolean>> {
  const flags: Record<string, Record<string, boolean>> = {};
  for (const item of Array.isArray(raw) ? raw : []) {
    if (typeof item !== "object" || item === null) continue;
    const kind = String(item.claim_kind ?? "");
    if (!kind) continue;
    if (item.spec_agrees) flags[kind] = { ...flags[kind], spec_agrees: true };
    if (item.xml_absent_manual_only) flags[kind] = { ...flags[kind], xml_absent_manual_only: true };
  }
  return flags;
}

function _claim_kinds_from_facts(aid: string, mine: Record<string, any>[]): [string, Record<string, any>][] {
  const answered = new Set(mine.filter((f) => _decision_resolves_question(f) && String(f.question_id ?? "")).map((f) => String(f.question_id ?? "")));
  const out: [string, Record<string, any>][] = [];
  for (const fact of mine) {
    if (fact.ev !== "needs_decision") continue;
    const qid = String(fact.question_id ?? "");
    if (answered.has(qid)) continue;
    const match = _ND_QID_RE.exec(qid);
    if (match) {
      for (const kind of match.groups!.kinds.split("+")) {
        out.push([kind, fact]);
      }
    }
  }
  return out;
}

export function classify_blocking(
  aid: string,
  mine: Record<string, any>[],
  ledger_claims: any = null,
  raw_ledger_claims: any = null,
  terminal_outcome: string = "",
  opts: { facts?: Record<string, any>[] | null } = {}
): Record<string, any> {
  const basis: Record<string, any>[] = [];
  const matched: string[] = [];

  function _hit(cls: string, fact: Record<string, any>, field: string, value: string): void {
    basis.push(_basis_entry(fact, field, value));
    if (cls && !matched.includes(cls)) matched.push(cls);
  }

  const { effective_authority_facts, is_authority_block_terminal, is_authority_unverified_block } = require("./authority_delivery_policy");
  const execution_terminal = active_execution_terminal(mine, { facts: opts.facts });
  if (is_authority_block_terminal(execution_terminal)) {
    const TC = require("./terminal_credentials");
    const effective = effective_authority_facts(opts.facts ?? mine, aid);
    const position = effective.findIndex((row: any) => row === execution_terminal);
    const evidence = position >= 0 ? effective.slice(0, position + 1) : [];
    const refs = TC.build_terminal_credential({ aid, outcome: "blocked", preferred_layer: "delivery", facts: evidence });
    const [valid, errors] = TC.validate_terminal_credential({ aid, outcome: "blocked", layer: "delivery", credential_refs: refs }, { facts: evidence });
    if (valid) {
      const kind = is_authority_unverified_block(execution_terminal) ? B_AUTHORITY_UNVERIFIED : B_AUTHORITY_CONFLICT;
      _hit(kind, execution_terminal, "reason_code", String(execution_terminal.reason_code ?? ""));
      return { class: kind, basis, co_signals: [] };
    }
    return { class: NOT_OBJECTIVE, basis: [{ field: "credential_validation", value: errors }], co_signals: [] };
  }

  const { is_unattributed_authoring_stop } = require("./authoring_stops");
  if (is_unattributed_authoring_stop(execution_terminal)) {
    const TC = require("./terminal_credentials");
    const { UNATTRIBUTED_LAYER } = require("./terminal_outcomes");
    const rows = opts.facts ?? mine;
    const position = rows.findIndex((row) => row === execution_terminal);
    const evidence = position >= 0 ? rows.slice(0, position + 1) : [];
    const refs = TC.build_terminal_credential({ aid, outcome: "blocked", preferred_layer: UNATTRIBUTED_LAYER, facts: evidence });
    const [valid, errors] = TC.validate_terminal_credential({ aid, outcome: "blocked", layer: UNATTRIBUTED_LAYER, credential_refs: refs }, { facts: evidence });
    if (valid) {
      const { is_contradiction_stop } = require("./contradiction_stop");
      const stop_cause = String(execution_terminal.stop_cause ?? "");
      let kind: string;
      if (stop_cause === B_UNRECOGNIZED_ROUTING) kind = B_UNRECOGNIZED_ROUTING;
      else if (stop_cause === B_ARTIFACT_UNVERIFIABLE) kind = B_ARTIFACT_UNVERIFIABLE;
      else if (is_contradiction_stop(execution_terminal)) kind = B_CONTRA_UNATTRIBUTED;
      else kind = B_AUTHORING_UNATTRIBUTED;
      _hit(kind, execution_terminal, "stop_cause", stop_cause);
      return { class: kind, basis, co_signals: [] };
    }
    return { class: NOT_OBJECTIVE, basis: [{ field: "credential_validation", value: errors }], co_signals: [] };
  }

  for (let i = mine.length - 1; i >= 0; i--) {
    const fact = mine[i];
    if (fact.ev !== "decision") continue;
    const [cls, field] = _override_class_from_decision(fact);
    if (cls) {
      _hit(cls, fact, field, String(fact[field] ?? ""));
      return { class: cls, basis, co_signals: [] };
    }
  }

  const atts = mine.filter((f) => f.ev === "attribution");
  for (const att of atts) {
    if (String(att.disposition ?? "") === "defect_candidate" && String(att.evidence ?? "").trim() !== "" && String(att.evidence ?? "").trim() !== "user" && typeof att.defect_candidate === "object" && att.defect_candidate !== null && product_expected_source_is_valid(att.defect_candidate?.expected_with_source)) {
      _hit(B_DEVICE_DEFECT, att, "disposition", "defect_candidate");
    }
  }

  const unsupported = mine.filter((f) => f.ev === "unsupported_feature");
  for (const fact of unsupported) {
    _hit(B_ENV_UNMET, fact, "ev", "unsupported_feature");
  }

  for (const fact of mine) {
    if (fact.ev === "coexist_conflict") {
      _hit(B_ENV_UNMET, fact, "channel", String(fact.channel ?? "cross_case_coexistence"));
    }
  }

  const active_scenario2 = scenario2_abandon_active(mine);
  for (const fact of mine) {
    if (fact.ev === "policy_abandon") {
      if (fact.reason_code === SCENARIO2_REASON_CODE && !active_scenario2) continue;
      const cls = canonical_class(String(fact.blocking_class ?? ""));
      if (ABANDON_CLASSES.includes(cls as any)) {
        _hit(cls, fact, "ev", "policy_abandon");
        return { class: cls, basis, co_signals: [] };
      }
    }
    if (fact.ev === "source_conflict_blocked") {
      _hit(B_XML_CONFLICT, fact, "ev", "source_conflict_blocked");
      return { class: B_XML_CONFLICT, basis, co_signals: [] };
    }
    if (fact.ev === "authority_preflight_blocked") {
      _hit(B_SPEC_CASE, fact, "ev", "authority_preflight_blocked");
      return { class: B_SPEC_CASE, basis, co_signals: [] };
    }
    if (fact.ev === "recompose_case_quarantined") {
      _hit(B_UNCLASSIFIED, fact, "ev", "recompose_case_quarantined");
      return { class: B_UNCLASSIFIED, basis, co_signals: [] };
    }
    if (fact.ev === "xml_absence_terminal") {
      _hit(B_XML_CONFLICT, fact, "ev", "xml_absence_terminal");
      return { class: B_XML_CONFLICT, basis, co_signals: [] };
    }
  }

  const claim_hits: [string, Record<string, any>, Record<string, any>][] = [];
  for (const claim of _structured_claims(ledger_claims)) {
    claim_hits.push([String(claim.claim_kind ?? ""), { ev: "needs_decision_ledger", claim_kind: claim.claim_kind }, claim]);
  }
  claim_hits.push(...(_claim_kinds_from_facts(aid, mine) as unknown as [string, Record<string, any>, Record<string, any>][]));

  const raw_terminal_claims = (Array.isArray(raw_ledger_claims) ? raw_ledger_claims : []).filter(
    (claim: any) => typeof claim === "object" && claim !== null && claim.claim_kind === "command_existence" && claim.terminal === true && claim.requires_user_decision === false && typeof claim.xml_basis === "object" && claim.xml_basis !== null
  );
  const existing_commands = new Set(claim_hits.filter(([, , claim]) => typeof claim === "object" && claim !== null).map(([, , claim]) => String(claim.command ?? "")));
  for (const claim of raw_terminal_claims) {
    if (existing_commands.has(String(claim.command ?? ""))) continue;
    claim_hits.push(["command_existence", { ev: "needs_decision_ledger", claim_kind: "command_existence" }, claim]);
  }

  const mech_flags = _ledger_mechanical_flags(raw_ledger_claims ?? ledger_claims);
  for (const [kind, fact, claim] of claim_hits) {
    if (DEVICE_CLAIM_KINDS.has(kind)) {
      _hit(B_ENV_UNMET, fact, "claim_kind", kind);
    } else if (MANUAL_CLAIM_KINDS.has(kind)) {
      if (claim.xml_absent_manual_only || mech_flags[kind]?.xml_absent_manual_only) {
        _hit(B_MANUAL_ERROR, fact, "claim_kind", `${kind}+xml_absent_manual_only`);
        const version_basis = _xml_precedent_basis(claim);
        if (version_basis !== null) basis.push(version_basis);
        if (claim.spec_agrees || mech_flags[kind]?.spec_agrees) {
          basis.push(_basis_entry(fact, "claim_kind", `${kind}+spec_also_disagrees_with_xml`));
        }
      } else if (claim.spec_agrees || mech_flags[kind]?.spec_agrees) {
        _hit(B_XML_CONFLICT, fact, "claim_kind", `${kind}+spec_agrees`);
      } else {
        _hit(B_MANUAL_ERROR, fact, "claim_kind", kind);
      }
    } else if (MINDMAP_CLAIM_KINDS.has(kind)) {
      _hit(B_SPEC_CASE, fact, "claim_kind", kind);
    }
  }

  for (const fact of mine) {
    if (fact.ev === "contradiction" && String(fact.shape ?? "") === "manual_vs_device") {
      _hit(B_MANUAL_ERROR, fact, "shape", "manual_vs_device");
    }
  }

  if (matched.length) {
    if (matched.includes(B_MANUAL_ERROR) && matched.includes(B_DEVICE_DEFECT)) {
      const rest = matched.filter((c) => ![B_MANUAL_ERROR, B_DEVICE_DEFECT].includes(c));
      return { class: B_DEVICE_MANUAL, basis, co_signals: [B_MANUAL_ERROR, B_DEVICE_DEFECT, ...rest] };
    }
    return { class: matched[0], basis, co_signals: matched.slice(1) };
  }

  const dispositions = new Set(atts.map((f) => String(f.disposition ?? "")));
  const engine_internal = [...dispositions].some((d) => _NOT_OBJECTIVE_DISPOSITIONS.has(d)) || mine.some((f) => f.ev === "delivery_blocked");
  if (engine_internal && unsupported.length === 0) {
    return { class: NOT_OBJECTIVE, basis, co_signals: [] };
  }
  if (_SELF_CLASSIFYING_TERMINALS.has(terminal_outcome)) {
    return { class: NOT_OBJECTIVE, basis, co_signals: [] };
  }

  const { escalation_budget_kind } = require("./_shared");
  for (let i = mine.length - 1; i >= 0; i--) {
    const fact = mine[i];
    if (fact.ev !== "escalated") continue;
    const _kind = escalation_budget_kind(fact);
    if (_kind) {
      _hit(B_UNCLASSIFIED, fact, "engine_budget_exhausted", _kind);
      return { class: B_UNCLASSIFIED, basis, co_signals: [] };
    }
    break;
  }

  const { is_runtime_infrastructure_terminal_fact } = require("./execution_failure");
  const execution_terminal2 = active_execution_terminal(mine, { facts: opts.facts });
  if (is_runtime_infrastructure_terminal_fact(execution_terminal2)) {
    const reason_code = String(execution_terminal2.reason_code ?? "");
    _hit(B_EXECUTION_INFRA, execution_terminal2, "reason_code", reason_code);
    basis[basis.length - 1].details = { layer: "execution", error_text: String(execution_terminal2.error_text ?? "") };
    return { class: B_EXECUTION_INFRA, basis, co_signals: [] };
  }

  return { class: B_UNCLASSIFIED, basis, co_signals: [] };
}
