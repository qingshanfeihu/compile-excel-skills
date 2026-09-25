# 生成：tools/extract_engine.py ← InfoTest main/common/runtime_paths.py（sha256 588c198e03038907）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import os
import tempfile
from pathlib import Path
_REPO_ROOT = _cex_data_path('')

def runtime_path(*parts: str) -> Path:
    if os.environ.get('PYTEST_CURRENT_TEST'):
        return Path(tempfile.gettempdir()).joinpath(f'ist_pytest_runtime.{os.getpid()}', *parts)
    return _REPO_ROOT.joinpath('runtime', *parts)
