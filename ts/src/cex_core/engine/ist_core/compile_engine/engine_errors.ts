export const E_WORKER_TIMEOUT = "0001";
export const E_COLLECT_SETUP = "0002";
export const E_CONTRACT_STAMP = "0003";
export const E_ENVIRONMENT = "0004";
export const E_NO_LEDGER_CHANNEL = "0005";
export const E_MECHANICAL_CASE_IDENTITY = "0006";
export const E_ENGINE_INSERTED_ROW_INVALID = "0007";
export const E_COMMAND_TREE_UNAVAILABLE = "0008";
export const E_INVENTORY_RECEIPT_REDACTED = "0009";
export const E_WORKER_RESULT_ENVELOPE = "0010";
export const E_DELIVERY_BINDING_UNAVAILABLE = "0011";
export const E_FORK_CHANNEL_FAULT = "0012";
export const E_MECHANICAL_CASE_UNPRODUCIBLE = "0013";
export const E_RECOMPOSE_CHANNEL_FAULT = "0014";
export const E_ROUND_CAP_EXHAUSTED = "0015";
export const E_LLM_QUOTA_EXHAUSTED = "0016";
export const E_LLM_TRANSIENT_EXHAUSTED = "0017";
export const E_API_REQUEST_REJECTED = "0018";
export const E_API_AUTH_REJECTED = "0019";
export const E_ENTRY_INPUT_REFERENCES = "0031";

export const ENGINE_ERROR_CODES: string[] = [
  E_WORKER_TIMEOUT,
  E_COLLECT_SETUP,
  E_CONTRACT_STAMP,
  E_ENVIRONMENT,
  E_NO_LEDGER_CHANNEL,
  E_MECHANICAL_CASE_IDENTITY,
  E_ENGINE_INSERTED_ROW_INVALID,
  E_COMMAND_TREE_UNAVAILABLE,
  E_INVENTORY_RECEIPT_REDACTED,
  E_WORKER_RESULT_ENVELOPE,
  E_DELIVERY_BINDING_UNAVAILABLE,
  E_FORK_CHANNEL_FAULT,
  E_MECHANICAL_CASE_UNPRODUCIBLE,
  E_RECOMPOSE_CHANNEL_FAULT,
  E_ROUND_CAP_EXHAUSTED,
  E_LLM_QUOTA_EXHAUSTED,
  E_LLM_TRANSIENT_EXHAUSTED,
  E_API_REQUEST_REJECTED,
  E_API_AUTH_REJECTED,
  E_ENTRY_INPUT_REFERENCES,
];

export const CHECKPOINT_RESERVED_CODES: Record<string, string> = {
  manifest_identity: "0020",
  volume_population: "0021",
  artifact_handoff: "0022",
  projection_receipt: "0023",
  closing_state: "0024",
  runtime_envelope: "0025",
  dispatch_settlement: "0026",
  window_binding: "0027",
  fact_vocabulary: "0028",
  supply_identity: "0029",
  rule_supply_disagreement: "0030",
};

const _CODE_SPACE = [...ENGINE_ERROR_CODES, ...Object.values(CHECKPOINT_RESERVED_CODES)].sort();
if (JSON.stringify(_CODE_SPACE) !== JSON.stringify([...Array(_CODE_SPACE.length)].map((_, i) => String(i + 1).padStart(4, "0")))) {
  throw new Error(`engine four-digit code space must stay collision-free and contiguous: ${_CODE_SPACE}`);
}

export const CASE_SCOPED_CODES = new Set([
  E_WORKER_TIMEOUT,
  E_ENVIRONMENT,
  E_CONTRACT_STAMP,
  E_NO_LEDGER_CHANNEL,
  E_MECHANICAL_CASE_IDENTITY,
  E_INVENTORY_RECEIPT_REDACTED,
  E_WORKER_RESULT_ENVELOPE,
  E_DELIVERY_BINDING_UNAVAILABLE,
  E_FORK_CHANNEL_FAULT,
  E_MECHANICAL_CASE_UNPRODUCIBLE,
  E_ROUND_CAP_EXHAUSTED,
  E_LLM_TRANSIENT_EXHAUSTED,
  E_API_REQUEST_REJECTED,
  E_ENTRY_INPUT_REFERENCES,
]);

