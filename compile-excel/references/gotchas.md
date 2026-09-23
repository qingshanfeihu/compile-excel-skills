# Gotchas：上机必炸的写法与 lint 反馈→修法对照

来源：InfoTest structural_gate 实测判例（2026-09 真实返工两轮验证）。
本地 `verify_batch.py` 是结构验收，**不判语义**；下表错误本地全绿、引擎侧才拦。

## lint 反馈→修法对照表

| lint code | 根因 | 修法 |
|---|---|---|
| `dangling_assertion` | 断言读 framework result，但 result=None | 两种成因见下；保证断言**正上方**是一个**无 h** 的观察步 |
| `dangling_assertion`（成因A） | 用了 `APV_0::cmd`——cmd 只执行不回显，不产生 observation echo | `f` 改 `cmd_config` |
| `dangling_assertion`（成因B） | 观察步带 `h`（save_as）——捕获进变量，**不更新 framework result** | 简单断言：去掉 `h`；要比对变量：三步捕获形式（下节） |
| `autoid_malformed` / 边界丢失 | autoid 非 18 位数字（或 <12 位） | 12-24 位纯数字，生产惯例 18 位 |
| `found` 自匹配失败 | 期望文本含正则元字符（`.` `+` `@` `$` 等），框架按**正则**编译 G | 字面比对用 `abs_found`；或逐个转义（`10\.1\.1\.1`） |
| `found_times` 契约违规 | I 列非正整数次数，或 H 列非空 | I=正整数字符串、H 留空 |
| `ambiguous_observation_binding` | 连续多个观察步后只断言最后一个 | 断言紧跟它验证的那个观察步；中间的观察要么删、要么用 h 捕获后显式引用 |

## 方法语义速查（APV_0 为例）

| 方法 | 产生回显 | 更新 framework result | 适用 |
|---|---|---|---|
| `cmd` | 否 | 否 | 纯执行（reboot 之类），后面**不能**直接跟断言 |
| `cmd_config` | 是 | 无 h 时是 | 配置/观察两用；断言的标准供能步 |
| `cmds_config` | 是（多行） | 无 h 时是 | 文件级 init 块、多命令 |
| `execute` | 动作语义 | — | `动作：载荷` 形式，走 execute registry |

**规则一句话：断言消费的是"正上方那个无 h 步骤"的回显。**

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

- `verify_batch` Layer 1 全绿 ≠ 语义正确（dangling、G 语法它不判）。
- 引擎可用时务必跑 Layer 2（`IST_ENGINE_ROOT` 透传给 execute 子进程再调
  `tests/deep_check_infotest.py`）；不可用时在汇报里明说"语义终判未跑"。
