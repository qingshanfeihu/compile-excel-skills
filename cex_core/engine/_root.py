"""数据根：抽取来的引擎按 InfoTest 仓根的布局读数据（knowledge/…、runtime/…）。

CEX_ENGINE_DATA_ROOT 指向这样一个目录。没设时指向一个不存在的目录：读数据的地方照
InfoTest 自己的"数据不可达"路径失败关闭，而不是悄悄读到别处。
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT_ENV = "CEX_ENGINE_DATA_ROOT"
_UNSET = Path(__file__).resolve().parent / ".data-root-unset"


def data_root() -> Path:
    raw = os.environ.get(DATA_ROOT_ENV, "").strip()
    return Path(raw).expanduser().resolve() if raw else _UNSET


def data_root_configured() -> bool:
    return data_root() != _UNSET


def _cex_data_path(rel: str = "") -> Path:
    """原来 ``Path(__file__)`` 往上数到的那个目录，换算到数据根下。"""
    root = data_root()
    return root / rel if rel else root
