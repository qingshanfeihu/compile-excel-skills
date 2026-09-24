"""数据根：抽取来的引擎按 InfoTest 仓根的布局读数据（knowledge/…、runtime/…）。

CEX_ENGINE_DATA_ROOT 指向这样一个目录。没设时指向一个不存在的目录：读数据的地方照
InfoTest 自己的"数据不可达"路径失败关闭，而不是悄悄读到别处。
"""

from __future__ import annotations

import json
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


class IdentityListUnavailable(RuntimeError):
    pass


class _Unavailable:
    """外置的身份表不在：任何读取都报错，不当成空集。"""

    def __init__(self, key: str) -> None:
        self._key = key

    def _fail(self, *_args, **_kwargs):
        raise IdentityListUnavailable(
            f"{self._key} is kept out of the generated code; its values live in _identities.json "
            "next to cex_core/engine, which is missing (tools/extract_engine.py writes it)")

    __contains__ = __iter__ = __len__ = __bool__ = _fail

    def __getattr__(self, _name):
        return self._fail


def _cex_identity_set(key: str):
    """抽取时外置的模块级身份常量（tools/extract_engine.py 的 EXTERNALIZED）。"""
    path = Path(__file__).resolve().parent / "_identities.json"
    try:
        table = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _Unavailable(key)
    return frozenset(table[key])
