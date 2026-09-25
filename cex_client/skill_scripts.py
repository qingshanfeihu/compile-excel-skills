"""compile-excel 技能自带的出件与验收脚本，按文件加载（它们与 cex_client 同在发行根下）。

cex_author_emit 出件走的就是模型手动出件时跑的同一份 compile_excel.py / verify_batch.py，
不另写一份。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from .errors import ClientError

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "compile-excel" / "scripts"


def _load(name: str) -> ModuleType:
    path = SCRIPTS / f"{name}.py"
    if not path.is_file():
        raise ClientError(f"the compile-excel skill script {path} is missing; reinstall")
    spec = importlib.util.spec_from_file_location(f"cex_skill_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compile_workbook(cases_path: Path, out_dir: Path) -> dict[str, Any]:
    module = _load("compile_excel")
    try:
        stats = module.compile_excel(str(cases_path), str(out_dir))
    except module.CompileError as exc:
        raise ClientError(f"compile_excel refused the cases: {exc}") from None
    batch = str(stats.get("batch") or "")
    return {**stats, "path": str(Path(out_dir).resolve() / batch / "case.xlsx")}


def verify_workbook(xlsx: Path) -> dict[str, Any]:
    return _load("verify_batch").verify(Path(xlsx))


__all__ = ["compile_workbook", "verify_workbook"]
