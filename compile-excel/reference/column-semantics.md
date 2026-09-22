# 列语义（E/F/G/H/I）

来源：InfoTest_Engine `main/ist_core/tools/device/emit_xlsx_tool.py`（compile_emit 工具说明）
与 `main/case_compiler/excel_contract.py` 的 `EXECUTION_HEADERS`。同步上游改动时更新本文并标注 commit。

## 执行页表头（A→I，逐字一致，顺序不可变）

| 列 | 表头 | 含义 |
|---|---|---|
| A | 自动化ID | 用例唯一标识，同一条用例的所有步骤行重复同一值 |
| B | 优先级 | 如 P0-P7，可空 |
| C | 语句类型 | 如 功能/性能，可空 |
| D | 描述 | 用例描述，步骤行重复同一值 |
| E | 测试对象 | 操作对象：被测设备 / check_point / test_env / time 等 |
| F | 方法 | 步骤动作类型，**只允许下表方法集** |
| G | 数据 | 命令或期望文本（内容的核心载体） |
| H | 临时保存期望结果 | save_as：把本步输出存为变量名，可空 |
| I | 输入变量 | input_var：引用 H 列存下的变量，可空 |

## F 列允许的方法集（收紧而非放开）

`cmd_config` · `cmds_config` · `found` · `not_found` · `found_times` · `事实源主机名` · `sleep`

不在集合内的方法一律拒绝出盘（防止框架侧找不到动作实现形成空真结果）。

## 文件级前置命令

cases JSON 顶层的 `init_commands` 数组是**整个工作簿执行前**的前置命令序列，
不属于任何单步；脚本只透传统计，不写入步骤行。

## cases JSON 步骤五元组

```json
{"e": "被测设备", "f": "cmd_config", "g": "show version", "h": "ver_text", "i": ""}
```
