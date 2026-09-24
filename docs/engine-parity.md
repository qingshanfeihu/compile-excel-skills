# InfoTest 引擎 vs compile-excel skill 功能对账

> 2026-09-24 实测基线：同一脑图（slb virtual httplist 等 list 命令支持 no 和 clear），
> 引擎最好成绩 internala-final1/httplist_qwen3 = 5/5 上机 pass；skill 路线 slb_virtual_list_0923 =
> 5/5 pass、slb_list_noclear_full = 3/3 pass + verify_batch 11/11。**判定通道同源**
> （都是 10.4.127.103 框架真跑 + MySQL result DB），差距全部在判定通道**之前和之后**。

## 0. 一句话定位

- **引擎** = 12 节点事件溯源闭环：多轮 LLM 编排 + 知识投影 + 机械门禁 + 四层归因 + 不动点返工。
- **skill** = 单会话轻路径：Circle（LLM）+ 7 个确定性脚本；编译契约与上机通道已与引擎同源，
  缺的是知识面、门禁深度、归因与返工纪律。
- **架构结论**：skill 不应复刻引擎的 LLM 编排（那是 Circle 会话本身），应把引擎的
  **确定性资产**（知识投影、门禁、判定语义）当作服务消费。差距按"借服务"还是"自建"分级。

## 1. 管线对照（引擎 12 节点 vs skill 阶段）

| 引擎节点 | 引擎实现（代码事实） | skill 对应 | 差距级 |
|---|---|---|---|
| prep | compile_prep：脑图解析、管辖 SPEC 检索（governing_spec_status：bound/ambiguous/no_governing_spec）、版本锚定（vendor_build_anchor） | `cex_sync` 数据包（按工作区 device_build 取 stable 包）；`cex_env_prepare` 核对床自述 build | **P1**：无管辖 SPEC 检索；build 锚定由数据包 + env_prepare 承担 |
| recompose | 专职 fork + 引擎分片（assigned_autoids）、步骤适配（cmdtree 证据纠拼写）、过程值具体化、重绑许可（rebind_license）、proposal 披露、契约盖 seal | Circle 会话内做（mindmap-recompose 直接预览，governing_spec 恒 null） | **P0/P1**：无 spec 绑定、无命令树证据、无分片；零发明纪律已对齐 |
| bed_gate | 环境池租约（env_pool.acquire_lease）、床身份钉死（execution_bed_identity_mismatch）、stale pytest 清理（force_clean）、device_busy 全局锁、设备可达探测 | 网关单床租约（flock 床锁随 pytest 进程组继承 + fencing token）+ `cex_env_prepare`（框架/可达/build/规则） | **P2**：单床；多床池未做 |
| author | compile-worker fork 多轮：供给检查（supply_check）、载子检查（carriers）、自检 21 次/批、场景保真（scenario-fidelity fork：机械比对在先，模型判残差）、escalate/de-escalate | Circle 单会话写 cases.json（E/F/G/H/I IR） | **P2**：单会话质量靠模型档位；无机械保真比对 |
| emit | emit 必崩规则（恒真/恒假断言族、崩卷形态，从框架 mirror 源码语义推导）+ emit_xlsx_tool | compile_excel.py（钉死模板 SHA、契约 marker、defined-name、哨兵） | **P1**：契约层同源；**必崩规则族未镜像**（verify_batch 只覆盖 echo-hit 一族） |
| ask_decision | 唯一问人位：情景③④全批来源冲突，interrupt+Command(resume) | 无（Circle 直接问用户） | **P2**：交互面等价，无裁决空间模型 |
| merge | 合并双卡点（重派集 ⊆ fail 集、passed→重编数据层非法、pass 锁卷面 mtime） | `scripts/rework_gate.py`（重派集 ⊆ fail 集、pass 案按 provenance 指纹锁卷面，写 rework.json） | ✅ 主径已补（见 §5 第 5 条） |
| run | dev_run_batch：一次递交整卷、result DB verdict（fail-closed）、detail_tail 证据、result_channel 状态机 | run_device.py / `cex_case_submit` → 网关冻结工作簿、上机前闸、只读落位 sha 对账 → 框架 pytest → 结果库按 task 取回 | ✅ **等价**；结果按任务绑定、早于投递的日志标 stale（引擎按构建表 + case_id 取） |
| reconcile | 真机 vs 预期矛盾处理：六种带身份预期来源（Author/Spec/DefectSpec/Manual/ConfigBinding/CapabilityXml）、权威顺序自动裁决（Spec>Author>CapabilityXml>Manual）+ 披露 | 无；非 pass 只留 detail_tail | **P0**：预期值来源学完全缺失——这是"假断言"防线的中枢 |
| attribute | 四层归因（G/E/V/瞬态）+ attributor fork + submit_attribution（证据须 verbatim）+ 同方法冻结 + 瞬态复发=误归因守卫 | backfill.py 只记 verdict 台账 | **P1**：有证据（detail_tail）无归因 |
| diagnose | fail_attribution → 修复方向分派（G→emit 规则、E→可验证性、V→语义层） | references/gotchas.md 人工对照表 | **P1**：人工环 vs 机械分派 |
| closing | 终验幂等闸 + 人口账（有效终态/隔离/未终结）+ 交付报告 + certification_coverage | run_receipt.md + footprint.jsonl | **P2**：无人口账概念 |

