#!/usr/bin/env python3
"""从 InfoTest 源抽取编译判据引擎到 cex_core/engine（改判据先改 InfoTest，再跑本脚本）。

  python3 tools/extract_engine.py --infotest-root ../InfoTest_Engine [--out .] [--check]

抽取对象是 SEEDS 的顶层 import 闭包（函数内的延迟 import 不跟：它们多数指向编排层，
跟进去就是整个引擎）。SEEDS 里有 InfoTest 的 scripts/ 生成器（服务端生成链用），它们顶层
import 的 scripts.* 也一并进闭包。每个模块按 AST 机械变换后重新生成，逻辑一字不改：

- ``main.*`` 导入改成 ``cex_core.engine.*``，``scripts.*`` 改成 ``cex_core.engine.scripts.*``；
- ``Path(__file__)…parents[k]`` / ``.parent`` 这类"按源码位置找仓根"的表达式，改成
  ``_cex_data_path("<相对仓根的目录>")``：数据根由环境变量 CEX_ENGINE_DATA_ROOT 指定，
  布局与 InfoTest 仓根相同（knowledge/…、runtime/…）；
- 去掉注释（其中有批次名、用例号等内部实证记录；设计理由回 InfoTest 源看）。docstring
  保留——工具函数的 docstring 就是给模型的工具说明，langchain 还会解析它；docstring 里的
  批次名与六位用例号换成占位（_sanitize_docstrings），换到会被当工具说明的 docstring 上就
  报错，不许静默改提示词。

- 生产身份字面（真实用例号这类）不进生成代码：EXTERNALIZED 里点名的模块级常量原样搬进抽取树
  旁的 _identities.json（不入库，安装器也不拷给客户端），代码改成按名字取。文件在时取到的是
  同一个 frozenset；不在时一读就报错（失败关闭），不当成空集。

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
    # E11：服务端生成链。批入口里的两段本地编排（环境收敛模块顶层只依赖两个已抽取模块，
    # 连上游的函数都在函数体里，留在边界外不调）与各投影生成器
    "main.ist_core.compile_engine.environment_prepare",
    "main.ist_core.compile_engine.framework_projections",
    "scripts.gen_blocks_schema",
    "scripts.gen_capability_atlas",
    "scripts.gen_capability_usage_index",
    "scripts.gen_command_teardown_atlas",
    "scripts.gen_confirmation_prompt_projection",
    "scripts.gen_criterion_rules",
    "scripts.gen_device_behavior_examples",
    "scripts.gen_device_characteristics",
    "scripts.gen_method_reference",
    "scripts.gen_package_advisories",
    "scripts.gen_rule_registry",
    "scripts.gen_vendor_pacing_usage",
    "scripts.maintenance.build_vendor_stdlib",
    "scripts.maintenance.build_package_advisories",
    "scripts.maintenance.build_language_docs_index",
)
PREFIX = "cex_core.engine"
# InfoTest 仓根下的顶层包 → 抽取后的包名。scripts.* 挪到 cex_core.engine.scripts 下：不在闭包里的
# 那些在客户端里明确地找不到，而不是碰巧解析到别的名叫 scripts 的包
PACKAGES = {"main": PREFIX, "scripts": PREFIX + ".scripts"}


def _renamed(name: str) -> str | None:
    for src, dst in PACKAGES.items():
        if name == src or name.startswith(src + "."):
            return dst + name[len(src):]
    return None
OUT_DIR = Path("cex_core") / "engine"
ROOT_HELPER = "_cex_data_path"
IDENTITY_HELPER = "_cex_identity_set"
IDENTITY_FILE = "_identities.json"
# 源文件 → 要外置的模块级常量（值必须是 frozenset({字面}) 形状）
EXTERNALIZED = {"main/case_compiler/package_advisories.py": ("DENIED_668_AUTOIDS",)}

ROOT_MODULE = '''"""数据根：抽取来的引擎按 InfoTest 仓根的布局读数据（knowledge/…、runtime/…）。

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


def _externalize(tree: ast.Module, rel_file: str) -> dict[str, list[str]]:
    """EXTERNALIZED 点名的 `NAME = frozenset({字面})` 改成按名字取，值交给调用方另存。"""
    wanted = EXTERNALIZED.get(rel_file, ())
    found: dict[str, list[str]] = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in wanted):
            continue
        name = node.targets[0].id
        value = node.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id == "frozenset" and len(value.args) == 1 and not value.keywords):
            raise ExtractError(f"{rel_file}: {name} is not frozenset(<literal>)")
        items = ast.literal_eval(value.args[0])
        if not all(isinstance(item, str) for item in items):
            raise ExtractError(f"{rel_file}: {name} holds non-string items")
        key = f"{rel_file}:{name}"
        found[key] = sorted(items)
        node.value = ast.parse(f"{IDENTITY_HELPER}({key!r})").body[0].value  # type: ignore[attr-defined]
    missing = sorted(set(wanted) - {key.rsplit(":", 1)[1] for key in found})
    if missing:
        raise ExtractError(f"{rel_file}: externalized constants not found: {missing}")
    return found


