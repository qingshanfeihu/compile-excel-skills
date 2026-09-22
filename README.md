# compile-excel-skills

把用例内容（脑图 / 用例列表 / 步骤 JSON）编译成**结构正确**的 `case.xlsx` 的 Agent Skill。
结构（执行页、表头、E/F/G/H/I 列语义、契约 marker）由脚本保证，内容由 agent 整理。
设计上与 InfoTest 编译出件的哲学一致（见 `compile-excel/reference/` 标注的上游来源），
但**不做上机验证**——那是 InfoTest 编译引擎的职责边界。

## 安装（prompt 驱动，推荐）

把这句 prompt 发给你的 agent（circle / pi / opencode / claude 均可），安装动作由 agent 在会话内完成：

```
Fetch https://raw.githubusercontent.com/qingshanfeihu/compile-excel-skills/main/INSTALL.md
and follow its instructions to install the compile-excel skill.
```

安装指令详见 [INSTALL.md](INSTALL.md)
（实体拷贝到 `~/.agents/skills/compile-excel`，非 symlink；已安装时先询问再覆盖）。

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
├── SKILL.md                  # 加载入口：Setup 段 + 编译主流程 + 禁止事项
├── scripts/
│   ├── compile_excel.py      # 用例 JSON → case.xlsx（唯一出盘通道）
│   ├── bind_env.sh           # 非交互写环境绑定
│   └── preflight.py          # 绑定检查 + TCP 探活（结构化 JSON）
├── templates/
│   └── case_template.v2.xlsx # 契约模板（占位版，待接 InfoTest 晋升模板）
├── reference/
│   ├── column-semantics.md   # E/F/G/H/I 列语义与 cases JSON 契约
│   └── excel-contract.md     # IST_EXCEL_CONTRACT / IST_EXECUTION_SHEET 契约
└── .env.example
```