export const API_CAUSE_CODES: Record<string, string> = {
  LLM_QUOTA_EXHAUSTED: E_LLM_QUOTA_EXHAUSTED,
  TRANSIENT_ERROR: E_LLM_TRANSIENT_EXHAUSTED,
  API_REQUEST_REJECTED: E_API_REQUEST_REJECTED,
  API_AUTH_REJECTED: E_API_AUTH_REJECTED,
};

export const API_SIDE_CODES = new Set(Object.values(API_CAUSE_CODES));

const _UNSET = Symbol("unset");

export function condition_from_legacy_code(
  aid: string,
  code: string,
  detail: string = "",
  opts: {
    identity?: Record<string, any> | null;
    source_location?: Record<string, any> | null;
    observed?: any;
    site?: string;
    inputs?: Record<string, any> | null;
    scope?: string;
  } = {}
): Record<string, any> {
  const C = require("./engine_checkpoints");
  if (!ENGINE_ERROR_CODES.includes(String(code))) {
    throw new Error(`unknown legacy engine code: ${JSON.stringify(code)}`);
  }
  const location = { ...(opts.source_location ?? C._location()) };
  const location_site = `${location.file ?? ""}:${location.function ?? ""}`.replace(/^:+|:+$/g, "");
  return C.condition_disclosure(opts.site || location_site || "legacy_code_observation", opts.observed === _UNSET ? String(detail) : opts.observed, {
    identity: opts.identity,
    aid: String(aid ?? ""),
    legacy_code: String(code),
    inputs: opts.inputs,
    source_location: location,
    scope: opts.scope,
    detail: String(detail),
  });
}

export function is_batch_scoped(code: string, aid: string = ""): boolean {
  if (!CASE_SCOPED_CODES.has(String(code ?? ""))) return true;
  return !String(aid ?? "").trim();
}

export const ENGINE_ERROR_EVENT = "engine_error";

export const CODE_TITLE_CN: Record<string, string> = {
  [E_WORKER_TIMEOUT]: "worker 空转无产出",
  [E_COLLECT_SETUP]: "测试收集/初始化或批次人口账不可用",
  [E_CONTRACT_STAMP]: "机械脑图用例无法生成",
  [E_ENVIRONMENT]: "环境错误",
  [E_NO_LEDGER_CHANNEL]: "欠定判据无落账通道",
  [E_MECHANICAL_CASE_IDENTITY]: "机械用例身份不符",
  [E_ENGINE_INSERTED_ROW_INVALID]: "引擎插入的对照行不合法",
  [E_COMMAND_TREE_UNAVAILABLE]: "命令树投影不可用",
  [E_INVENTORY_RECEIPT_REDACTED]: "命令清单凭证被遮蔽破坏",
  [E_WORKER_RESULT_ENVELOPE]: "编写孔返回信封不合协议",
  [E_DELIVERY_BINDING_UNAVAILABLE]: "交付期权威绑定不可用",
  [E_FORK_CHANNEL_FAULT]: "编写孔进程被引擎自身通道中止",
  [E_MECHANICAL_CASE_UNPRODUCIBLE]: "机械用例产不出来且不该再问人",
  [E_RECOMPOSE_CHANNEL_FAULT]: "机器脑图产不出来（重组段引擎侧故障）",
  [E_ROUND_CAP_EXHAUSTED]: "重编轮次用尽仍未收敛",
  [E_LLM_QUOTA_EXHAUSTED]: "LLM 端点账户配额/余额不足",
  [E_LLM_TRANSIENT_EXHAUSTED]: "LLM 端点瞬态压力耗尽引擎重试",
  [E_API_REQUEST_REJECTED]: "API错误：请求被拒（400）",
  [E_API_AUTH_REJECTED]: "API错误：鉴权或权限被拒（401/403）",
  [E_ENTRY_INPUT_REFERENCES]: "编译入口引用侧车不可用",
};