def transform(source: str, rel_file: str) -> tuple[str, list[str], dict[str, list[str]]]:
    tree = ast.parse(source)
    _sanitize_docstrings(tree, rel_file)
    identities = _externalize(tree, rel_file)
    rewriter = _Rewrite(rel_file)
    tree = rewriter.visit(tree)
    leftovers = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "__file__"]
    if leftovers:
        raise ExtractError(f"{rel_file}: unhandled __file__ use at line {leftovers[0].lineno}")
    helpers = ([ROOT_HELPER] if rewriter.rewrites else []) + ([IDENTITY_HELPER] if identities else [])
    if helpers:
        helper = ast.parse(f"from {PREFIX}._root import {', '.join(helpers)}").body[0]
        at = 1 if tree.body and _is_doc(tree.body[0]) else 0
        while at < len(tree.body) and isinstance(tree.body[at], ast.ImportFrom) \
                and tree.body[at].module == "__future__":
            at += 1
        tree.body.insert(at, helper)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n", rewriter.rewrites, identities


# ── generation ────────────────────────────────────────────────────────────


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate(root: Path) -> tuple[dict[Path, str], dict]:
    modules, lazy_sites = closure(root)
    extracted = set(modules)
    files: dict[Path, str] = {}
    entries = []
    packages: set[tuple[str, ...]] = set()
    identities: dict[str, list[str]] = {}
    for mod in modules:
        src_path = _module_path(root, mod)
        rel = src_path.relative_to(root).as_posix()
        engine_module = _renamed(mod)
        assert engine_module is not None
        parts = engine_module.split(".")[len(PREFIX.split(".")):]
        if src_path.name == "__init__.py":
            if parts:
                packages.add(tuple(parts))
            continue
        for i in range(1, len(parts)):
            packages.add(tuple(parts[:i]))
        source = src_path.read_text(encoding="utf-8")
        body, rewrites, found = transform(source, rel)
        identities.update(found)
        header = (f"# 生成：tools/extract_engine.py ← InfoTest {rel}"
                  f"（sha256 {_sha(source)[:16]}）。不在这里手改。\n")
        out = OUT_DIR.joinpath(*parts).with_suffix(".py")
        try:
            compile(header + body, str(out), "exec")
        except SyntaxError as exc:
            raise ExtractError(f"{rel}: generated code does not compile: {exc}") from exc
        files[out] = header + body
        entries.append({"module": mod, "engine_module": engine_module, "source": rel,
                        "source_sha256": _sha(source),
                        "data_root_rewrites": sorted(set(rewrites))})
    for pkg in sorted(packages):
        files[OUT_DIR.joinpath(*pkg, "__init__.py")] = PACKAGE_INIT
    files[OUT_DIR / "__init__.py"] = ENGINE_INIT
    files[OUT_DIR / "_root.py"] = ROOT_MODULE
    # 生成出来的包（含只有 __init__ 的中间包）按 InfoTest 原名记，边界不把它们算作闭包外
    generated = {".".join(mod.split(".")[:i]) for mod in modules
                 for i in range(1, len(mod.split(".")))}
    boundary = [site for site in lazy_sites
                if site["target"] not in extracted and site["target"] not in generated]
    manifest = {
        "schema": "cex.engine-extract/v1",
        "seeds": list(SEEDS),
        "modules": entries,
        "boundary": sorted(boundary, key=lambda s: (s["module"], s["function"], s["target"])),
        "boundary_targets": sorted({s["target"] for s in boundary}),
        "externalized": sorted(identities),
    }
    if identities:
        files[OUT_DIR / IDENTITY_FILE] = json.dumps(identities, ensure_ascii=False,
                                                    indent=1, sort_keys=True) + "\n"
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
    identity_file = OUT_DIR / IDENTITY_FILE
    drift = sorted(str(p) for p in files
                   if not (p == identity_file and not (out / p).is_file())
                   and (not (out / p).is_file()
                        or (out / p).read_text(encoding="utf-8") != files[p]))
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
    for directory in sorted((p for p in (out / OUT_DIR).rglob("*") if p.is_dir()), reverse=True):
        if directory.name != "__pycache__" and not any(directory.iterdir()):
            directory.rmdir()
    print(f"extracted {len(manifest['modules'])} modules; boundary targets "
          f"{len(manifest['boundary_targets'])}; wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
