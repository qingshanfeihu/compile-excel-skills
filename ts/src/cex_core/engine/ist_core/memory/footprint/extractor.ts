import { RawFact, makeRawFact, anchor_paths } from "./schema";

const logger = {
  warning: (...args: any[]) => console.warn(...args),
};

const _THREAD_ID_RE = /thread_id:\s*(\S+)/;

const _SYSTEM_PROMPT = `你是 IST-Core 的产品知识提取助手。阅读给定文本（产品 CLI 文档 / agent 工作记忆），
提取**有原文证据支撑的产品事实**，调用 \`emit_facts\` 工具按其参数 schema 提交。
输出结构由工具 schema 强约束——你只做语义判断：抽什么、归到哪个 feature_path、引哪句证据。

## 各 fact_kind 何时用、填哪些字段

- **cli_command**（一条 CLI 命令的语法）：填 \`cli_syntax\` = **完整调用签名**（命令主体 + 全部参数，
  按正确顺序，用记法表示参数：必填 \`<param>\`、可选 \`[param]\`、枚举 \`{a|b}\`）。只写命令本身，
  禁止描述句、引号、中文标点、"用于"/"语法为"。
  - 签名要**完整规范**。文档对同一命令常分散呈现：标题行可能只列主体加个别参数，真正的参数集要
    结合紧随的参数表/说明才完整；规范定义与使用示例也常并存。综合还原出完整规范签名，不要照抄某一行
    残片，也不要把示例里选定的具体取值当成命令的一部分。
  - 参数值不是命令路径：枚举值 / 模式名 / 具体地址等是参数取值，只出现在记法里，绝不作独立命令 token。
  - 命令带命名参数且原文有参数表/说明 → 填 \`parameters\`（每参数一对象，\`name\` 必填作去重键；其余字段
    按原文如实给，如 \`type\`/\`required\`/\`default\`/\`value_range\`/\`desc\`，不限于此）。纯枚举开关直接写进
    \`cli_syntax\` 即可、\`parameters\` 留空。原文无参数信息就留空，不要编造或猜测取值范围。
  - **同一命令的 配置 / no / show / clear 各自是独立 cli_command**：分别给完整签名，它们 feature_path
    相同、代码会自动归到同一节点。
- **decision_rule**：\`condition\`（触发条件）+ \`decision\`（结论/默认值/限制）**两者都必填**。原文没有明确
  "条件 → 结论"两段时，**改用 behavior**。
  - **多分支条件行为必须逐条抽全**：同一命令/特性在**不同条件下有不同结论**时（按请求类型 / 查询类型 /
    模式 / 参数取值 / 命中与否 / 启用与否等分支），**每个分支各抽一条独立 decision_rule**，各带自己的
    condition 与 evidence_quote。**绝不要只抽其中一条、只抽概括句、或把多个并列分支合并成一句**——
    漏抽分支会让下游只看到片面行为、据此写错断言（例：手册"收到 CNAME 类请求→返回 CNAME 记录；
    收到 A/AAAA 类请求→用 CNAME 再解析返回 IP"是**两条** decision_rule，不是一条概括的"会重新查询"）。
- **behavior**：填 \`content\`（一句话功能行为）。**必须是某条 CLI 命令的行为说明**。架构概念 / 设计术语 /
  项目代号不是命令也不是命令行为，**不要提取**——知识树只收 CLI 命令及其相关事实，不收名词解释。
- **known_issue**：填 \`issue_id\`（BUG 编号）+ \`issue_title\`（**照抄 BUG title 原文，一字不改、不概括、不留空**）。
  可选 \`affected_versions\`。

## evidence（cli_command / decision_rule / behavior 必填；known_issue 不需要）

- \`evidence_file\`：这条事实在哪个文档能查到。真实路径，从所读文件的 path 获取，不要凭空构造。
- \`evidence_quote\`：**evidence_file 里的原文片段**，未经改写 / 合并 / 概括。merger 会用 grep 验证，
  grep 不到整条 fact 丢弃。取**最能直接证明该事实的那段原文**：cli_command 引命令定义/语法呈现那行
  （哪怕残缺）；decision_rule/behavior 引陈述该规则/行为的那句。不要用章节标题、
  泛泛导语、无关旁支句充数。
  - \`cli_syntax\` 是你综合还原的完整签名，\`evidence_quote\` 是文档原始呈现，两者不必逐字相同。
- known_issue 的 BUG 数据来自 API 而非磁盘文件，无需 evidence。
- condition / decision / content 可以是你的概括，但 \`evidence_quote\` 必须引用原文。
  cli/rule/behavior 找不到字面证据时，**宁可不提取**，不要用自己的话改写凑结构。

## cli_commands（这条事实涉及哪几条命令）—— 决定它挂在树的哪一层

知识树是分层的，层级由**一条事实横跨几条命令**决定，不是由你指定：

- 事实只讲**一条**命令的语法/行为/限制 → \`cli_commands\` 就写那一条，它挂在这条命令的节点上。
- 事实讲的是**一组命令共同**的原理、约束、工作机制、状态机、切换/同步规则 → 把它实际涉及的
  那几条命令**都写上**。引擎会算出它们的公共父节点，把这条事实挂到模块层。
  例：一条讲 HA 配置同步机制的规则，同时约束 \`ha group\`、\`ha decision rule\`、\`ha synconfig bootup\`
  → 三条都写，事实落到 \`ha\` 模块节点，而不是硬塞进其中某一条命令。
- 事实跨越**不同模块** → 同样把涉及的命令都写上，引擎会让它在每个模块下都能被找到。

两个方向都别做过头：不要为了"挂高一点"硬凑本不相关的命令；也不要把只讲一条命令的事实
拆成多条命令写。**写你在原文里真正读到的那几条。**

## feature_path（命令主体 token 序列，单锚）

- 剥 \`no\` / \`show\` / \`clear\` 操作前缀；**只放命令主体 token，不放参数值**
  （如 \`show <a> <b> <c>\` → \`["a","b","c"]\`；枚举/取值参数不进 path）。
- cli_command 的 path 代码会从 cli_syntax 兜底派生，但你仍应给对。
- \`cli_commands\` 只有一条时，\`feature_path\` 就是那一条；多条时代码按公共前缀自己算，
  你给不给都行。
- known_issue 无明确命令时，从 BUG title/描述里找**真正的功能模块或命令**作锚点。注意 title 开头的
  方括号未必是模块名——可能是 OS/硬件环境标签、客户名等，这些**不是 feature_path**；要从问题描述本身
  找功能锚点（真实命令或功能模块名）。
- 找不到锚点就丢弃这条 fact，不要凭空造路径。

## feature_path 归一化（避免同一特性分裂成多个节点）

- **以真实 CLI 命令路径为锚**：某事实属于某条命令，就用那条命令的 token 序列，不要另造同义分组
  （不要造没有对应真实命令的路径）。
- known_issue 优先挂到命令节点；完全无法对应命令时才退化为模块名（长度=1）。
- **复用 \`<existing_facts>\` 里已存在的 feature_id**：上下文清单里已有语义相同的特性节点就直接用它，
  优先收敛到已有节点而非新增近义节点。
- 同义标准：描述的是**同一条命令 / 同一配置项 / 同一特性**，即使措辞不同也算同一特性。

## fact_key（决定 dedup，snake_case 描述该 fact 主题）

- cli_command 用命令核心 token；decision_rule 用规则主题；behavior 用行为主题；known_issue 直接用 issue_id。
- **复用已有 fact_key**：若 \`<existing_facts>\` 里某 fact 与你要提取的**语义等同**，必须复用同一 fact_key
  （哪怕措辞不同）；同一规则的不同复述映射到同一 key，否则产生重复。

## 绝对不要提取

- agent 工作计划（"接下来"/"需要找到"/"继续读取"）、评审建议（"应补充"/"建议修改"）、文件导航日志
  （"找到 N 个文件"）、等价映射（"等价于某友商型号"）、无原文证据的推测。

无可提取事实时，仍调用 emit_facts，传入空 facts 数组。`;

