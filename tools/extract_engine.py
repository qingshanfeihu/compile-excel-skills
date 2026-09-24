#!/usr/bin/env python3
"""从 InfoTest 源抽取编译判据引擎到 cex_core/engine（改判据先改 InfoTest，再跑本脚本）。

  python3 tools/extract_engine.py --infotest-root ../InfoTest_Engine [--out .] [--check]

抽取对象是 SEEDS 的顶层 import 闭包（函数内的延迟 import 不跟：它们多数指向编排层，
跟进去就是整个引擎）。每个模块按 AST 机械变换后重新生成，逻辑一字不改：

- ``main.*`` 导入改成 ``cex_core.engine.*``；
- ``Path(__file__)…parents[k]`` / ``.parent`` 这类"按源码位置找仓根"的表达式，改成
  ``_cex_data_path("<相对仓根的目录>")``：数据根由环境变量 CEX_ENGINE_DATA_ROOT 指定，
  布局与 InfoTest 仓根相同（knowledge/…、runtime/…）；
- 去掉注释（其中有批次名、用例号等内部实证记录；设计理由回 InfoTest 源看）。docstring
  保留——工具函数的 docstring 就是给模型的工具说明，langchain 还会解析它；docstring 里的
  批次名与六位用例号换成占位（_sanitize_docstrings），换到会被当工具说明的 docstring 上就
  报错，不许静默改提示词。

指向闭包外模块的延迟 import 原样保留（运行到那里会 ModuleNotFoundError），全部记进
cex_core/engine/MANIFEST.json 的 boundary，并标出被 try/except 包住、可能静默走另一
分支的那些。--check 只比对不写，有差异退出码 1。
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

SEEDS = (
    "main.case_compiler.apv_lang",
    "main.case_compiler.vendor_stdlib",
    "main.case_compiler.step_structure",
    "main.ist_core.tools.device.structural_gate",
    "main.case_compiler.mechanical_case_gate",
    "main.case_compiler.mindmap_contract_projector",
    # E5c：脑图重组的提交、零件台账、语言查询与 SPEC 索引
    "main.ist_core.tools.device.recompose_submission",
    "main.ist_core.tools.device.recompose_parts",
    "main.ist_core.tools.device.recompose_submit_tool",
    "main.ist_core.tools.device.lang_query_tool",
    "main.kms.spec_index",
    # 提交主路径上的依赖：回绑、重组协议、密封输出、引擎共享层（project_root 等）
    "main.ist_core.compile_engine.rebind_binder",
    "main.ist_core.compile_engine.recompose_protocol",
    "main.ist_core.tools.device._sealed_output",
    "main.ist_core.compile_engine._shared",
    # 多个候选规格书时引擎给的参考切片（零签发权）
    "main.ist_core.compile_engine.spec_references",
    # 命令树代际与手册定位：load_vendor_stdlib / lang_query 的延迟 import，缺了它们
    # 命令树在客户端恒为"不可用"（try/except 吞掉 ModuleNotFoundError）
    "main.sync.command_tree_sync",
    "main.kms.manual_locator",
)
PREFIX = "cex_core.engine"
# InfoTest 仓根下的顶层包 → 抽取后的包名。scripts.* 只会以延迟 import 出现（生成器），
# 改名后在客户端里明确地找不到，而不是碰巧解析到别的名叫 scripts 的包
PACKAGES = {"main": PREFIX, "scripts": PREFIX + ".scripts"}


def _renamed(name: str) -> str | None:
    for src, dst in PACKAGES.items():
        if name == src or name.startswith(src + "."):
            return dst + name[len(src):]
    return None
OUT_DIR = Path("cex_core") / "engine"
ROOT_HELPER = "_cex_data_path"

ROOT_MODULE = '''"""数据根：抽取来的引擎按 InfoTest 仓根的布局读数据（knowledge/…、runtime/…）。

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
'''

PACKAGE_INIT = '"""生成的包（tools/extract_engine.py）；不在这里手改。"""\n'

ENGINE_INIT = '''"""从 InfoTest 抽取的编译判据引擎（tools/extract_engine.py 生成，不在这里手改）。

模块树与 InfoTest ``main`` 包一一对应：``cex_core.engine.case_compiler.apv_lang`` 就是
``main/case_compiler/apv_lang.py``。数据根见 ``_root``；抽取范围、每个文件的源哈希与
闭包边界见 MANIFEST.json。
"""

from cex_core.engine._root import DATA_ROOT_ENV, data_root, data_root_configured

