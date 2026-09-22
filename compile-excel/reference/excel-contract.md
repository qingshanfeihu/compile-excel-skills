# Excel 契约

来源：InfoTest_Engine `main/case_compiler/excel_contract.py`（`SCHEMA = "ist.excel.function-contract"`）。
**当前模板为骨架占位版**：真实模板应由 InfoTest 的 release promotion 产物晋升而来；
接入真实模板后更新本文件并标注来源 commit。

## marker

- `IST_EXECUTION_SHEET`：定位执行页的唯一依据。扫描所有 sheet 的单元格，命中即执行页；
  **禁止**回退到"第一个 sheet"之类的猜测。
- `IST_EXCEL_CONTRACT`：契约 marker，模板必须携带；无 marker 的 markerless legacy 模板一律拒绝。

## 模板版本

- v2：现役候选（含 `IST_EXCEL_CONTRACT`）。本骨架的 `templates/case_template.v2.xlsx` 即按此生成。
- 上游规则：生产模式优先选"已完成同 SHA 真机验收"的新契约模板；缺晋升凭证时用现役 v2 候选；
  不回落 markerless legacy（见 `excel_release.py` 的模板选择逻辑，剪切时简化掉了晋升链）。

## 出盘纪律

- 表头逐字校验（见 column-semantics.md），不一致拒绝出盘
- 原子写盘（tmp + rename），半成品文件不可见
- 只重写执行数据区，模板结构（sheet 顺序、隐藏列、样式）不动