function _nstr(desc: string): Record<string, any> {
  return { type: ["string", "null"], description: desc };
}

const _PARAM_ITEM: Record<string, any> = {
  type: "object",
  additionalProperties: false,
  properties: {
    name: { type: "string", description: "参数名。" },
    required: { type: ["boolean", "null"], description: "是否必选。" },
    type: _nstr("参数类型（string/integer/IP 地址…）。"),
    default: _nstr("默认值。"),
    value_range: _nstr("取值范围/约束。"),
    desc: _nstr("参数说明（原文）。"),
  },
  required: ["name", "required", "type", "default", "value_range", "desc"],
};

const _FACT_ITEM: Record<string, any> = {
  type: "object",
  additionalProperties: false,
  properties: {
    fact_kind: {
      type: "string",
      enum: ["cli_command", "decision_rule", "behavior", "known_issue"],
      description: "事实类型，决定哪些字段填值（其余填 null）。",
    },
    feature_path: {
      type: "array",
      items: { type: "string" },
      description:
        "命令主体 token 序列（剥 no/show/clear 前缀，不含参数值）。cli_commands 只有一条时可留空由它派生。",
    },
    cli_commands: {
      type: ["array", "null"],
      items: { type: "string" },
      description:
        '这条事实**实际涉及的命令**，每项一条完整命令主体（如 "ha group"）。只讲一条命令就写一条；讲的是一组命令共同的原理/行为/约束就把那几条都写上——引擎据此把事实挂到它们的公共父节点（模块）上。不确定时留 null。',
    },
    fact_key: {
      type: "string",
      description: "同一 feature_path 下该 fact 的唯一短标识，snake_case；语义等同则复用已有 key。",
    },
    cli_syntax: _nstr("fact_kind=cli_command 时填：完整命令调用签名（含全部参数记法），否则 null。"),
    parameters: {
      type: ["array", "null"],
      items: _PARAM_ITEM,
      description: "cli_command 的命名参数表（纯枚举开关填 []）；非 cli_command 填 null。",
    },
    condition: _nstr("fact_kind=decision_rule 时填：触发条件，否则 null。"),
    decision: _nstr("fact_kind=decision_rule 时填：结论/默认值/限制，否则 null。"),
    content: _nstr("fact_kind=behavior 时填：一句话功能行为，否则 null。"),
    issue_id: _nstr("fact_kind=known_issue 时填：BUG 编号，否则 null。"),
    issue_title: _nstr("fact_kind=known_issue 时填：照抄 BUG title 原文一字不改，否则 null。"),
    affected_versions: {
      type: ["array", "null"],
      items: { type: "string" },
      description: "known_issue 可选：受影响版本号列表，否则 null。",
    },
    evidence_file: _nstr("cli/rule/behavior 必填：证据所在文档路径。"),
    evidence_quote: _nstr("cli/rule/behavior 必填：evidence_file 中的原文片段，未经改写。"),
  },
  required: [
    "fact_kind",
    "feature_path",
    "cli_commands",
    "fact_key",
    "cli_syntax",
    "parameters",
    "condition",
    "decision",
    "content",
    "issue_id",
    "issue_title",
    "affected_versions",
    "evidence_file",
    "evidence_quote",
  ],
};

