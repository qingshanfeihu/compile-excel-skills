"""仓库边界守门：compile-excel 的代码不读 InfoTest 的配置文件、不 import InfoTest 的环境加载模块。

上机已改走跳板机网关（run_device.py 不再借 InfoTest 引擎的客户端）。
"""

from __future__ import annotations

import json
import re
import subprocess

from conftest import REPO_ROOT

# tools/sync_from_infotest.py 以文本方式读取 InfoTest 源码做逐字抽取（字符串里必然出现 main.），
# 从不 import InfoTest；它是唯一例外。
ALLOWED = {"tools/sync_from_infotest.py"}
# 运行时拼装，避免守卫扫到自身
_PATTERNS = [
    re.compile(r"langchain" + r"_env"),
    re.compile(r"""["'/]\s*""" + "environ" + r"""ment["']"""),
    re.compile(r"from\s+main\.|import\s+main\."),
]
# 逐字放行的同名字面（文件 → 原文）：不是配置文件路径。只剥这一段原文再扫，同一文件里别处
# 再出现照样报。三处都不是配置文件路径：facts.py 是编写失败原因的枚举值（环境类原因）；
# excel_capability_receipts.py 读 Excel 晋升回执里的字段；environment_prepare.py 读模板选择结果的属性。
_ENV = "environ" + "ment"
_KNOWN_LITERALS = {
    "cex_core/engine/ist_core/compile_engine/facts.py": (f"AUTHORING_CAUSE_ENV = '{_ENV}'",),
    "cex_core/engine/case_compiler/excel_capability_receipts.py":
        (f"_object(receipt.get('{_ENV}'), label='{_ENV}')",),
    "cex_core/engine/ist_core/compile_engine/environment_prepare.py":
        (f"getattr(selection, '{_ENV}', None)",),
}


def _engine_env_loader_is_outside_the_closure() -> bool:
    """引擎代码里的 langchain_env 只能是闭包外的延迟 import（调到就 ModuleNotFoundError）。"""
    manifest = json.loads((REPO_ROOT / "cex_core" / "engine" / "MANIFEST.json")
                          .read_text(encoding="utf-8"))
    loader = "main.langchain" + "_env"
    return (loader in manifest["boundary_targets"]
            and loader not in {entry["module"] for entry in manifest["modules"]})


def test_code_does_not_touch_infotest_configuration():
    tracked = subprocess.run(["git", "ls-files", "*.py", "bin/*"], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    loader_outside = _engine_env_loader_is_outside_the_closure()
    offenders = []
    for rel in tracked:
        if rel in ALLOWED or rel.startswith("tests/"):
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        for literal in _KNOWN_LITERALS.get(rel, ()):
            assert text.count(literal) == 1, f"{rel}: 放行的原文变了，重核这条放行：{literal}"
            text = text.replace(literal, "")
        for pattern in _PATTERNS:
            if pattern is _PATTERNS[0] and rel.startswith("cex_core/engine/") and loader_outside:
                continue
            if pattern.search(text):
                offenders.append(f"{rel}: {pattern.pattern}")
    assert offenders == []


def test_tool_specs_and_registry_agree():
    from cex_client import tools

    specs = tools.load_specs()
    assert [s["name"] for s in specs] == list(tools.TOOLS)
    for spec in specs:
        assert spec["input_schema"]["type"] == "object"
        assert spec["description"].isascii(), f"{spec['name']}: tool descriptions are LLM-facing English"


def test_everything_imports_and_runs_without_infotest(tmp_path):
    """在屏蔽 InfoTest `main` 包的子进程里导入全部模块、跑一遍脱敏与解析：
    抽取来的代码里若残留函数内的延迟导入，这里会炸（对拍测试因为 InfoTest 在 sys.path 上看不出来）。

    cex_core.engine 除外：它的模块像在 InfoTest 里一样导入时就读数据，没有数据根导入即失败；
    带数据根的独立导入在 tests/core/test_engine_extract.py 里查。"""
    import sys

    script = tmp_path / "probe.py"
    script.write_text(f'''
import builtins, importlib, pkgutil, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
_real = builtins.__import__
def _guard(name, *a, **k):
    if name == "main" or name.startswith("main."):
        raise ImportError("InfoTest imported: " + name)
    return _real(name, *a, **k)
builtins.__import__ = _guard
import cex_core, cex_client
for pkg in (cex_core, cex_client):
    for mod in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + ".",
                                     onerror=lambda name: None):
        if mod.name.startswith("cex_core.engine."):
            continue
        importlib.import_module(mod.name)
from cex_core.defects.scrub import scrub_declaration_text, contains_prohibited_declaration
assert scrub_declaration_text("password=hunter2 x") != "password=hunter2 x"
contains_prohibited_declaration("token: abc")
print("ok")
''', encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0 and proc.stdout.strip() == "ok", proc.stderr[-2000:]
