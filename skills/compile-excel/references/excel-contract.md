# Excel 契约

上游来源：InfoTest_Engine `main/case_compiler/excel_contract.py`（`SCHEMA = "ist.excel.function-contract"`）的
`resolve_execution_sheet` 子集，随 `cex_core/ist_emit/excel_contract.py` 剪切分发。

## 模板身份（冻结快照，钉死）

| 项 | 值 |
|---|---|
| 模板文件 | `cex_core/templates/case_template.xlsx`（发行根下） |
| 模板 SHA256 | `46aa14dfffbe767ec486dc6b186d582458d666de8a8f6aec2294f920077a45f9` |
| marker 契约 SHA（A1 行 C 列） | `ca32544f34bbd8662e14320e1cec7ca7892df63a3852a24f496ae2e2eb1fdf6c` |
| runtime schema | `ist.excel.runtime` |
| 晋升回执 | `runtime/excel_release/promotion_receipt.json`：status=promoted，verdict=pass，device_build=`SAMPLE_BUILD_LOCAL`，runtime_template_file_sha256 与上表逐字一致 |
| 来源快照 | InfoTest_Engine 本地副本（2026-09-22 晋升的 585 版真机验收模板） |

出件时模板 SHA 与钉死值不符即拒绝（`cex_core/ist_emit/xlsx_emit.select_runtime_template`）。

## 执行页定位语义（真语义，替换早期"表头在第 1 行"的占位假设）

- 全 sheet 扫描**唯一**完整 A-I 表头行（本模板在第 29 行，不在第 1 行）；
- defined-name `IST_EXECUTION_SHEET` 必须精确指向 `$A$29:$I$29`（表头行的绝对引用）；
- `IST_EXCEL_CONTRACT` marker（A1）必须在表头之前且唯一，携带 runtime schema 与契约 SHA；
- marker 版本经 schema 归一（`.vN` 后缀剥离）后必须等于 `ist.excel.runtime`，契约 SHA 必须等于钉死值；
- **禁止 legacy 回退**：缺 marker/defined-name 的工作簿一律拒绝（`allow_legacy` 缺省 False）。

## 出盘纪律

- fd 级原子写盘：staging inode（O_EXCL+O_NOFOLLOW）→ fsync → 硬链备份 → `os.replace` → 目录 fsync → 读回复核 → 失败验证回滚（`cex_core/ist_emit/xlsx_emit.py`，全链 `dir_fd` 绑定校验）
- 目的地必须形如 `<输出根>/<单段批次名>/case.xlsx`；拒绝符号链接与多硬链目标
- 数据区清空后按真语义布局：Author 行（C=0）→ init 行（C=1，`APV_0::cmds_config` 共享前置块）→ 各 case 步骤行（C=2+i 起递增，首行带 A/B/D，续行仅 E-I）→ case 间空行 → 末尾哨兵 case（`999999999999999`/P9/`time::sleep 1`，框架延迟执行契约）
- 模板继承单元格做凭据 redact（字面量源见下）

## 与 InfoTest 的三处行为差异（声明，勿删）

1. **失去 contract 数据驱动的 G 列内容校验**。InfoTest 出件时按 1.1MB
   `excel_contract.json` 逐行校验 E/F 启用状态与 G 参数签名绑定；skill 版不携带该
   数据，G 列内容合法性归 agent（按 `reference/column-semantics.md` 整理），
   InfoTest lint/contract 校验兜底（对拍工具：`tests/reverse_check_infotest.py`）。
2. **模板是冻结快照，非晋升链**。InfoTest 生产模式走 promotion receipt 验证的
   candidate→promoted 晋升链；skill 版内置一份 585 晋升模板并把 SHA 钉死，换模板
   = 改钉死常量 + 重新分发 skill。
3. **凭据字面量镜像源变为本地可选文件**。InfoTest 从框架镜像源码 AST 提取凭据
   字面量做 redact；skill 版改读 `~/.config/compile-excel/credentials.deny`
   （一行一个字面量，缺省空集）。加固性质不变，出件不依赖该文件。
