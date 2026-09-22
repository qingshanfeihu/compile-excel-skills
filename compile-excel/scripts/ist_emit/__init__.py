"""ist_emit：InfoTest emit_xlsx 的最小剪切（skill 分发版）。

模块清单与上游对应关系（剪切声明详见 reference/excel-contract.md）：
- _sealed_io.py      ← main/case_compiler/_sealed_io.py（全量；run_governance 钩子置空）
- config.py          ← main/case_compiler/config.py（全量；配置路径参数化）
- schema_identity.py ← main/common/schema_identity.py（全量）
- excel_contract.py  ← excel_contract.py 的 resolve_execution_sheet 子集（身份钉死）
- case_ir.py         ← case_ir.py 的 FileIR/CaseIR/Step/Row
- credential_literals.py ← 字面量源改为本地可选 deny 文件
- xlsx_emit.py       ← xlsx_emit.py（fd 级原子写盘；模板=内置冻结快照+SHA 钉死）

依赖仅 python3 标准库 + openpyxl。
"""

from ist_emit.case_ir import CaseIR, FileIR, Row, Step
from ist_emit.excel_contract import (
    CONTRACT_MARKER,
    EXECUTION_HEADERS,
    EXECUTION_SHEET_MARKER,
    PINNED_CONTRACT_SHA256,
    TEMPLATE_SHA256,
    ExcelContractError,
    resolve_execution_sheet,
)
from ist_emit.xlsx_emit import emit_xlsx, select_runtime_template

__all__ = [
    "CaseIR", "FileIR", "Row", "Step",
    "CONTRACT_MARKER", "EXECUTION_HEADERS", "EXECUTION_SHEET_MARKER",
    "PINNED_CONTRACT_SHA256", "TEMPLATE_SHA256",
    "ExcelContractError", "resolve_execution_sheet",
    "emit_xlsx", "select_runtime_template",
]