## 2. 知识面对账（差距最大的一块）

| 引擎资产 | 位置 | 用途 | skill 现状 |
|---|---|---|---|
| **cmdtree_585.xml**（真命令树） | knowledge/data/compile_ref/ | 命令存在性/拼写/参数形态的**上机前**判定（`kind=complete` 查询；portlist→portlists 纠错就靠它） | KMS 只有 115 字节 sample 桩；**上机前无命令校验**，靠设备报错兜底 → **P0** |
| capability_atlas / capability_usage_index | compile_ref | 断言方法可用性（verifiability_tool 2686 行的消费面） | 无 → P1 |
| method_reference（.json + 目录） | compile_ref | E/F 方法族语义（found/abs_found/found_times/h 捕获三步形式） | references/column-semantics.md（人读版，覆盖主径）→ P2 |
| criterion_rules / rule_registry | compile_ref | 判词归一（"访问成功"→可判定观察形状）的规则库 | 无；靠 LLM 会话自觉 → P1 |
| device_characteristics / device_behavior_examples | compile_ref | 设备行为先例（echo 形状、静默失败） | 无 → P2 |
| confirmation_prompt_patterns | compile_ref | 确认类命令的交互形态 | 无 → P2 |
| spec 系统（active.json + generations） | knowledge/data/spec/ | 管辖 SPEC 绑定与歧义披露 | 无（recompose 恒 null）→ P1 |
| 手册（10.4.6/10.5.0/10.5.1 cli_cn/app_cn） | knowledge/data/manual/ | 步骤适配的逐字依据（manual:file:line 引用） | KMS docs_query 通道在，内容未接 → P1 |
| mirror_manifest / EXCEL_FUNCTIONS.md / excel_workbook_manifest | compile_ref | 框架行为镜像（emit 必崩规则的推导源） | ist_emit 内嵌了冻结契约快照（同 SHA）→ 部分✅ |

**关键事实**：服务端数据包注册表（按构建、candidate/stable 通道、逐件 SHA-256）已能承载真投影，
发布通道是 compile-excel-server 的 `tools/import_infotest.py`（在跑过 InfoTest 收敛链的工作站上，
只调 InfoTest 自己的解析与校验函数）。本机只验证过合成样例包；**真实导入尚未在工作站上跑过**，
所以 skill 现在拿到的仍不是真投影——这是发布侧待办，不是 skill 代码问题。

## 3. 门禁与纪律对账

