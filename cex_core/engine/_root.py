"""数据根：抽取来的引擎按 InfoTest 仓根的布局读数据（knowledge/…、runtime/…）。

CEX_ENGINE_DATA_ROOT 指向这样一个目录。没设时指向 /dev/null 底下一个建不出来的位置：读数据的
地方照 InfoTest 自己的"数据不可达"路径失败关闭，写盘在操作系统那一层就失败（NotADirectoryError，
root 也一样），不会悄悄读写到别处——包目录里也不会长出文件。

引擎模块多数在导入时就按数据根算好路径常量。数据根没设时算出来的路径指向那个不可达位置，之后
再设数据根也改不过来：``modules_bound_while_unset()`` 列出这样的模块，调用方据此拒绝在这个进程
里接着用引擎（先设数据根、换个进程再导入）。

抽取时外置的生产身份表（真实用例号这类）不随包分发：CEX_ENGINE_IDENTITIES 指向它；没设时找抽取
树旁的 _identities.json（开发检出里由 tools/extract_engine.py 写出，不入库、不发给客户端和网关）。
表不可用时读到的是一个一读就报错的占位（失败关闭），不是空集。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DATA_ROOT_ENV = "CEX_ENGINE_DATA_ROOT"
IDENTITIES_ENV = "CEX_ENGINE_IDENTITIES"
# /dev/null 不是目录（POSIX）：它底下的路径读不到、也建不出来，哪个用户都一样
_UNSET = Path(os.devnull) / "CEX_ENGINE_DATA_ROOT-is-unset"
_BOUND_WHILE_UNSET: set[str] = set()


def data_root() -> Path:
    raw = os.environ.get(DATA_ROOT_ENV, "").strip()
    return Path(raw).expanduser().resolve() if raw else _UNSET


def data_root_configured() -> bool:
    return data_root() != _UNSET


def modules_bound_while_unset() -> tuple[str, ...]:
    """数据根没设时就按它算过路径的模块（多数在导入时算成模块常量）。

    非空说明这个进程里的引擎拿着指向不可达位置的路径，之后再设 CEX_ENGINE_DATA_ROOT 也改不
    过来：调用方应拒绝在这个进程里接着用引擎。"""
    return tuple(sorted(_BOUND_WHILE_UNSET))


def _cex_data_path(rel: str = "") -> Path:
    """原来 ``Path(__file__)`` 往上数到的那个目录，换算到数据根下。"""
    root = data_root()
    if root == _UNSET:
        try:
            caller = sys._getframe(1).f_globals.get("__name__") or "?"
        except (AttributeError, ValueError):
            caller = "?"
        _BOUND_WHILE_UNSET.add(str(caller))
    return root / rel if rel else root


class IdentityListUnavailable(RuntimeError):
    pass


class _Unavailable:
    """外置的身份表不可用：任何读取都报错，不当成空集。"""

    def __init__(self, key: str, reason: str = "") -> None:
        self._key = key
        self._reason = reason

    def _fail(self, *_args, **_kwargs):
        why = f" ({self._reason})" if self._reason else ""
        raise IdentityListUnavailable(
            f"{self._key} is kept out of the shipped engine and its identity table is "
            f"unavailable{why}; set {IDENTITIES_ENV} to the _identities.json that "
            "tools/extract_engine.py writes from the InfoTest source")

    __contains__ = __iter__ = __len__ = __bool__ = _fail

    def __getattr__(self, _name):
        return self._fail


def _identity_table() -> Path:
    raw = os.environ.get(IDENTITIES_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parent / "_identities.json"


def _cex_identity_set(key: str):
    """抽取时外置的模块级身份常量（tools/extract_engine.py 的 EXTERNALIZED）。

    表不在、读不成、没有这一项或形状不对，都返回一读就报错的占位：不当成空集，也不让导入失败
    （同一模块里用不到身份表的功能照常可用）。"""
    path = _identity_table()
    try:
        table = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _Unavailable(key, f"{path} does not exist")
    except (OSError, UnicodeError, ValueError) as exc:
        return _Unavailable(key, f"{path} is unreadable: {type(exc).__name__}")
    values = table.get(key) if isinstance(table, dict) else None
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        return _Unavailable(key, f"{path} has no list of strings under this key")
    return frozenset(values)