export const CODE_CAUSE_CN: Record<string, string> = {
  [E_WORKER_TIMEOUT]: "旧码登记未获可采信编写产物。无产出或预算结束本身不证明模型或引擎责任。",
  [E_COLLECT_SETUP]: "旧码登记 collect/setup 失败或批次 manifest 人口账不可用；具体观察以本条 detail 为准，编号不区分这两条来源。",
  [E_CONTRACT_STAMP]: "旧码登记机械脑图用例或身份章不可用；是否缺材料、读取失败或内部故障须看本条原始记录。",
  [E_ENVIRONMENT]: "旧码登记环境相关结算；是否已有明确确认以及观察范围须回查本条原始记录。",
  [E_NO_LEDGER_CHANNEL]: "旧码曾用于一致性账初始化、冲突结算或组题通道条件；不能只凭同一码断言共同根因。",
  [E_MECHANICAL_CASE_IDENTITY]: "旧码登记机械用例读取或身份不一致；变化由谁造成、是否为软件缺陷未由编号证明。",
  [E_ENGINE_INSERTED_ROW_INVALID]: "登记契约为引擎插入控制观测的 U3 绑定。新签发必须带真实检查器可复算的证明；原始用例整体是否正确不在此证明范围。",
  [E_COMMAND_TREE_UNAVAILABLE]: "旧码登记命令树投影不可用；缺失、不可读和来源不符不能单独证明软件根因或设备不支持。",
  [E_INVENTORY_RECEIPT_REDACTED]: "旧码登记命令清单凭据的遮蔽相关条件；具体差异及处理责任须由前后原始凭据证明。",
  [E_WORKER_RESULT_ENVELOPE]: "旧码登记编写结果信封未获受理；没有输出、解析失败和传输中止须按实际原始记录区分。",
  [E_DELIVERY_BINDING_UNAVAILABLE]: "旧码登记交付权威绑定不可用；编号不证明卷未变、设备已通过或用例没有问题。",
  [E_FORK_CHANNEL_FAULT]: "旧码登记编写通道中止或未完成；裸异常名称不能证明是引擎软件故障。",
  [E_MECHANICAL_CASE_UNPRODUCIBLE]: "旧码登记编写/回修未形成可用产物的旧结算；新运行不得据此省略模型失败的独立凭据条件。",
  [E_RECOMPOSE_CHANNEL_FAULT]: "旧码登记重组阶段未获可用机械脑图；来源或责任未闭合时只披露实际停点。",
  [E_ROUND_CAP_EXHAUSTED]: "旧码登记轮次预算用尽。预算结束不单独证明能力不足或引擎缺陷。",
  [E_LLM_QUOTA_EXHAUSTED]: "旧码表示上游配额类分类；实际返回、适用账户及限制条件以原始 API 记录为准。",
  [E_LLM_TRANSIENT_EXHAUSTED]: "旧码表示上游瞬态重试结束分类；具体调用结果与重试记录分别保留，不由编号推断其他组件健康。",
  [E_API_REQUEST_REJECTED]: "旧码登记 API 请求被拒的分类；原始状态码和响应内容保留，拒绝本身不证明请求构造或引擎没有问题。",
  [E_API_AUTH_REJECTED]: "旧码登记 API 身份/权限类拒绝；401/403 本身不区分密钥、权限、区域、配额等具体限制。",
  [E_ENTRY_INPUT_REFERENCES]: "旧码登记编译入口引用侧车不可用；收据与侧车必须同生，缺失不证明用例稿不合格。",
};

Object.assign(CODE_TITLE_CN, {
  [E_WORKER_TIMEOUT]: "编写未获可采信产物",
  [E_WORKER_RESULT_ENVELOPE]: "编写结果信封未获受理",
  [E_FORK_CHANNEL_FAULT]: "编写通道未完成（历史分类）",
  [E_RECOMPOSE_CHANNEL_FAULT]: "重组未获可用机械脑图",
  [E_LLM_QUOTA_EXHAUSTED]: "API配额类响应记录",
  [E_LLM_TRANSIENT_EXHAUSTED]: "API瞬态类响应记录",
  [E_API_REQUEST_REJECTED]: "API请求拒绝记录",
  [E_API_AUTH_REJECTED]: "API身份/权限类响应记录",
});