export const EXTRACTION_TOOL: Record<string, any> = {
  type: "function",
  function: {
    name: "emit_facts",
    strict: true,
    description: "提交从给定文本中提取的、有原文证据支撑的结构化产品事实列表。无可提取时传空数组。",
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        facts: {
          type: "array",
          description: "提取到的产品事实数组；无可提取事实时为空数组 []。",
          items: _FACT_ITEM,
        },
      },
      required: ["facts"],
    },
  },
};

function _parse_thread_id(content: string): string {
  const m = _THREAD_ID_RE.exec(content);
  return m ? m[1] : "";
}

const _OP_PREFIXES = ["no", "show", "clear"];
const _NOTATION_PARAM_RE = /^[<\[{].*[>\]}]$/;
const _NOTATION_GROUP_RE = /[<\[{][^>\]}]*[>\]}]/g;
const _MD_ESCAPE_RE = /\\([_*~])/g;

function _clean_token(tok: string): string {
  return tok.replace(_MD_ESCAPE_RE, "$1").replace(/^[_*]+|[_*]+$/g, "");
}

function _feature_path_from_syntax(cli_syntax: string): string[] {
  if (!cli_syntax) {
    return [];
  }
  const stripped = cli_syntax.replace(_NOTATION_GROUP_RE, " ");
  let toks = stripped.split(/\s+/).filter((t) => t.length > 0);
  while (toks.length > 0 && _OP_PREFIXES.includes(toks[0].toLowerCase())) {
    toks = toks.slice(1);
  }
  const out: string[] = [];
  for (const raw of toks) {
    const tok = _clean_token(raw).trim();
    if (!tok) {
      continue;
    }
    if (_NOTATION_PARAM_RE.test(tok) || tok.includes("|") || !/[a-zA-Z0-9]/.test(tok)) {
      continue;
    }
    out.push(tok.toLowerCase());
  }
  return out;
}