| 门禁 | 引擎 | skill | 差距 |
|---|---|---|---|
| 结构/布局/契约 | structural_gate（1739 行）+ lint 双卡点 | verify_batch.py（结构/布局/E-F 模板自举/check_point≥1/found_times 契约/autoid≥12 位/echo-hit） | 主径✅；深度差（崩卷形态族）P1 |
| 恒真/恒假断言族 | emit 必崩规则（mirror 源码语义推导） | 仅"断言不命中命令原文"一条 | **P0**（同族漏洞：命中 prompt 行、命中空回显等未覆盖） |
| 断言可验证性 | verifiability_tool 对 capability 投影 | 无 | P1 |
| 断言审计 | assertion_audit_suite + pass_audit | 无 | P2 |
| 幂等/续跑 | checkpoint SQLite + 终验幂等闸 + verdict 幂等键 | 无（重跑=重编整卷） | P1 |
| 返工合法性 | 重派集⊆fail 集（代码断言）、passed→重编非法、pass 锁 mtime | 无 | P1 |
| 证据不可伪造 | verdict_fact_sha256、mechanical_case_sha256、run identity | run identity（xlsx SHA+时间戳）✅、无逐案 fact hash | P2 |

## 4. 已等价/领先的部分（不要重复建设）

| 能力 | 状态 |
|---|---|
| 上机判定通道（deliver→框架→result DB→verdict） | ✅ 同一框架 test_xlsx + 结果库；经网关投递，sha 对账同款 |
| Excel 契约（表头 29 行/marker/defined-name/钉死模板 SHA） | ✅ 同源（ist_emit 冻结快照） |
| E/F/G/H/I 语义主径 + found_times 硬契约 | ✅ verify_batch 与引擎 structural_gate 对拍过 |
| 断言不命中命令原文（假通过防线第一条） | ✅ skill 先落地（引擎靠 emit 必崩规则覆盖） |
| 凭据安全（不进对话/不落日志） | ✅ 文件夹里只有 OAuth 令牌；跳板机/设备口令只在网关；门户会话在用户级 0600 缓存 |
| 真值回写 | ✅ 各自口径（引擎→knowledge footprint；skill→footprint.jsonl 台账） |
| 速度/透明度 | skill 领先（3 案 42s，全链可对账） |

## 5. 收口计划（按优先级）

**P0（不补就会产假判定/假断言）**
1. ◐ **真命令树进数据包**（`scripts/cmdtree_check.py` / `cex_cmd_check` 读数据包里的命令树投影，
   判定函数逐字抽自引擎 `resolve_vendor_command`，命令头与参数契约都判；服务端只发投影、不发
   原始 XML。**待办：工作站实跑导入器，发布真投影**）。
2. ✅ **恒真/恒假断言族**（2026-09-24 落地：verify_batch 新增 tautology family——提示符形态/
   空串可匹配正则/not_found 命中命令词，附回归测试）。

**P1（质量与纪律）**
3. ✅ 预期值来源标注（2026-09-24 落地：compile 写 `provenance.json` 边车，check_point 带
   `source{kind,ref}`，verify_batch 校验非空；缺省回落 author-verbatim 并计数）。
4. ✅ 归因初版（2026-09-24 落地：run_device 非 pass 案机械归因 G/transient?/undetermined，
   回执带归因层计数；语义层 E/V 仍留给会话，不越权）。
5. ✅ 返工纪律（2026-09-24 落地：`scripts/rework_gate.py` 重派集⊆fail 集、pass 案锁卷面
   （provenance 指纹比对）、--force 整批判废留痕，写 rework.json 轮次账）。
6. ◐ SPEC/手册通道：数据包带 spec / manual 条目，`cex_docs_query` 检索手册，二者都是合法逐字来源；
   **待办：导入器发布真手册/SPEC**。

**P2（体验与闭环深化）**
7. 人口账（有效终态/隔离/未终结）进 run_receipt。
8. runtime slots（`<RUNTIME>` def-use 边车）。
9. 逐案 fact hash 台账。

## 6. 判据（什么算补齐）

