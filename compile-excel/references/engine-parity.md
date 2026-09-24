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
| prep | compile_prep：脑图解析、管辖 SPEC 检索（governing_spec_status：bound/ambiguous/no_governing_spec）、版本锚定（vendor_build_anchor） | link_status/fetch（KMS 绑定） | **P1**：无 SPEC 检索与 build 锚定 |
| recompose | 专职 fork + 引擎分片（assigned_autoids）、步骤适配（cmdtree 证据纠拼写）、过程值具体化、重绑许可（rebind_license）、proposal 披露、契约盖 seal | Circle 会话内做（mindmap-recompose 直接预览，governing_spec 恒 null） | **P0/P1**：无 spec 绑定、无命令树证据、无分片；零发明纪律已对齐 |
| bed_gate | 环境池租约（env_pool.acquire_lease）、床身份钉死（execution_bed_identity_mismatch）、stale pytest 清理（force_clean）、device_busy 全局锁、设备可达探测 | run_device 直连单床（.103）；无租约/清场检查 | **P1**：单床假设成立时够用；多床/并发无保护 |
| author | compile-worker fork 多轮：供给检查（supply_check）、载子检查（carriers）、自检 21 次/批、场景保真（scenario-fidelity fork：机械比对在先，模型判残差）、escalate/de-escalate | Circle 单会话写 cases.json（E/F/G/H/I IR） | **P2**：单会话质量靠模型档位；无机械保真比对 |
| emit | emit 必崩规则（恒真/恒假断言族、崩卷形态，从框架 mirror 源码语义推导）+ emit_xlsx_tool | compile_excel.py（钉死模板 SHA、契约 marker、defined-name、哨兵） | **P1**：契约层同源；**必崩规则族未镜像**（verify_batch 只覆盖 echo-hit 一族） |
| ask_decision | 唯一问人位：情景③④全批来源冲突，interrupt+Command(resume) | 无（Circle 直接问用户） | **P2**：交互面等价，无裁决空间模型 |
| merge | 合并双卡点（重派集 ⊆ fail 集、passed→重编数据层非法、pass 锁卷面 mtime） | 无（整卷重编） | **P1**：返工纪律缺失（见 §3） |
| run | dev_run_batch：一次递交整卷、result DB verdict（fail-closed）、detail_tail 证据、result_channel 状态机 | run_device.py = **同一 FrameworkMCPClient 无头驱动**，deliver SHA 对账 + run_and_wait + fetch_case_detail | ✅ **等价**（本轮补齐） |
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

**关键事实**：24 个投影里，skill 通过 KMS manifest 协议**一个真投影都还没拿到**——
`device_build: SAMPLE_BUILD_LOCAL`。cmdtree 缺失不是 skill 代码问题，是 **KMS 内容建设问题**；
fetch.py 的协议（manifest+sha256+receipt）已经能承载真投影。

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
| 上机判定通道（deliver→框架→result DB→verdict） | ✅ 同一 FrameworkMCPClient，deliver SHA 对账同款 |
| Excel 契约（表头 29 行/marker/defined-name/钉死模板 SHA） | ✅ 同源（ist_emit 冻结快照） |
| E/F/G/H/I 语义主径 + found_times 硬契约 | ✅ verify_batch 与引擎 structural_gate 对拍过 |
| 断言不命中命令原文（假通过防线第一条） | ✅ skill 先落地（引擎靠 emit 必崩规则覆盖） |
| 凭据安全（不进对话/不落日志） | ✅ 双方同纪律（env 绑定 600，由用户自行写入） |
| 真值回写 | ✅ 各自口径（引擎→knowledge footprint；skill→footprint.jsonl 台账） |
| 速度/透明度 | skill 领先（3 案 42s，全链可对账） |

## 5. 收口计划（按优先级）

**P0（不补就会产假判定/假断言）**
1. ✅ **真命令树进 KMS**（2026-09-24 部分落地：`scripts/cmdtree_check.py` 已实现编译期
   grounding，树自动发现 `KNOWLEDGE_DIR`/workspace `knowledge/`/引擎 compile_ref；实测抓
   出原文 `portlist` 单数拼写并给出 `portlists` 建议。**待办：KMS 服务侧发布真投影**
   ——现在 KMS 里仍是 sample 桩，树只在本机/引擎仓可得）。
2. ✅ **恒真/恒假断言族**（2026-09-24 落地：verify_batch 新增 tautology family——提示符形态/
   空串可匹配正则/not_found 命中命令词，附回归测试）。

**P1（质量与纪律）**
3. ✅ 预期值来源标注（2026-09-24 落地：compile 写 `provenance.json` 边车，check_point 带
   `source{kind,ref}`，verify_batch 校验非空；缺省回落 author-verbatim 并计数）。
4. ✅ 归因初版（2026-09-24 落地：run_device 非 pass 案机械归因 G/transient?/undetermined，
   回执带归因层计数；语义层 E/V 仍留给会话，不越权）。
5. ✅ 返工纪律（2026-09-24 落地：`scripts/rework_gate.py` 重派集⊆fail 集、pass 案锁卷面
   （provenance 指纹比对）、--force 整批判废留痕，写 rework.json 轮次账）。
6. ◐ SPEC/手册通道：KNOWLEDGE_DIR 约定已立（recompose 把 *.md 当合法逐字来源），
   KMS docs_query 通道在；**待办：KMS 内容侧接真手册/SPEC**。

**P2（体验与闭环深化）**
7. 人口账（有效终态/隔离/未终结）进 run_receipt。
8. runtime slots（`<RUNTIME>` def-use 边车）。
9. 逐案 fact hash 台账。

## 6. 判据（什么算补齐）

同一脑图、同一床、同一晚：skill 路线在「上机前拦截的命令拼写错误数」「恒真断言漏网数」
「非 pass 案的归因覆盖率」「返工环重编案数 ≤ fail 集」四项上与引擎基线对齐，
且 5/5 上机判定保持——即视为功能对账收敛。