__all__ = ["DATA_ROOT_ENV", "data_root", "data_root_configured"]
'''


class ExtractError(RuntimeError):
    pass


def _module_path(root: Path, module: str) -> Path | None:
    base = root / Path(*module.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _imports(tree: ast.Module, module: str, root: Path) -> tuple[set[str], list[dict]]:
    """(顶层 import 的 main.* 模块, 函数内 import 的站点)。"""
    top: set[str] = set()
    lazy: list[dict] = []

    def targets(node: ast.AST) -> list[str]:
        if isinstance(node, ast.ImportFrom):
            if node.level:
                raise ExtractError(f"{module}: relative import is not supported")
            name = node.module or ""
            out = [name]
            out += [f"{name}.{a.name}" for a in node.names if _module_path(root, f"{name}.{a.name}")]
            return out
        return [a.name for a in node.names]  # type: ignore[attr-defined]

    def walk(node: ast.AST, func: str | None, guarded: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                for name in targets(child):
                    if _renamed(name) is None or not _module_path(root, name):
                        continue
                    if func is None:
                        if not name.startswith("main"):
                            raise ExtractError(f"{module}: top-level import of {name}")
                        top.add(name)
                    else:
                        lazy.append({"module": module, "function": func, "target": name,
                                     "guarded": guarded})
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, child.name if func is None else func, guarded)
            elif isinstance(child, ast.Try):
                catches = any(h.type is None or "Error" in ast.unparse(h.type)
                              or "Exception" in ast.unparse(h.type) for h in child.handlers)
                for part in child.body:
                    walk(ast.Module(body=[part], type_ignores=[]), func, guarded or catches)
                for part in (*child.handlers, *child.orelse, *child.finalbody):
                    walk(part if not isinstance(part, ast.stmt) else
                         ast.Module(body=[part], type_ignores=[]), func, guarded)
            else:
                walk(child, func, guarded)

    walk(tree, None, False)
    return top, lazy


def closure(root: Path) -> tuple[list[str], list[dict]]:
    seen: dict[str, ast.Module] = {}
    stack = list(SEEDS)
    lazy_sites: list[dict] = []
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        path = _module_path(root, mod)
        if path is None:
            raise ExtractError(f"{mod} not found under {root}")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen[mod] = tree
        top, lazy = _imports(tree, mod, root)
        stack.extend(sorted(top))
        lazy_sites.extend(lazy)
    return sorted(seen), lazy_sites


# ── AST transforms ─────────────────────────────────────────────────────────


def _is_doc(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str))


_BATCH = re.compile(r"\b(?:internala|internalb)[A-Za-z0-9_]*", re.IGNORECASE)
_SIX = re.compile(r"(?<![\d.])\d{6}(?![\d.])")


def _scrub_doc(text: str) -> str:
    def case(match: re.Match) -> str:
        n = int(match.group(0))
        # 整数常量（整万、2 的幂）不是用例号
        return match.group(0) if n % 1000 == 0 or n & (n - 1) == 0 else "<case>"
    return _SIX.sub(case, _BATCH.sub("<batch>", text))


def _makes_tools(tree: ast.Module) -> bool:
    """``@tool`` / ``@tool(...)`` 装饰器或 ``X.from_function(...)``：docstring 会成为工具说明。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "from_function":
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                target = deco.func if isinstance(deco, ast.Call) else deco
                if isinstance(target, ast.Name) and target.id == "tool":
                    return True
    return False


def _sanitize_docstrings(tree: ast.Module, rel_file: str) -> int:
    changed = 0
    tools = _makes_tools(tree)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body or not _is_doc(node.body[0]):
            continue
        const = node.body[0].value
        scrubbed = _scrub_doc(const.value)
        if scrubbed != const.value:
            if tools:
                raise ExtractError(f"{rel_file}: a docstring needs scrubbing in a module that "
                                   "builds tools from docstrings; fix it in InfoTest")
            const.value = scrubbed
            changed += 1
    return changed


def _file_anchor(node: ast.AST) -> bool:
    """``Path(__file__)`` 或 ``Path(__file__).resolve()``。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("resolve", "absolute") and not node.args:
        node = node.func.value
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "Path" and len(node.args) == 1
            and isinstance(node.args[0], ast.Name) and node.args[0].id == "__file__")


class _Rewrite(ast.NodeTransformer):
    def __init__(self, rel_file: str) -> None:
        self.rel_dirs = Path(rel_file).parents  # parents[0] 是文件所在目录
        self.rewrites: list[str] = []

    def _root_call(self, depth: int) -> ast.Call:
        rel = self.rel_dirs[depth].as_posix()
        rel = "" if rel == "." else rel
        self.rewrites.append(rel or "<root>")
        return ast.Call(func=ast.Name(id=ROOT_HELPER, ctx=ast.Load()),
                        args=[ast.Constant(value=rel)], keywords=[])

    def visit_Subscript(self, node: ast.Subscript):
        if (isinstance(node.value, ast.Attribute) and node.value.attr == "parents"
                and _file_anchor(node.value.value) and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, int)):
            return ast.copy_location(self._root_call(node.slice.value), node)
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr == "parent":
            depth, inner = 0, node.value
            while isinstance(inner, ast.Attribute) and inner.attr == "parent":
                depth, inner = depth + 1, inner.value
            if _file_anchor(inner):
                return ast.copy_location(self._root_call(depth), node)
        return self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        renamed = _renamed(node.module or "")
        if renamed is not None:
            node.module = renamed
        return node

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if _renamed(alias.name) is not None:
                raise ExtractError(f"`import {alias.name}` is not supported; use from-imports")
        return node


def transform(source: str, rel_file: str) -> tuple[str, list[str]]:
    tree = ast.parse(source)
    _sanitize_docstrings(tree, rel_file)
    rewriter = _Rewrite(rel_file)
    tree = rewriter.visit(tree)
    leftovers = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "__file__"]
    if leftovers:
        raise ExtractError(f"{rel_file}: unhandled __file__ use at line {leftovers[0].lineno}")
    if rewriter.rewrites:
        helper = ast.parse(f"from {PREFIX}._root import {ROOT_HELPER}").body[0]
        at = 1 if tree.body and _is_doc(tree.body[0]) else 0
        while at < len(tree.body) and isinstance(tree.body[at], ast.ImportFrom) \
                and tree.body[at].module == "__future__":
            at += 1
        tree.body.insert(at, helper)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n", rewriter.rewrites


# ── generation ────────────────────────────────────────────────────────────


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate(root: Path) -> tuple[dict[Path, str], dict]:
    modules, lazy_sites = closure(root)
    extracted = set(modules)
    files: dict[Path, str] = {}
    entries = []
    packages: set[tuple[str, ...]] = set()
    for mod in modules:
        src_path = _module_path(root, mod)
        rel = src_path.relative_to(root).as_posix()
        parts = mod.split(".")[1:]
        if src_path.name == "__init__.py":
            if parts:
                packages.add(tuple(parts))
            continue
        for i in range(1, len(parts)):
            packages.add(tuple(parts[:i]))
        source = src_path.read_text(encoding="utf-8")
        body, rewrites = transform(source, rel)
        header = (f"# 生成：tools/extract_engine.py ← InfoTest {rel}"
                  f"（sha256 {_sha(source)[:16]}）。不在这里手改。\n")
        out = OUT_DIR.joinpath(*parts).with_suffix(".py")
        try:
            compile(header + body, str(out), "exec")
        except SyntaxError as exc:
            raise ExtractError(f"{rel}: generated code does not compile: {exc}") from exc
        files[out] = header + body
        entries.append({"module": mod, "source": rel, "source_sha256": _sha(source),
                        "data_root_rewrites": sorted(set(rewrites))})
    for pkg in sorted(packages):
        files[OUT_DIR.joinpath(*pkg, "__init__.py")] = PACKAGE_INIT
    files[OUT_DIR / "__init__.py"] = ENGINE_INIT
    files[OUT_DIR / "_root.py"] = ROOT_MODULE
    generated = {".".join(["main", *pkg]) for pkg in packages} | {"main"}
    boundary = [site for site in lazy_sites
                if site["target"] not in extracted and site["target"] not in generated]
    manifest = {
        "schema": "cex.engine-extract/v1",
        "seeds": list(SEEDS),
        "modules": entries,
        "boundary": sorted(boundary, key=lambda s: (s["module"], s["function"], s["target"])),
        "boundary_targets": sorted({s["target"] for s in boundary}),
    }
    files[OUT_DIR / "MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return files, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--infotest-root", required=True)
    parser.add_argument("--out", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.infotest_root).resolve()
    out = Path(args.out).resolve()
    try:
        files, manifest = generate(root)
    except ExtractError as exc:
        print(f"extract failed: {exc}", file=sys.stderr)
        return 2
    existing = {p.relative_to(out) for p in (out / OUT_DIR).rglob("*")
                if p.is_file() and "__pycache__" not in p.parts} if (out / OUT_DIR).exists() else set()
    drift = sorted(str(p) for p in files if not (out / p).is_file()
                   or (out / p).read_text(encoding="utf-8") != files[p])
    stale = sorted(str(p) for p in existing - set(files))
    if args.check:
        for item in drift:
            print(f"drift: {item}")
        for item in stale:
            print(f"stale: {item}")
        return 1 if drift or stale else 0
    for rel, text in files.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for rel in stale:
        (out / rel).unlink()
    print(f"extracted {len(manifest['modules'])} modules; boundary targets "
          f"{len(manifest['boundary_targets'])}; wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