同一脑图、同一床、同一晚：skill 路线在「上机前拦截的命令拼写错误数」「恒真断言漏网数」
「非 pass 案的归因覆盖率」「返工环重编案数 ≤ fail 集」四项上与引擎基线对齐，
且 5/5 上机判定保持——即视为功能对账收敛。

## 7. 判据引擎抽取与对拍（Phase 3 / E10）

**抽了什么**：`tools/extract_engine.py` 从六个种子模块出发——`apv_lang`、`vendor_stdlib`、
`step_structure`、`structural_gate`、`mechanical_case_gate`、`mindmap_contract_projector`——
沿顶层 import 走出闭包，共 27 个模块，生成到 `cex_core/engine/`（E5c 又加了 12 个种子，
现在是 48 个模块，见 §8）。模块树与 InfoTest 的
`main` 包一一对应。每个文件按 AST 做了三处机械改动，逻辑一字不改：

- `main.*` 改成 `cex_core.engine.*`，`scripts.*` 改成 `cex_core.engine.scripts.*`；
- `Path(__file__)…parents[k]` 改成数据根下的同一相对目录。数据根由 `CEX_ENGINE_DATA_ROOT`
  指定，布局与 InfoTest 仓根相同；没设时指向一个不存在的目录，读数据的地方按引擎自己的
  "不可达"路径失败关闭；
- 去掉注释（里面有批次名、用例号等内部实证记录；设计理由回 InfoTest 源看）。docstring
  保留，其中的批次名与六位用例号换成占位：langchain 工具的 docstring 就是给模型的工具说明，
  `parse_docstring=True` 还会解析它。E10 那一版连 docstring 一起删了，E5c 接入提交工具时
  langchain 当场报 docstring 格式错误才暴露，已改；替换落到会被当工具说明的 docstring 上时
  抽取直接报错，不静默改提示词。

`MANIFEST.json` 记录每个文件的源 sha256，以及闭包边界。`--check` 比对漂移，默认测试会跑。

**边界**：函数内的延迟 import 没有跟进去。跟进去就是整个引擎：338 个模块，约 23 万行。
这类延迟 import 共 63 处，指向 29 个闭包外模块，最多的是 `emit_xlsx_tool` 12 处、
`command_tree_sync` 8 处、`env_facts` 5 处。其中 15 处包在 try/except 里：在客户端会静默
走另一个分支，而不是报错，所以在清单里标成 `guarded`。
`provenance_ir` 的 ConfigBinding 规则指纹按路径读 InfoTest 源文件（`main/...py`），客户端
没有这些文件，走"源不可达"失败关闭。

**对拍方法**（`tools/engine_parity.py`，插件 `tests/core/engine_alias_plugin.py`）：
在 InfoTest 自己的测试树里跑它自己的测试。一轮用原模块；另一轮把 `main.<抽取模块>`
换成 `cex_core.engine.<模块>`。两轮按 (classname, name) 逐条比较结果（通过/失败/报错/跳过，
失败时再比异常类型）。抽取副本那一轮必须留下"别名已生效"的证据，否则判失败，
否则插件没装上时两轮必然一致。

**结果**（2026-09-24，本机 InfoTest 检出，数据是库内那 8 份 compile_ref，没有镜像，
没有环境派生投影）：

| 模式 | 测试数 | 结果有变化 | 说明 |
|---|---|---|---|
| faithful（闭包外的延迟 import 回落 InfoTest 原模块） | 10,372 | 0（外加 1 条已登记） | 那 1 条是测试按 `structural_gate.__file__` 去同目录读 `emit_xlsx_tool.py`，抽取树里没有这个文件；与引擎行为无关，已按精确结果登记在 `EXPECTED_DIFFS` |
| standalone（闭包外的延迟 import 照客户端的样子失败） | 10,372 | 555 | 474 条是撞上边界的 ModuleNotFoundError；另有约 80 条变成 AssertionError、IndexError 等，是被 try/except 包住的边界 import 悄悄走了另一个分支 |

