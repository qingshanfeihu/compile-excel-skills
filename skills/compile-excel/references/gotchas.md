# Gotchas：上机必炸的写法与 lint 反馈→修法对照

来源：InfoTest structural_gate 实测判例（2026-09 真实返工两轮验证）与测试框架 test_xlsx 的执行语义。
本地 `verify_batch.py` 是结构验收，**不判语义**；下表有的错本地就拦，有的引擎侧才拦。

脑图批（`cex_author_emit` 出件）的修法落在机械用例上：改块、`cex_author_submit_case` 重交、再
`cex_author_emit`。不要改出件的 `cases.json`——`compile_excel.py` 认得出件标记，会拒绝编译它。
下表的修法按手写 `cases.json` 写。

## lint 反馈→修法对照表

| lint code | 根因 | 修法 |
|---|---|---|
| `init rows only reset state` | init_commands 在**每个案之前**重放；在 init 里建的对象会带进每个案，某案重定义同名对象时设备拒绝那一步（实测：init 里 addlist1 绑了 vs3，另一案往 addlist1 加地址被拒） | init 只留 clear/no/show/模式切换；案要用的对象写进该案自己的步骤，用完在本案收尾删掉 |
| `dangling_assertion` / verify 的 `no dangling check_point` | 断言读框架 result：本案里最近一条**不带 H** 的非断言步骤的返回值。没有这样的步骤、或它不是观察，就悬空：没有 result 时框架 preflight 整卷拒跑，result 为 None 时运行到这一行抛错，后面的案都不跑 | 保证断言**正上方**（中间只隔带 H 的步或别的断言）是一个**无 h** 的观察步 |
| `dangling_assertion`（成因A） | 最近那条无 h 的步骤不是观察：`cmds_config` 与 `time::sleep` 返回 None，`cmd_enable` 引擎也不算观察 | 在断言前补一步观察（`cmd_config` 的 show…），配置放在它前面 |
| `dangling_assertion`（成因B） | 前面的观察步都带 `h`（save_as）——捕获进变量，**不更新 framework result**；案首直接断言同理 | 简单断言：去掉 `h`；要比对变量：三步捕获形式（下节） |
| CLI 命令写成 `APV_0::cmd` | `cmd` 在设备的 Linux root shell 里执行（框架 `APV.cmd` → root shell），`show …` 这类 CLI 命令在 shell 里跑不起来，断言读到的是 shell 的报错 | CLI 命令一律 `cmd_config`；`cmd` 只放 shell 命令（`ls`、`cat`、`/ca/bin/…`）。`cmdtree_check.py` 对 `cmd` 里的 CLI 命令给警告 |
| `autoid_malformed` / 边界丢失 | autoid 非 18 位数字（或 <12 位） | 12-24 位纯数字，生产惯例 18 位 |
| `found` 自匹配失败 | 期望文本含正则元字符（`.` `+` `@` `$` 等），框架按**正则**编译 G | 字面比对用 `abs_found`；或逐个转义（`10\.1\.1\.1`） |
| **`found` 期望值包含命令关键词** | G="version" 会匹配到上一步命令 "show version"，引擎判定为自匹配、假通过 | **期望值必须比命令更具体**：改 `g="Version:"`（带冒号/前缀）或 `g="V[0-9]"`（正则匹配版本号格式），让期望匹配输出而非命令本身 |
| `found_times` 契约违规 | I 列非正整数次数，或 H 列非空 | I=正整数字符串、H 留空 |
| `ambiguous_observation_binding` | 连续多个观察步后只断言最后一个（单条命令的 `cmd_config` 配置步也算观察） | 断言紧跟它验证的那个观察步；中间的观察要么删、要么用 h 捕获后显式引用 |

## 方法语义速查（APV_0 为例）

| 方法 | 回显 | 无 h 时对 framework result 的作用 | 适用 |
|---|---|---|---|
| `cmd` | 设备 Linux root shell 的输出 | 置为这段输出 | shell 命令（`ls`、`cat`、`/ca/bin/anetstat`…），**不是** CLI |
| `cmd_config` | CLI 配置模式的输出 | 置为这段输出 | 配置/观察两用；断言的标准供能步 |
| `cmd_enable` | CLI enable 模式的输出 | 置为这段输出，但引擎不认它是观察，断言不能直接跟 | enable 模式命令 |
| `cmds_config` | 逐行发送，不返回 | 置为 None | 文件级 init 块、多命令配置 |
| `time::sleep` | 无 | 置为 None | 等待生效 |
| `execute` | 动作语义 | 置为动作的返回值（没有返回值的动作留下 None） | `动作：载荷` 形式，走 execute registry |

**规则一句话：断言消费的是本案里"最近一条无 h 的观察步"的回显。** 带 h 的步只存寄存器，不动 result。

## 捕获比对三步形式（会话保持/轮转/一致性）

```
{"e":"APV_0","f":"cmd_config","g":"show session","h":"v1"}        # 捕获
{"e":"APV_0","f":"cmd_config","g":"show session"}                 # 再观察（无 h）
{"e":"check_point","f":"found","g":"v1"}                          # 编译器自动归一为 abs_found + h=v1
```

写成 `g:"v1"` 且 v1 恰为前序捕获名时编译器自动移到 h 列并转 `abs_found`——
不要手工写 abs_found+h，让归一化做，provenance 才一致。

## test_env / time

- `test_env` 的 f 是网络事实源主机名，框架按 `getattr(env, F)` 分派且**不转小写**——
  统一写小写（合法主机名均为小写）。
- `time::sleep` 的 g 是秒数字符串。

## verify 的语义边界

- `verify_batch` 全绿 ≠ 语义正确：它判结构、悬空断言、恒真族、出处边车与 init 隔离；G 的语法与
  命令是否在这个 build 上存在它不判（后者是 `cmdtree_check.py`），期望对不对更不判。
- 语义终判是上机：经网关跑框架、取结果库判定（SKILL.md 第 9 步）。没上机就在汇报里明说
  "语义终判未跑"，不要拿 verify_batch 的结果顶替。
