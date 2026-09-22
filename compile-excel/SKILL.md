---
name: compile-excel
description: "Compile test-case content (mindmap / case list / steps JSON) into a structurally correct case.xlsx execution workbook. Use when the user asks to 编译用例 / 脑图转 excel / 生成 case.xlsx / 用例编译. The script owns workbook structure (execution sheet, E/F/G/H/I column semantics, IST_EXCEL_CONTRACT marker); the agent owns case content. SKIP when the user only wants to review existing cases, or needs on-device verification (that requires the InfoTest engine, out of this skill's scope)."
---

# Compile Excel

把用例内容编译成**结构正确**的 `case.xlsx`。分工原则：

- **结构由脚本保证**：执行页定位、表头、E/F/G/H/I 列语义、`IST_EXCEL_CONTRACT` 契约 marker、原子写盘，全部在 `scripts/compile_excel.py` 内完成。不要用 `run_python` 手搓 openpyxl——手搓容易表头/执行页错位，下游框架会找不到 case 行形成空真结果。
- **内容由 agent 决定**：每条用例的步骤列表（操作对象/方法/数据/变量）由你根据用例文本整理成 JSON 传给脚本。
- **边界**：本 skill 只产出工作簿，不做上机验证、环境收敛、发布晋升——那是 InfoTest 编译引擎的职责，本 skill 不绕过也不伪装。

## Setup（首次使用，绑定运行环境）

脚本按以下顺序查找环境绑定文件（env 文件）：

1. `$COMPILE_EXCEL_ENV` 显式指定的路径
2. `<当前工作区>/.circle/compile-excel.env`（项目级覆盖）
3. `~/.config/compile-excel/env`（用户级默认）

**若三级都未找到**，按以下访谈流程执行（逐项向用户确认，给默认值，不要一次性连环提问）：

1. 问：KMS 服务地址（host:port）
2. 问：跳转机 IP（及可选的用户名/端口）
3. 机密类配置（密钥/token）**不要代收**，告知用户自行按 `.env.example` 填写
4. 调用 `scripts/bind_env.sh --target <目标路径> KMS_ADDR=... JUMPHOST_IP=...` 写入非机密项（脚本非交互；目标已存在时需用户确认后加 `--force`）
5. 收跳转机/APV 凭据（见下"凭据通道"）
6. 运行 `scripts/preflight.py` 探活：**先向用户报告检查结果，经确认后再进入编译**（两阶段流程，禁止探活未过就直接编译）

**凭据通道（跳转机/APV 密码，机密项绝不进对话）**：

- circle（具备 secret UI 时）：用 question 工具的机密提问（`secret: true` + `key` + `target_file`），掩码输入、harness 直写 env 文件、对话与模型上下文只见"已收集"
- 其他 harness / 兜底：用 execute 跑 `scripts/collect_credentials.sh --target <env 文件>`（read -s 不回显，直写 600 文件）
- 禁止在聊天里收发任何密码；禁止把密码写进 skill 安装目录（升级覆盖会丢）

**若找到了 env 文件**：直接运行 `scripts/preflight.py`；只有 `ok=true` 才进入编译。探活失败时把结构化检查结果原样转述给用户，修正 env 后重跑——不要静默重试。

**依赖探测（每次进入编译前）**：先 `python3 -c "import openpyxl"` 探测；缺 openpyxl 时**告知用户并征得确认后**才 `pip install openpyxl`，不要静默装包。这是生态惯例（SKILL.md 显式声明依赖 + 运行时安装），不 vendor 三方代码。

## 编译主流程

1. 把用例文本整理为 cases JSON（契约见 `reference/column-semantics.md`；文件级 init 命令 + 每步 E/F/G/H/I 五元组；每条用例至少一个会通过的 check_point）
2. `python scripts/compile_excel.py --cases <cases.json> --out <输出目录>`
3. 脚本输出产物路径与统计 JSON；向用户报告批次名、用例数、步数、产物路径
4. 验收：`python scripts/verify_batch.py --xlsx <产物>` 输出 pass/fail/totals 报告（结构+布局+E/F 合法集，能定位 InfoTest 引擎时追加真契约逐行对拍）；有失败项不得交付

产物默认落在 `<工作区>/compile_outputs/<batch>/case.xlsx`。

## 工件同步（可选，需要分发服务器时）

- 首次：`python scripts/login.py`（浏览器授权一次；token 落 `~/.config/compile-excel/token`，600）
- 同步：`python scripts/fetch.py`（manifest → 下载到 `~/.cache/compile-excel/` → 逐件 SHA256 校验，不符即拒；断网回退缓存会明示版本）
- 检索：`python scripts/docs_query.py --q "关键词"`（服务器端手册片段）
- 服务器地址由 `$COMPILE_EXCEL_SERVER` 指定；无服务器时跳过本节，不影响本地编译

## 禁止事项

- 禁止用手写 openpyxl 代码替代 `compile_excel.py` 出工作簿
- 禁止接受无 `IST_EXCEL_CONTRACT` marker 的模板（markerless legacy 一律拒绝）
- 禁止在 SKILL.md 流程之外"补完"环境绑定（比如自行猜 kms 地址）