反向对照：在抽取副本里把 `nearest_candidates` 改成返回逆序，faithful 对拍报出 4 条差异。
更弱的一个改动（`norm_action` 不做归一化）没被检出：现有测试的候选在不归一化时排序也不变。
可见对拍的检出力受限于 InfoTest 测试本身覆盖到哪里。

**证据边界**：
- 基线里有 1318 条失败、241 条报错，主要缺的是环境派生的投影、框架镜像和 Excel 模板。
  这些路径两边都在同一处失败：只证明失败方式一致，没有在真实数据上比过；
- 要在真实数据上对拍，得在跑过收敛链的工作站上重跑
  `CEX_ENGINE_PARITY=full pytest tests/core/test_engine_extract.py`。

**InfoTest 改为转发**：按计划，只有对拍全绿且 InfoTest 测试全绿时才做。本机两个条件都不满足
（环境数据缺失），而且 InfoTest 怎样依赖 cex_core（拷贝进仓，还是 `pip install -e`）
还没定，所以没有改 InfoTest。

## 8. 脑图重组移到客户端（E5c）

**做了什么**：InfoTest 编译引擎的 recompose 节点（`nodes.recompose`）按原顺序移植成客户端的
一层薄胶水 `cex_client/recompose.py`，判据一律调 `cex_core/engine` 里抽取的同一批函数。
四个工具：

| 工具 | 对应引擎 |
|---|---|
| `cex_recompose_prepare` | 封存脑图快照、定位管辖规格书、判缺陷单通道、写两份状态文件、`initialize_machine_mindmap_submission` |
| `cex_recompose_submit_cases` | 在派发作用域里调 `submit_machine_mindmap_cases.func`（逐字闭集、锚定、step_structure、一致性引文都在这里判） |
| `cex_recompose_seal` | `_engine_seal_from_parts`：读台账 → `fill_mechanical_fields` → `submit_machine_mindmap_payload` → 核对提交 |
| `cex_lang_query` | 同一个 `lang_query` 工具函数；带 `out_name` 时进该批的派发作用域 |

技能 `skills/mindmap-recompose/` 从 InfoTest 的重组 skill 与 agent 定义合并移植，规则原文
与 `[Rn]` 编号保留，工具与派发相关的句子改成上面四个工具；分片、直连预览这两种派发形态
客户端没有，相关规则删去。

为此抽取种子加了 12 个：提交与台账（`recompose_submission`、`recompose_parts`、
`recompose_submit_tool`）、`lang_query_tool`、`kms.spec_index`、`rebind_binder`、
`recompose_protocol`、`_sealed_output`、`compile_engine._shared`、`spec_references`，以及
`sync.command_tree_sync` 与 `kms.manual_locator`。后两个原是 `load_vendor_stdlib` 与
`lang_query` 的延迟 import，被 try/except 包着：不抽的话命令树在客户端恒为"不可用"，而且
没有任何报错。现在闭包 48 个模块，延迟 import 138 处，指向 53 个模块，其中 31 处 guarded。

**引擎数据根**（`cex_client/engine_env.py`）：按 InfoTest 仓根的布局，从已同步的数据包摆出
`compile_ref/`（包里的 projections 加 cmdtree 投影）、`manual/<版本>/`、
`auto_env/env_capabilities.json`（设备 OS build，取自 `cmdtree/source.json`）、规格书代际
（要数据包带 `state.tsv`，导入器已补发）和框架镜像。一律复制，不链接。

**与引擎的差别**（只在胶水层）：
- 只收 XMind JSON 导出，只能有一个根标题；
- 规格书定位不开 Jev 精排（调外部 LLM）：只影响语义候选的先后与截取，命中 / 多候选 / 没有
  的判定不变；
- 多个候选时与引擎一样继续（状态 `ambiguous`，给零签发权的参考切片），不问人；引擎的
  "查不到再问一次"面板不移植，`spec='none'` 对应用户在那个面板上拒绝重查，
  `spec=<文件名>` 对应入口点名；
