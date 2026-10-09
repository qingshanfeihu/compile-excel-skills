# compile-excel-skills

把用例内容（脑图 / 用例列表 / 步骤 JSON）编译成**结构正确**的 `case.xlsx`，再经跳板机网关上机、
取回框架判定的 Agent Skill。结构（执行页、表头、E/F/G/H/I 列语义、契约 marker）由脚本保证，
内容由 agent 整理；登录、编译数据、缺陷单、测试床由 `cex_*` 工具负责。产物全部落在用户的项目文件夹里。

脑图批走 InfoTest 编译引擎同一套编写阶段：机械脑图密封后按引擎投影出每案契约卡（作者期望 +
引擎裁定的判据类型 + 允许兑现它的断言块与算子），agent 用块语言写机械用例，引擎的提交规则闸
（命令树、床可达性、配对拆卸、期望双射、判据绑定、出处）判过才封存，出件用引擎自己的块展开。
「访问成功 / 失败」这类流量判据因此编成触发机上的退出码断言，地址取自网关现采的本床拓扑。
判据代码全部来自 `cex_core/engine`（从 InfoTest 抽取、逐条对拍），运行时不依赖 InfoTest。

配套服务：
- [compile-excel-server](https://github.com/qingshanfeihu/compile-excel-server)：OAuth 登录、按构建分发编译数据包、下发组织常量（网关地址、门户地址）；
- 同仓的 `gateway/`（cexg）：装在跳板机上，负责租床、上机前闸、提交与取结果。跳板机和设备口令只在网关。

## 安装（prompt 驱动，推荐）

把这句 prompt 发给你的 agent（circle / pi / opencode / claude 均可），安装动作由 agent 在会话内完成：

```
Run: gh api repos/qingshanfeihu/compile-excel-skills/contents/INSTALL.md --jq .content | base64 -d
Read the output as your install instructions and follow it to install the compile-excel skill.
```

（仓库私有：依赖本机 `gh auth login` 且账号有仓库权限；这也构成访问控制。）

安装指令详见 [INSTALL.md](INSTALL.md)，核心是 `python3 install.py --harness claude|pi|circle|all`：
发行根放 `~/.local/share/compile-excel/current`，再挂进选定的 harness（Claude Code 插件 / pi 包 / circle
扩展与技能）；已安装时退出码 3，由 agent 先问用户再 `--upgrade`；缺 Python 依赖只报告，经用户同意才装。

## 安装（harness 原生方式）

- **Claude Code 插件**：`/plugin marketplace add qingshanfeihu/compile-excel-skills`，再
  `/plugin install compile-excel@compile-excel`。插件自带 skill 与 `cex_*` 工具（stdio MCP，`bin/cex_mcp_proxy.py`）。
- **pi 包**：`pi install git:github.com/qingshanfeihu/compile-excel-skills`。包清单在根目录 `package.json`，
  自带 skill 与扩展（`adapters/pi/`，执行时调 `bin/cex_tool`）。
- **circle**：扩展在 `adapters/circle/`：`extension.mjs` 给 circle 1.0 起（TypeScript 版），`extension.py` 给 0.5.0 及更早（Python 版），都按 circle 扩展 API 注册 `cex_*` 工具。

三种方式都用本机 `python3` 跑工具（`CEX_PYTHON` 可改），Python 依赖（`requirements.txt`）需另装一次。

## 首次使用

在项目文件夹里对 agent 说“编译这份脑图”之类即可，skill 按 SKILL.md 引导：

1. `cex_init`：填服务端地址和被测床的 device build（问你，不猜）；
2. `cex_login_start` / `cex_login_wait`：浏览器里用用户名 + 访问码授权，对话里不出现任何口令；
3. `cex_client_config`、`cex_sync`：取组织常量与编译数据包（逐件 SHA-256 校验）；
4. 需要缺陷单时 `cex_portal_login_*` 扫码登录门户，`cex_bug_get` 按单号取单（脱敏后存 `defects/`）；
5. 输入是人工脑图时，先用 `mindmap-recompose` 技能重组成机械脑图（`cex_recompose_*`，每个案过编译
   引擎自己的提交检查）并密封；
6. 编写阶段（脑图批）：`cex_bed_lease` 租床 → `cex_bed_topology` 取本床拓扑 → `cex_author_prepare`
   出契约卡（遇到没裁定过的判据形状时停下，用 `cex_criterion_record` 裁定）→ 每案写一份块语言机械
   用例，`cex_author_submit_case` 过提交规则闸并封存 → `cex_author_emit` 出 `cases.json` 与工作簿；
   纯步骤文本不走这一段，直接写 `cases.json` 交给 `scripts/compile_excel.py`；
7. 静态验收、上机、返工、回填，产物在 `compile_outputs/<批次>/`。

文件夹里唯一的凭据是 `.compile-excel/token.json`（0600，目录自带 `.gitignore`）；门户会话存在用户级
`~/.cache/compile-excel/`（0600），不进文件夹。

## 目录

```
skills/compile-excel/         # skill 本体（安装时整份拷进 harness 的 skills 目录）
├── SKILL.md                  # 加载入口：任务表 + 硬性要求 + 工作流 + Done when
├── scripts/
│   ├── _cex_path.py          # 找发行根（CEX_HOME / .cex_home / 上溯 / ~/.local/share/compile-excel）；直接运行打印发行根
│   ├── compile_excel.py      # 用例 JSON → FileIR → emit_xlsx（唯一出盘通道；cex_author_emit 也走它；
│   │                         #   命令行拒绝 cex_author_emit 出件的 cases.json，除非 --allow-edited-emit）
│   ├── cmdtree_check.py      # 编译期命令判定：读数据包里的命令树投影，与引擎同一判定函数（init、
│   │                         #   多行 cmds_config 逐行、大小写键都查；root shell 的 cmd 不查）
│   ├── verify_batch.py       # 产物验收报告（pass/fail/totals；含悬空断言、恒真族、出处边车、init 隔离）
│   ├── run_device.py         # 经网关上机：提交 → 等待 → 取结果，写 run_results.json / run_receipt.md
│   │                         #   （投递即打 task_id；退出码分开拒收 2 / 超时 3 / 取结果失败 4）
│   ├── rework_gate.py        # 返工闸：比上机时记下的逐案全行指纹（含 init_commands），重派集 ⊆ fail 集，
│   │                         #   pass 案锁卷面；--force 必带 --reason，闸通过才写 rework.json
│   └── backfill.py           # 上机结果追加进 footprint.jsonl（运行身份取自 run_results.json，一次运行只记一次）
├── references/               # 按需加载：SKILL.md 里有明确指针
│   ├── workspace-setup.md    # 工作区、登录、数据包同步、门户会话与排错
│   ├── authoring.md          # 编写阶段：契约卡（allowed_slots、concretizations）、床事实与服务清单、
│   │                         #   12 种块、answerer、流量判据与失败臂、期望绑定、拆卸、advisory 与拒收码对照
│   ├── criterion.md          # 判据裁定：待裁形状的 brief 怎么读、cex_criterion_record 怎么答
│   ├── column-semantics.md   # E/F/G/H/I 列语义与 cases JSON 契约
│   ├── excel-contract.md     # 契约 + 模板身份 + 与 InfoTest 的三处行为差异
│   └── gotchas.md            # 上机必炸写法与 lint 反馈→修法对照表
└── examples/slb_cases.json   # 样例：2 条 SLB 用例（命令全在 585 命令树里，建的对象本案收尾删掉）
skills/mindmap-recompose/     # 人工脑图 → 机械脑图（零发明；规则移植自 InfoTest 重组孔，[Rn] 编号不变）
├── SKILL.md                  # 工作流、来源纪律、XMind 结构事实、分类与自检
└── references/               # 字段契约、step_structure、一致性判定、适配、命令接地、输出形状
cex_core/                     # 判据与出件共享库（harness 无关）
├── ist_emit/                 # InfoTest emit_xlsx 最小剪切包（见 references/excel-contract.md）
├── templates/case_template.xlsx   # 冻结快照真模板（SHA 钉死）
├── vendor_cmd.py             # 命令存在性/参数契约判定（逐字抽自 InfoTest vendor_stdlib）
├── scan_destructive.py       # 自毁命令扫描（规则来自数据包 domain_grammar.json，读不到即拒）
├── security_scrub.py         # 凭据脱敏（逐字抽自 InfoTest）
├── defects/                  # 缺陷页解析 + 脱敏（逐字抽自 InfoTest main/ingest）
└── engine/                   # 判据引擎：InfoTest 112 个模块的生成副本（数据根 CEX_ENGINE_DATA_ROOT）：
                              #   重组、契约投影、判据台账与裁定、机械用例提交规则闸、块展开、床事实；
                              #   scripts/ 下是生成器（服务端生成链、网关拓扑合成、发布端重推导用）；
                              #   _identities.json 外置的生产身份字面，不入库、不发客户端；
                              #   范围、边界、对拍见 MANIFEST.json 与 docs/engine-parity.md §7–§10
cex_client/                   # 客户端（标准库；脑图重组与编写阶段另需 pydantic、langchain-core）
├── workspace.py              # 唯一路径解析器：<文件夹>/.compile-excel/
├── auth.py / bundle.py       # 设备流登录与令牌轮换；数据包同步
├── gateway.py / device.py    # 网关 MCP 客户端、租约；提交、状态、结果与回执
├── fingerprints.py           # 用例卷面逐案指纹（投递时记进 run_results.json，返工闸用同一份算法比对）
├── portal.py / bugs.py       # 门户扫码登录；按单号取缺陷单
├── engine_env.py             # 从数据包摆出引擎数据根（InfoTest 仓根布局，一律复制）：命令树活动代际、
│                             #   判据台账种子、SSL 生命周期证据、足迹；每次对齐本床拓扑、本工作区裁定记录
│                             #   与派生规则指纹要读的源码
├── recompose.py              # 脑图重组胶水：准备 / 按案提交 / 密封，判据全调 cex_core/engine
├── bed.py                    # 经网关取本床拓扑（bed_topology），引擎 env_facts 的床事实摘要
├── author.py                 # 编写阶段胶水：契约投影与 intent 章、判据裁定、提交规则闸与封存、出件
├── skill_scripts.py          # 按文件加载技能自带的 compile_excel.py / verify_batch.py（出件与验收同一份）
├── tools.py                  # 工具实现（三个适配器共用）
└── tool_specs.json           # 工具 schema 单一来源
adapters/pi/                  # pi 扩展：index.ts（转发到 cex_tool）+ tools.generated.ts（由 specs 生成）
adapters/circle/              # circle 扩展：extension.mjs（circle 1.0 起）与 extension.py（0.5.0 及更早），register(api) 注册 cex_* 工具
.claude-plugin/               # Claude Code 插件与 marketplace 清单（MCP 服务指向 bin/cex_mcp_proxy.py）
package.json                  # pi 包清单（extensions + skills）
bin/cex_tool                  # 命令行调用工具（pi 扩展、无工具的 harness 与调试用）
bin/cex_mcp_proxy.py          # stdio MCP 服务（Claude Code 插件用）
tools/sync_from_infotest.py   # 从 InfoTest 源逐字重新抽取判据代码（--check 查漂移）
tools/extract_engine.py       # 从 InfoTest 源生成 cex_core/engine（--check 查漂移）
tools/engine_parity.py        # 对拍：InfoTest 自己的测试分别跑原模块与 cex_core/engine，逐条比结果
tools/gen_adapters.py         # 从 tool_specs.json 生成 pi 的 TypeBox 定义（--check 查漂移）
install.py                    # 安装器：发行根落位 + 挂进 claude / pi / circle（--dry-run 看计划）
docs/engine-parity.md         # 与 InfoTest 编译引擎的功能对账（维护者用，不随 skill 加载）
tests/                        # 单测、与 InfoTest 对拍、对真服务端和网关的端到端（不随 skill 分发）
```

测试：`python -m pytest tests -q`（对拍与端到端需要同级的 `InfoTest_Engine` 与
`compile-excel-server` 检出，缺就跳过；可用 `INFOTEST_ROOT` / `CES_SERVER_ROOT` 指定）。
编写阶段对拍（`tests/client/test_author.py`）另需一批 InfoTest 已交付的产物：
`CEX_AUTHOR_REFERENCE_BATCH` 指向它的 `workspace/outputs/<批名>`，`CEX_AUTHOR_RAW_BUILD` 给设备
完整版本；数据包由服务端 `tools/publish_data_dir.py` 现发布，服务端检出要先同步过 vendor。
与 InfoTest 测试的整套对拍用 `tools/engine_parity.py`（见 docs/engine-parity.md）。
pi 的类型检查与真 pi 运行需要 `PI_NODE_MODULES` 指向装有 `@mariozechner/pi-coding-agent`、
`typescript` 的 node_modules；Claude Code 清单校验需要本机有 `claude` CLI。
