# compile-excel-skills

把用例内容（脑图 / 用例列表 / 步骤 JSON）编译成**结构正确**的 `case.xlsx`，再经跳板机网关上机、
取回框架判定的 Agent Skill。结构（执行页、表头、E/F/G/H/I 列语义、契约 marker）由脚本保证，
内容由 agent 整理；登录、编译数据、缺陷单、测试床由 `cex_*` 工具负责。产物全部落在用户的项目文件夹里。

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
- **circle**：扩展在 `adapters/circle/extension.py`（按 circle 扩展 API 注册 `cex_*` 工具）。

三种方式都用本机 `python3` 跑工具（`CEX_PYTHON` 可改），Python 依赖（`requirements.txt`）需另装一次。

## 首次使用

在项目文件夹里对 agent 说“编译这份脑图”之类即可，skill 按 SKILL.md 引导：

1. `cex_init`：填服务端地址和被测床的 device build（问你，不猜）；
2. `cex_login_start` / `cex_login_wait`：浏览器里用用户名 + 访问码授权，对话里不出现任何口令；
3. `cex_client_config`、`cex_sync`：取组织常量与编译数据包（逐件 SHA-256 校验）；
4. 需要缺陷单时 `cex_portal_login_*` 扫码登录门户，`cex_bug_get` 按单号取单（脱敏后存 `defects/`）；
5. 编译、静态验收、租床上机、返工、回填，产物在 `compile_outputs/<批次>/`。

文件夹里唯一的凭据是 `.compile-excel/token.json`（0600，目录自带 `.gitignore`）；门户会话存在用户级
`~/.cache/compile-excel/`（0600），不进文件夹。

## 目录

```
skills/compile-excel/         # skill 本体（安装时整份拷进 harness 的 skills 目录）
├── SKILL.md                  # 加载入口：任务表 + 硬性要求 + 工作流 + Done when
├── scripts/
│   ├── _cex_path.py          # 找发行根（CEX_HOME / .cex_home / 上溯 / ~/.local/share/compile-excel）；直接运行打印发行根
│   ├── compile_excel.py      # 用例 JSON → FileIR → emit_xlsx（唯一出盘通道，薄 CLI）
│   ├── cmdtree_check.py      # 编译期命令判定：读数据包里的命令树投影，与引擎同一判定函数
│   ├── verify_batch.py       # 产物验收报告（pass/fail/totals）
│   ├── run_device.py         # 经网关上机：提交 → 等待 → 取结果，写 run_results.json / run_receipt.md
│   ├── rework_gate.py        # 返工闸：重派集 ⊆ fail 集，pass 案锁卷面
│   └── backfill.py           # 上机结果追加进 footprint.jsonl
├── references/               # 按需加载：SKILL.md 里有明确指针
│   ├── workspace-setup.md    # 工作区、登录、数据包同步、门户会话与排错
│   ├── column-semantics.md   # E/F/G/H/I 列语义与 cases JSON 契约
│   ├── excel-contract.md     # 契约 + 模板身份 + 与 InfoTest 的三处行为差异
│   └── gotchas.md            # 上机必炸写法与 lint 反馈→修法对照表
└── examples/slb_cases.json   # 样例：2 条 SLB 用例
cex_core/                     # 判据与出件共享库（harness 无关）
├── ist_emit/                 # InfoTest emit_xlsx 最小剪切包（见 references/excel-contract.md）
├── templates/case_template.xlsx   # 冻结快照真模板（SHA 钉死）
├── vendor_cmd.py             # 命令存在性/参数契约判定（逐字抽自 InfoTest vendor_stdlib）
├── scan_destructive.py       # 自毁命令扫描（规则来自数据包 domain_grammar.json，读不到即拒）
├── security_scrub.py         # 凭据脱敏（逐字抽自 InfoTest）
└── defects/                  # 缺陷页解析 + 脱敏（逐字抽自 InfoTest main/ingest）
cex_client/                   # 客户端（只用标准库）
├── workspace.py              # 唯一路径解析器：<文件夹>/.compile-excel/
├── auth.py / bundle.py       # 设备流登录与令牌轮换；数据包同步
├── gateway.py / device.py    # 网关 MCP 客户端、租约；提交、状态、结果与回执
├── portal.py / bugs.py       # 门户扫码登录；按单号取缺陷单
├── tools.py                  # 工具实现（三个适配器共用）
└── tool_specs.json           # 工具 schema 单一来源
adapters/pi/                  # pi 扩展：index.ts（转发到 cex_tool）+ tools.generated.ts（由 specs 生成）
adapters/circle/extension.py  # circle 扩展：register(api) 注册 cex_* 工具
.claude-plugin/               # Claude Code 插件与 marketplace 清单（MCP 服务指向 bin/cex_mcp_proxy.py）
package.json                  # pi 包清单（extensions + skills）
bin/cex_tool                  # 命令行调用工具（pi 扩展、无工具的 harness 与调试用）
bin/cex_mcp_proxy.py          # stdio MCP 服务（Claude Code 插件用）
tools/sync_from_infotest.py   # 从 InfoTest 源逐字重新抽取判据代码（--check 查漂移）
tools/gen_adapters.py         # 从 tool_specs.json 生成 pi 的 TypeBox 定义（--check 查漂移）
install.py                    # 安装器：发行根落位 + 挂进 claude / pi / circle（--dry-run 看计划）
docs/engine-parity.md         # 与 InfoTest 编译引擎的功能对账（维护者用，不随 skill 加载）
tests/                        # 单测、与 InfoTest 对拍、对真服务端和网关的端到端（不随 skill 分发）
```

测试：`python -m pytest tests -q`（对拍与端到端需要同级的 `InfoTest_Engine` 与
`compile-excel-server` 检出，缺就跳过；可用 `INFOTEST_ROOT` / `CES_SERVER_ROOT` 指定）。
pi 的类型检查与真 pi 运行需要 `PI_NODE_MODULES` 指向装有 `@mariozechner/pi-coding-agent`、
`typescript` 的 node_modules；Claude Code 清单校验需要本机有 `claude` CLI。