- 缺陷单规格（DefectSpec）不签发：客户端没有查单 → 安全投影 → 密封收据那条通道。规格书绑定
  时状态是 `not_queried`，根标题不带单号时是 `no_ticket_reference`，带单号时结果与引擎两次
  查单都不可用相同（`resolved_absent`，原因写 `client_has_no_defect_spec_channel`）；
  `cex_bug_get` 读到的单子只作线索，`defect:` 出处在提交时被引擎拒收；
- 全部案落盘后由客户端从台账密封。引擎在台账盖满时也是自己密封、不再派 fork；
  `self_check` / `orphan_notes` 两个可选字段引擎本来就不消费；
- 契约投影（contract cards、判词裁定 fork）不在这一步：compile-excel 直接按机械脑图编写。

**测试**（`tests/client/test_recompose.py`、`test_engine_env.py`、`test_cmd_check_projection.py`）：
- 客户端胶水与直接调 InfoTest 原模块逐项一致：同一份脑图、绑定与案，拒收回执、接收回执、
  密封产物字节都相同；
- 缺陷单通道状态逐字段对拍 InfoTest `nodes.py` 的构造函数（含单号识别，覆盖版本号排除）。
  反向对照：去掉"版本号不算单号"那条，测试变红；
- 多候选规格书、带单号的根标题、同结论重来续跑 / 换结论重来、`defect:` 出处被拒、技能文档
  给的 Scenario 2 形状被引擎提交检查接受；
- 数据根摆放：投影加 XML 时 `cex_lang_query` 能补全；只有投影时如实报不可用。

**对拍**（2026-09-24，48 个模块，InfoTest 里所有提到这些模块名的测试文件，共 769 个）：
faithful 模式 15,887 例，初跑 14 例结果不同，逐条查清：
- 6 例在 `test_command_tree_sync`：对拍插件把包名 `cex_core.engine.scripts` 本身错映射成
  `main.scripts`（只处理了带点的子模块）。E10 时没有抽取模块会延迟导入 `scripts.*`，所以没暴露。
  修掉后这个文件两边都是 128 例全过；
- 8 例是读源码文本的测试：抽取副本是 `ast.unparse` 的输出（字符串字面改用单引号）、去了注释、
  文件也不在 InfoTest 仓里。按"两边结果 + 异常类型"逐条登记进 `EXPECTED_DIFFS`，理由写明，
  结果一变就照常算差异。
修完后对这 7 个测试文件整套重跑：240 例，0 例意外差异，8 例已登记。基线 13,419 过、1,436 失败、
283 报错、749 跳过，失败主要是缺环境派生数据，证据边界同 §7。

**顺带发现并修掉的**：
- E3 的 `load_projection` 只认文件里就有 `heads`，而 InfoTest 生成器写的是 `headers` 加
  `manual_declarations`（`heads` 是引擎加载时合出来的）。E3 的测试夹具都是手写的 `heads`，
  所以没抓到：真实投影上 `cex_cmd_check` 与 `scripts/cmdtree_check.py` 会直接报错。已按引擎
  同一规则合成（同名条目拒绝），并补了真实文件形状的测试，旧版在新测试上两例都红；
- `cex_cmd_check` 结果补上命令树路径 `src`（`step_structure` 的对象类型要从它推）；
- 安装器的依赖自检漏了 E10 加的 `pydantic`，也没有 `langchain-core`，已补，并有测试钉住
  requirements 与检查表一致。

**未决**：数据包按决定只发命令树投影、不发原始 XML，而引擎读投影前要按投影里记的文件名与
哈希核对那份 XML。结果是客户端里 `cex_lang_query` 的 param / complete 不可用，
`step_structure` 的对象类型闭集（同样经 `load_vendor_stdlib`）也取不到，引擎于是对对象类型
放行不核。实测：同一份合成投影加上它的 XML，`cex_lang_query` 就能补全；对象类型闭集在带
XML 时能否取到还依赖别的数据，本机没有真实投影，未核。命令存在性与参数个数仍由
`cex_cmd_check` 按同一判定函数给出。怎么补由产品决定，选项见最终报告。