function _coerce_str_list(v: any): string[] {
  if (Array.isArray(v)) {
    return v.filter((x) => x).map((x) => String(x).trim());
  }
  if (typeof v === "string" && v.trim()) {
    return [v.trim()];
  }
  return [];
}

function _coerce_parameters(v: any): Record<string, any>[] {
  if (!Array.isArray(v)) {
    return [];
  }
  const out: Record<string, any>[] = [];
  for (const item of v) {
    if (item === null || typeof item !== "object" || Array.isArray(item)) {
      continue;
    }
    const name = String(item.name || "").trim();
    if (!name) {
      continue;
    }
    const entry: Record<string, any> = { name };
    for (const [k, val] of Object.entries(item)) {
      if (k === "name") {
        continue;
      }
      if (typeof val === "boolean" || typeof val === "number") {
        entry[k] = val;
      } else if (typeof val === "string") {
        const sval = val.trim();
        if (sval) {
          entry[k] = sval;
        }
      } else if (Array.isArray(val)) {
        const scalars = val
          .filter((x) => ["string", "number", "boolean"].includes(typeof x) && String(x).trim())
          .map((x) => String(x).trim());
        if (scalars.length > 0) {
          entry[k] = scalars;
        }
      }
    }
    out.push(entry);
  }
  return out;
}

