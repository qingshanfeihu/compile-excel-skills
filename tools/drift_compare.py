"""抽取一致性的"只比代码"判定（extract_engine.py / sync_from_infotest.py 的 --code-only 用它）。

本仓对抽取结果做过人工脱敏：注释、文档字符串、少数字符串常量里的内部出处（工单号、内部文档路径、
构建名、评审日期）换成了占位，所以逐字比对必然不一致。--code-only 的规则：
- 注释、文档字符串不比（说明文字）；
- 代码结构（除字符串常量以外的全部语法树）必须一致：判据逻辑改了照样报；
- 字符串常量必须一致，除非它的位置登记在 tools/sanitized_literals.json 里（第几个字符串常量，
  按语法树遍历顺序数，不含文档字符串）。登记表只记文件与位置，不记原文：不把内部内容带进本仓。
  正则等判据字符串不在登记表里，InfoTest 改了它们仍然报。

脱敏改动之后（确认差异都是脱敏）用 --record-sanitized 重新登记。
"""

from __future__ import annotations

import ast
import io
import json
import tokenize
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent / "sanitized_literals.json"


def _without_comments(text: str) -> list[tuple[int, str]]:
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    return [(t.type, t.string) for t in tokens
            if t.type not in (tokenize.COMMENT, tokenize.NL)]


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    return tree


def _scalar_fields(node: ast.AST) -> dict:
    return {k: v for k, v in ast.iter_fields(node) if not isinstance(v, (ast.AST, list))}


def literal_differences(ours: str, fresh: str) -> list[int] | None:
    """注释与文档字符串之外，两份源码只有字符串常量不同时，返回不同的那些字符串的位置；
    代码结构不同（或解析不了）返回 None。"""
    try:
        a = list(ast.walk(_strip_docstrings(ast.parse(ours))))
        b = list(ast.walk(_strip_docstrings(ast.parse(fresh))))
    except SyntaxError:
        return None
    if len(a) != len(b):
        return None
    positions, index = [], 0
    for x, y in zip(a, b):
        if type(x) is not type(y):
            return None
        if isinstance(x, ast.Constant) and isinstance(x.value, str):
            if not isinstance(y.value, str):
                return None
            if x.value != y.value:
                positions.append(index)
            index += 1
            continue
        if _scalar_fields(x) != _scalar_fields(y):
            return None
    return positions


def load_registry() -> dict[str, list[int]]:
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def same_code(rel: str, ours: str, fresh: str, registry: dict[str, list[int]]) -> bool:
    """--code-only 下这个文件算不算一致。非 Python 文件仍逐字比对。"""
    if ours == fresh:
        return True
    if not rel.endswith(".py"):
        return False
    try:
        if _without_comments(ours) == _without_comments(fresh):
            return True
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return False
    positions = literal_differences(ours, fresh)
    return positions is not None and set(positions) <= set(registry.get(rel, []))


def record(entries: dict[str, list[int]]) -> None:
    """--record-sanitized：合并写入登记表（调用方已确认这些差异都是脱敏）。"""
    registry = load_registry()
    for rel, positions in entries.items():
        merged = sorted(set(registry.get(rel, [])) | set(positions))
        if merged:
            registry[rel] = merged
    REGISTRY.write_text(json.dumps(dict(sorted(registry.items())), ensure_ascii=False, indent=1)
                        + "\n", encoding="utf-8")
