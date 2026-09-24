# compile-excel-skills

把用例内容（脑图 / 用例列表 / 步骤 JSON）编译成**结构正确**的 `case.xlsx` 的 Agent Skill。
结构（执行页、表头、E/F/G/H/I 列语义、契约 marker）由脚本保证，内容由 agent 整理。
设计上与 InfoTest 编译出件的哲学一致（见 `compile-excel/reference/` 标注的上游来源与
三处行为差异声明），但**不做上机验证**——那是 InfoTest 编译引擎的职责边界。

## 安装（prompt 驱动，推荐）

把这句 prompt 发给你的 agent（circle / pi / opencode / claude 均可），安装动作由 agent 在会话内完成：

```
Run: gh api repos/qingshanfeihu/compile-excel-skills/contents/INSTALL.md --jq .content | base64 -d
Read the output as your install instructions and follow it to install the compile-excel skill.
```

（仓库私有：依赖本机 `gh auth login` 且账号有仓库权限；这也构成访问控制。）

安装指令详见 [INSTALL.md](INSTALL.md)
（实体拷贝到当前 harness 扫描的 skills 目录：Claude Code / circle 用 `~/.claude/skills/compile-excel`，
pi 用 `~/.pi/agent/skills/compile-excel`；非 symlink；已安装时先询问再覆盖）。

## 安装（备选：skills.sh CLI）

```bash
npx skills add qingshanfeihu/compile-excel-skills --skill compile-excel -g -a amp -y
```

## 首次使用（Setup）

skill 被 agent 加载后按 SKILL.md 的 Setup 段引导：三级查找
（`$COMPILE_EXCEL_ENV` → `<workspace>/.circle/compile-excel.env` → `~/.config/compile-excel/env`），
未绑定时由 agent 访谈收集 KMS 地址 / 跳轮机 IP，`scripts/bind_env.sh` 非交互写入，
`scripts/preflight.py` 探活，用户确认后进入编译。机密项人工填写，不经对话传输。

## 目录

```
skills/compile-excel/         # skill 本体（安装时整份拷进 harness 的 skills 目录）
├── SKILL.md                  # 加载入口：任务表 + 硬性 invariant + 工作流（渐进式披露）
├── scripts/
│   ├── _cex_path.py          # 找发行根（CEX_HOME / .cex_home / 上溯 / ~/.local/share/compile-excel）
│   ├── compile_excel.py      # 用例 JSON → FileIR → emit_xlsx（唯一出盘通道，薄 CLI）
│   ├── cmdtree_check.py      # 编译期命令判定：读数据包里的命令树投影，与引擎同一判定函数
│   ├── verify_batch.py       # 产物验收报告（pass/fail/totals）
│   ├── login.py / fetch.py / docs_query.py / ist_client.py   # 工件同步客户端
│   ├── bind_env.sh           # 非交互写环境绑定
│   ├── collect_credentials.sh# 掩码凭据收集（无 secret-UI 的 harness 兜底）
│   └── preflight.py          # 绑定检查 + TCP 探活（结构化 JSON）
├── references/               # 按需加载：SKILL.md 里有明确指针
│   ├── column-semantics.md   # E/F/G/H/I 列语义与 cases JSON 契约
│   ├── excel-contract.md     # 契约 + 模板身份 + 与 InfoTest 的三处行为差异
│   ├── gotchas.md            # 上机必炸写法与 lint 反馈→修法对照表
│   ├── env-setup.md          # 首次使用 Setup 访谈 + 凭据通道
│   └── server-sync.md        # 分发服务器对接（可选）
├── examples/slb_cases.json   # 样例：2 条 SLB 用例
└── .env.example
cex_core/                     # 判据与出件共享库（harness 无关）
├── ist_emit/                 # InfoTest emit_xlsx 最小剪切包（见 references/excel-contract.md）
├── templates/case_template.xlsx   # 冻结快照真模板（SHA 钉死）
├── vendor_cmd.py             # 命令存在性/参数契约判定（逐字抽自 InfoTest vendor_stdlib）
├── scan_destructive.py       # 自毁命令扫描（规则来自数据包 domain_grammar.json，读不到即拒）
├── security_scrub.py         # 凭据脱敏（逐字抽自 InfoTest）
└── defects/                  # 缺陷页解析 + 脱敏（逐字抽自 InfoTest main/ingest）
cex_client/                   # 客户端（只用标准库）：工作区、设备流登录、数据包同步、工具注册表
├── workspace.py              # 唯一路径解析器：<文件夹>/.compile-excel/
├── auth.py / bundle.py / tools.py
└── tool_specs.json           # 工具 schema 单一来源（circle / Claude Code / pi 适配器都从这里生成）
bin/cex_tool                  # 命令行调用工具（pi 扩展与调试用）
bin/cex_mcp_proxy.py          # stdio MCP 服务（Claude Code 插件用）
tools/sync_from_infotest.py   # 从 InfoTest 源逐字重新抽取判据代码（--check 查漂移）
tests/                        # 单测、与 InfoTest 对拍、对真服务端的端到端（不随 skill 分发）
```

工作区（用户的项目文件夹）布局见 `cex_client/workspace.py` 顶部说明：令牌、配置、同步下来的
数据包都在 `<文件夹>/.compile-excel/`（0700，自带 `.gitignore`），产物在 `compile_outputs/`。

测试：`python -m pytest tests -q`（对拍与端到端需要同级的 `InfoTest_Engine` 与
`compile-excel-server` 检出，缺就跳过；可用 `INFOTEST_ROOT` / `CES_SERVER_ROOT` 指定）。