const _BARE_INNER_QUOTE_RE = /(?<=[^\s:, {}\[\]"\\])"(?=[^\s:, {}\[\]"])/g;

function _loads_facts_str(s: string): any[] {
  try {
    return JSON.parse(s);
  } catch {}
  try {
    return JSON.parse(s.replace(_BARE_INNER_QUOTE_RE, '\\"'));
  } catch {}
  try {
    const json_repair = require("json_repair");
    const r = json_repair.loads(s);
    if (Array.isArray(r) && r.length > 0) {
      return r;
    }
  } catch {}
  logger.warning(`footprint LLM facts 字符串修复后仍无法解析，丢弃: ${s.slice(0, 200)}`);
  return [];
}

function _parse_llm_response(raw: any, thread_id: string): RawFact[] {
  if (typeof raw === "string") {
    try {
      raw = JSON.parse(raw);
    } catch {
      logger.warning(`footprint LLM 返回非 JSON: ${raw.slice(0, 200)}`);
      return [];
    }
  }
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return [];
  }
  let facts_raw = raw.facts ?? [];
  if (typeof facts_raw === "string") {
    facts_raw = _loads_facts_str(facts_raw);
  }
  if (!Array.isArray(facts_raw)) {
    return [];
  }
  const valid_kinds = new Set(["cli_command", "decision_rule", "behavior", "known_issue"]);
  const results: RawFact[] = [];
  for (const item of facts_raw) {
    if (item === null || typeof item !== "object" || Array.isArray(item)) {
      continue;
    }
    const _s = (key: string): string => String(item[key] || "").trim();
    const kind = _s("fact_kind");
    if (!valid_kinds.has(kind)) {
      continue;
    }
    const cli_syntax = _s("cli_syntax");
    if (kind === "cli_command" && !cli_syntax) {
      continue;
    }
    if (kind === "decision_rule") {
      if (!item.condition || !item.decision) {
        continue;
      }
    }
    if (kind === "behavior" && !item.content) {
      continue;
    }
    if (kind === "known_issue" && !item.issue_id) {
      continue;
    }
    let path: string[];
    if (kind === "cli_command") {
      path = _feature_path_from_syntax(cli_syntax);
    } else {
      const raw_path = _coerce_str_list(item.feature_path)
        .filter((p) => p)
        .map((p) => p.toLowerCase());
      let j = 0;
      while (j < raw_path.length && _OP_PREFIXES.includes(raw_path[j])) {
        j += 1;
      }
      path = j > 0 && j < raw_path.length ? raw_path.slice(j) : raw_path;
    }
    let cli_commands = _coerce_str_list(item.cli_commands)
      .map((c) => _feature_path_from_syntax(c))
      .filter((toks) => toks.length > 0);
    if (kind === "cli_command" && path.length > 0) {
      cli_commands = [path];
    }
    if (path.length === 0 && cli_commands.length > 0) {
      const resolved = anchor_paths(cli_commands);
      path = resolved.length > 0 ? resolved[0] : [];
    }
    if (path.length === 0) {
      continue;
    }
    const fact_key = _s("fact_key");
    if (!fact_key) {
      continue;
    }
    results.push(
      makeRawFact({
        fact_kind: kind as RawFact["fact_kind"],
        feature_path: path,
        cli_commands,
        fact_key,
        cli_syntax,
        parameters: _coerce_parameters(item.parameters),
        condition: _s("condition"),
        decision: _s("decision"),
        content: _s("content"),
        issue_id: _s("issue_id"),
        issue_title: _s("issue_title"),
        affected_versions: _coerce_str_list(item.affected_versions),
        evidence_file: _s("evidence_file"),
        evidence_quote: _s("evidence_quote").slice(0, 300),
        valid_for: _coerce_str_list(item.valid_for),
        superseded_by: _s("superseded_by"),
        source_thread: thread_id,
      })
    );
  }
  return results;
}

function _format_existing_facts(existing_facts: Record<string, any> | null): string {
  if (!existing_facts) {
    return "";
  }
  const lines = [
    "<existing_facts>",
    "以下是已经存在的 footprint 节点和它们的 fact_keys（含已记录的命令参数、已知缺陷）。",
    "提取时：语义等同的事实必须复用同一 fact_key；BUG 优先挂到这里已有的命令节点；",
    "命令参数若已列出，不要重复输出。",
    "",
  ];
  for (const feature_id of Object.keys(existing_facts).sort()) {
    const kinds = existing_facts[feature_id];
    if (!Object.values(kinds).some((v: any) => v)) {
      continue;
    }
    lines.push(`## ${feature_id}`);
    for (const kind of ["cli_command", "decision_rule", "behavior", "known_issue"]) {
      const entries = kinds[kind] || [];
      if (entries.length === 0) {
        continue;
      }
      lines.push(`  ${kind}:`);
      for (const [fact_key, sample] of entries) {
        lines.push(`    - ${fact_key}: ${String(sample).slice(0, 120)}`);
      }
    }
    lines.push("");
  }
  lines.push("</existing_facts>");
  lines.push("");
  return lines.join("\n");
}

export function extract_facts(
  content: string,
  opts: {
    llm_chat?: ((system: string, user: string, tool: Record<string, any>) => any) | null;
    existing_facts?: Record<string, any> | null;
    raise_llm_errors?: boolean;
  } = {}
): RawFact[] {
  const llm_chat = opts.llm_chat ?? null;
  const existing_facts = opts.existing_facts ?? null;
  const raise_llm_errors = opts.raise_llm_errors ?? false;
  if (llm_chat === null) {
    return [];
  }
  const thread_id = _parse_thread_id(content);
  const user_prompt = _format_existing_facts(existing_facts) + content;
  let result: any;
  try {
    result = llm_chat(_SYSTEM_PROMPT, user_prompt, EXTRACTION_TOOL);
  } catch (exc) {
    if (raise_llm_errors) {
      throw exc;
    }
    logger.warning(`footprint LLM 调用失败: ${exc}`);
    return [];
  }
  return _parse_llm_response(result, thread_id);
}