export class CommandTreeUnavailable extends Error {
  detail: string;
  device_build: string;
  constructor(detail: string, opts: { device_build?: string } = {}) {
    super(String(detail || "command-tree projection is unavailable"));
    this.name = "CommandTreeUnavailable";
    this.detail = String(detail || "command-tree projection is unavailable");
    this.device_build = String(opts.device_build || "");
  }
}

export class EntryInputReferencesUnavailable extends Error {
  detail: string;
  engine_error_code: string;
  constructor(detail: string = "") {
    super(String(detail || "compile entry input references unavailable"));
    this.name = "EntryInputReferencesUnavailable";
    this.detail = String(detail || "compile entry input references unavailable");
    this.engine_error_code = E_ENTRY_INPUT_REFERENCES;
  }
}

export const ENTRY_INPUT_FORK_CAUSES = new Set([EntryInputReferencesUnavailable.name]);

export function is_engine_error_code(code: string): boolean {
  return ENGINE_ERROR_CODES.includes(String(code ?? ""));
}

export function engine_error_fact(aid: string, code: string, detail: string = ""): Record<string, any> {
  if (!is_engine_error_code(code)) {
    throw new Error(`unknown engine error code: ${JSON.stringify(code)}`);
  }
  const fact: Record<string, any> = { ev: ENGINE_ERROR_EVENT, aid: String(aid ?? ""), code: String(code) };
  if (detail) {
    fact.detail = String(detail).slice(0, 400);
  }
  return fact;
}

export function engine_errors(facts: Record<string, any>[]): Record<string, any>[] {
  return facts.filter((f) => f.ev === ENGINE_ERROR_EVENT);
}

export function active_engine_errors(facts: Record<string, any>[]): Record<string, any>[] {
  const _F = require("./facts");
  return engine_errors(_F.this_run_slice(facts));
}

export function case_scoped_engine_errors(facts: Record<string, any>[]): Record<string, any>[] {
  return active_engine_errors(facts).filter((fact) => (!("owner" in fact) || fact.owner === "engine") && error_halts_batch(fact) === false);
}

export const UNVERIFIABLE_ERROR_EVENT = "engine_error_unverifiable_disclosure";

function _interpret_error(fact: Record<string, any>): [boolean | null, Record<string, any> | null] {
  const C = require("./engine_checkpoints");
  const { write_schema } = require("../../common/schema_identity");
  const { scrub_value } = require("../security_scrub");
  const { _fact_sha256 } = require("./terminal_credentials");
  try {
    if (["schema", "error_id", "owner"].some((key) => key in fact)) {
      C.validate_error(fact);
      return [fact.mode === "halt" || (fact.mode === "pause" && fact.scope === "batch"), null];
    }
    if (!is_engine_error_code(fact.code)) {
      throw new Error("legacy error code is not registered");
    }
    return [is_batch_scoped(String(fact.code ?? ""), String(fact.aid ?? "")), null];
  } catch (exc: any) {
    const source_sha = _fact_sha256(fact);
    const failure = scrub_value({ exception: exc instanceof Error ? exc.name : "Error", reason: String(exc) }, { scrub_paths: false });
    const diagnostic_id = "error-read:" + C.digest({ source: source_sha, failure });
    const disclosure = scrub_value(
      {
        schema: write_schema("ist.engine-error-unverifiable-disclosure"),
        ev: UNVERIFIABLE_ERROR_EVENT,
        aid: String(fact.aid ?? ""),
        diagnostic_id,
        original_error_id: String(fact.error_id ?? ""),
        original_code: String(fact.code ?? ""),
        source_record_sha256: source_sha,
        validation_exception: failure.exception,
        validation_error: failure.reason,
        decision_status: "unverified",
      },
      { scrub_paths: false }
    );
    return [null, disclosure];
  }
}

export function error_halts_batch(fact: Record<string, any>): boolean | null {
  return _interpret_error(fact)[0];
}

export function unverifiable_error_disclosures(facts: Record<string, any>[]): Record<string, any>[] {
  return active_engine_errors(facts)
    .map((fact) => _interpret_error(fact)[1])
    .filter((disclosure): disclosure is Record<string, any> => disclosure !== null);
}

export function batch_aborted(facts: Record<string, any>[]): boolean {
  return active_engine_errors(facts).some((fact) => error_halts_batch(fact) === true);
}
