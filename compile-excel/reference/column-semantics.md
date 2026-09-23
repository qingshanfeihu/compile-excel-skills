# 列语义（E/F/G/H/I）

来源：InfoTest_Engine `main/ist_core/tools/device/emit_xlsx_tool.py`（compile_emit 工具说明、
`_steps_to_caseir`）与 `main/case_compiler/excel_contract.py` 的 `EXECUTION_HEADERS`。
模板冻结快照的 K-P 列即下表 E/F 合法值的出处（见 excel-contract.md）。

## 执行页表头（A→I，第 29 行，逐字一致，顺序不可变）

| 列 | 表头 | 含义 |
|---|---|---|
| A | 自动化ID | 用例唯一标识：**12-24 位纯数字（生产惯例 18 位）**，仅每条用例首行填写（续行留空）；低于 12 位不被框架识别为用例边界，出件即拒 |
| B | 优先级 | P0-P9，仅首行 |
| C | 语句类型 | Author 行=0，init 行=1，步骤行从 2 递增 |
| D | 描述 | 步骤描述，每步骤行携带 |
| E | 测试对象 | 见下表 |
| F | 方法 | 见下表 |
| G | 数据 | 命令或期望文本（内容的核心载体） |
| H | 临时保存期望结果 | save_as：把本步输出捕获为变量，供后续比对 |
| I | 输入变量 | input_var：引用捕获变量或次数等参数 |

## E 列合法对象 × F 列方法族（来自冻结模板 K-P 清单）

| E | F 方法族 |
|---|---|
| `APV_0` / `APV_1`（被测设备） | `cmd` `cmd_config`（单条）`cmd_enable` `cmds_config`（多条，换行分隔）`execute` `activeCert` `importCert` `importKey` `importRootCA` `ha_default` |
| `check_point`（断言） | `found`（正则 DOTALL）`abs_found`（字面）`not_found` `found_times`（I 列=正整数次数，H 必空） |
| `routera` `server213` `server231` `server232`（邻接主机） | `cmd` `execute` |
| `test_env`（测试环境主机） | F=网络事实源里的主机名（如 `clientc`/`console`/`routera`，框架按 `getattr(env, F)` 分派，**必须小写**） |
| `time` | `sleep` |

## G 列格式（框架按字面/正则匹配，不解析变量名）

- 配置类（APV/cmd 族）：`cmd_config` 的 G = 单条命令裸文本；`cmds_config` 的 G = 换行分隔的多条命令裸文本
- `check_point::found/not_found`：G = 正则；`abs_found`：G = 字面文本
- check_point 检查的是**上一个非 check_point 步骤**的输出，输出型步骤（show 等）必须在前

## H/I 捕获比对与自动归一（脚本保证）

- H 捕获的变量，后续 check_point 比对同值时脚本自动 `found`→`abs_found`（捕获值含正则元字符，字面匹配才判得对）
- check_point 把已捕获变量名误写进 G 列时，脚本自动移到 H 列（寄存器查找语义）
- 每条用例必须至少一个 check_point（否则上机必失败：pass 要求 success>0），缺则拒绝出盘

## 文件级前置命令

cases JSON 顶层的 `init_commands` 数组合并为一条 `APV_0::cmds_config` 共享前置块，
写在 Author 行之后、各 case 之前（C=1）。**会落卷面**（早期桩只统计不写入，已作废）。

## cases JSON 步骤五元组

```json
{"e": "APV_0", "f": "cmd_config", "g": "show version", "h": "ver_text", "i": "", "desc": "可选步骤描述"}
```

键名 e/f/g/h/i 与 E/F/G/H/I 等价；末尾自动垫哨兵 case（`--no-sentinel` 可关）。
