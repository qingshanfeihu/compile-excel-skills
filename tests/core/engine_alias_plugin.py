"""pytest plugin for engine parity runs inside InfoTest's own test tree.

Loaded with ``-p engine_alias_plugin`` (this directory on PYTHONPATH). Every extracted
module ``main.X`` is replaced by ``cex_core.engine.X`` before any test imports it, so
InfoTest's tests exercise the extracted copy.

CEX_ALIAS_MODE:
- ``faithful`` — a lazy import the extracted code makes outside the extracted set
  (``cex_core.engine.Y``) resolves to InfoTest's own ``main.Y``: any outcome change is
  then a difference in the extracted code itself;
- ``standalone`` — those imports fail as they would in a client; outcome changes show
  how far the boundary reaches.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

SKILLS_ROOT = Path(os.environ["CEX_SKILLS_ROOT"]).resolve()
MODE = os.environ.get("CEX_ALIAS_MODE", "faithful")
if str(SKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLS_ROOT))

_MANIFEST = json.loads((SKILLS_ROOT / "cex_core/engine/MANIFEST.json").read_text(encoding="utf-8"))
EXTRACTED = [entry["module"] for entry in _MANIFEST["modules"]]
_PREFIXES = {"main": "cex_core.engine", "scripts": "cex_core.engine.scripts"}


def _engine_name(name: str) -> str:
    head, _, rest = name.partition(".")
    return _PREFIXES[head] + ("." + rest if rest else "")


def _infotest_name(engine_name: str) -> str | None:
    if engine_name == "cex_core.engine.scripts":
        return "scripts"
    if engine_name.startswith("cex_core.engine.scripts."):
        return "scripts." + engine_name[len("cex_core.engine.scripts."):]
    if engine_name.startswith("cex_core.engine."):
        return "main." + engine_name[len("cex_core.engine."):]
    return None


def _local_names() -> set[str]:
    """Engine names that exist in the extracted tree: the modules and their packages."""
    names = {"cex_core.engine", "cex_core.engine._root"}
    for name in EXTRACTED:
        parts = _engine_name(name).split(".")
        names.update(".".join(parts[:i]) for i in range(2, len(parts) + 1))
    return names


class _BackToInfoTest(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """faithful mode: an engine module that was not extracted is InfoTest's own module
    object (never a second copy loaded under the engine name)."""

    local = _local_names()

    def find_spec(self, name, path, target=None):
        if name in self.local or _infotest_name(name) is None:
            return None
        return importlib.util.spec_from_loader(name, self, is_package=False)

    def create_module(self, spec):
        module = importlib.import_module(_infotest_name(spec.name))
        self._spec = getattr(module, "__spec__", None)
        return module

    def exec_module(self, module):
        if getattr(self, "_spec", None) is not None:
            module.__spec__ = self._spec


def _install() -> None:
    os.environ.setdefault("CEX_ENGINE_DATA_ROOT", str(Path.cwd()))
    if MODE == "faithful":
        sys.meta_path.insert(0, _BackToInfoTest())
    for name in EXTRACTED:
        sys.modules[name] = importlib.import_module(_engine_name(name))
        module = sys.modules[name]
        if MODE == "faithful" and hasattr(module, "__path__"):
            # 抽了正文的包：没抽的子模块仍从 InfoTest 自己的包目录加载
            original = Path(os.environ["CEX_ENGINE_DATA_ROOT"]).joinpath(*name.split("."))
            if original.is_dir() and str(original) not in module.__path__:
                module.__path__.append(str(original))
    for name in EXTRACTED:
        parent, _, child = name.rpartition(".")
        if parent:
            owner = importlib.import_module(parent)
            # 包的 __init__ 可能把同名对象（如与子模块同名的工具函数）绑在这个属性上：不覆盖
            if isinstance(getattr(owner, child, None), (types.ModuleType, type(None))):
                setattr(owner, child, sys.modules[name])
    marker = os.environ.get("CEX_ALIAS_MARKER")
    if marker:
        # 证明别名真的生效：每个 main.X 指向的模块文件都在抽取树里
        Path(marker).write_text(json.dumps(
            {name: getattr(sys.modules[name], "__file__", "") for name in EXTRACTED}), encoding="utf-8")


_install()
