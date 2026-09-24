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
compile-excel/
├── SKILL.md                  # 加载入口：任务表 + 硬性 invariant + 工作流（渐进式披露）
├── scripts/
│   ├── compile_excel.py      # 用例 JSON → FileIR → emit_xlsx（唯一出盘通道，薄 CLI）
│   ├── ist_emit/             # InfoTest emit_xlsx 最小剪切包（见 references/excel-contract.md）
│   ├── verify_batch.py       # 产物验收报告（pass/fail/totals）
│   ├── login.py / fetch.py / docs_query.py / ist_client.py   # 工件同步客户端
│   ├── bind_env.sh           # 非交互写环境绑定
│   ├── collect_credentials.sh# 掩码凭据收集（无 secret-UI 的 harness 兜底）
│   └── preflight.py          # 绑定检查 + TCP 探活（结构化 JSON）
├── templates/
│   └── case_template.xlsx    # 冻结快照真模板（585 晋升版，SHA 钉死）
├── references/               # 按需加载：SKILL.md 里有明确指针
│   ├── column-semantics.md   # E/F/G/H/I 列语义与 cases JSON 契约
│   ├── excel-contract.md     # 契约 + 模板身份 + 与 InfoTest 的三处行为差异
│   ├── gotchas.md            # 上机必炸写法与 lint 反馈→修法对照表
│   ├── env-setup.md          # 首次使用 Setup 访谈 + 凭据通道
│   └── server-sync.md        # 分发服务器对接（可选）
├── examples/slb_cases.json   # 样例：2 条 SLB 用例
├── tests/                    # 结构自检 + InfoTest 对拍/深验脚本（随 skill 分发）
└── .env.example
```
