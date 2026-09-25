"""cex_core/engine：从 InfoTest 抽取的判据引擎。

- 与同级 InfoTest 源重新抽取的结果一致（改判据先改 InfoTest，再跑 tools/extract_engine.py）；
- 不带内部实证记录（批次名、用例号、个人路径）；
- 数据根没设时读不到任何数据，照引擎自己的"不可达"路径失败关闭；
- 对拍：InfoTest 自己的测试跑抽取副本，逐条结果与跑原模块一致（tools/engine_parity.py）。
  默认跑一小批；CEX_ENGINE_PARITY=full 跑全部相关测试文件（约 1 万条，十来分钟）。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import INFOTEST_ROOT, REPO_ROOT

ENGINE = REPO_ROOT / "cex_core" / "engine"
HAS_INFOTEST = (INFOTEST_ROOT / "main" / "case_compiler" / "apv_lang.py").is_file()
INFOTEST_PYTHON = Path(os.environ.get("INFOTEST_PYTHON")
                       or Path.home() / ".venvs" / "infotest-engine" / "bin" / "python")
PARITY_SUBSET = [
    "tests/case_compiler/test_apv_lang.py",
    "tests/case_compiler/test_step_graph.py",
    "tests/case_compiler/test_observe_ops.py",
    "tests/case_compiler/test_step_structure.py",
    "tests/case_compiler/test_mechanical_case_gate.py",
    "tests/common/test_schema_identity.py",
    "tests/ist_core/tools/test_structural_gate_lesson_closure.py",
]


def _manifest() -> dict:
    return json.loads((ENGINE / "MANIFEST.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(not HAS_INFOTEST, reason=f"找不到 InfoTest 检出 {INFOTEST_ROOT}（设 INFOTEST_ROOT）")
def test_engine_matches_a_fresh_extraction():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "extract_engine.py"),
         "--infotest-root", str(INFOTEST_ROOT), "--check"],
        capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, "运行 tools/extract_engine.py 重新抽取：\n" + proc.stdout + proc.stderr


def test_manifest_lists_every_generated_module_and_boundary():
    manifest = _manifest()
    modules = {entry["module"] for entry in manifest["modules"]}
    assert "main.case_compiler.apv_lang" in modules and len(modules) >= 20
    for entry in manifest["modules"]:
        rel = entry["engine_module"].split(".")[2:]
        target = (ENGINE.joinpath(*rel, "__init__.py") if entry["source"].endswith("/__init__.py")
                  else ENGINE.joinpath(*rel).with_suffix(".py"))
        assert target.is_file(), entry["module"]
    assert not modules & set(manifest["boundary_targets"])
    assert all(site["target"] in manifest["boundary_targets"] for site in manifest["boundary"])


def test_generated_code_carries_no_internal_run_records():
    # /U[s]ers/：字符类写法，免得本文件自己被可移植性守门当成写死的个人路径
    # 990000000000000001：环境收敛生成能力样例卷时用的合成案号，不是生产数据
    pattern = re.compile(r"internala|internalb|RUN_20\d{2}|/U[s]ers/"
                         r"|\b(?!999999999999999\b|990000000000000001\b)\d{12,20}\b",
                         re.IGNORECASE)
    hits = []
    for path in ENGINE.rglob("*.py"):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{no}: {line.strip()[:80]}")
    assert hits == []


def test_without_a_data_root_nothing_is_read(tmp_path):
    """数据根没设：按 InfoTest 自己的"数据不可达"路径报错，不去读别处。"""
    script = f'''
import os, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
os.environ.pop("CEX_ENGINE_DATA_ROOT", None)
from cex_core.engine import data_root, data_root_configured
from cex_core.engine.case_compiler import apv_lang
assert not data_root_configured() and not data_root().exists()
try:
    apv_lang.language_document_catalog("x")
except apv_lang.QueryUnavailable:
    print("closed")
os.environ["CEX_ENGINE_DATA_ROOT"] = {str(tmp_path)!r}
assert data_root() == __import__("pathlib").Path({str(tmp_path)!r}).resolve()
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0 and proc.stdout.strip() == "closed", proc.stderr[-1500:]


@pytest.mark.skipif(not HAS_INFOTEST, reason=f"找不到 InfoTest 检出 {INFOTEST_ROOT}（设 INFOTEST_ROOT）")
def test_every_engine_module_imports_without_infotest_given_a_data_root(tmp_path):
    """数据根里只放 InfoTest 入库的那几份 compile_ref（输入全在库内的数据），屏蔽 InfoTest
    包：全部模块能导入，说明顶层闭包是全的、不靠 InfoTest 本体。"""
    tracked = subprocess.run(["git", "ls-files", "knowledge/data/compile_ref"], cwd=INFOTEST_ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    data = tmp_path / "data"
    for rel in tracked:
        (data / rel).parent.mkdir(parents=True, exist_ok=True)
        (data / rel).write_bytes((INFOTEST_ROOT / rel).read_bytes())
    script = f'''
import builtins, importlib, json, os, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
os.environ["CEX_ENGINE_DATA_ROOT"] = {str(data)!r}
_real = builtins.__import__
def _guard(name, globals=None, locals=None, fromlist=(), level=0):
    # 只拦绝对导入：pydantic 里的 `from .main import BaseModel` 是它自己的子模块
    if level == 0 and name.split(".")[0] in ("main", "scripts"):
        raise ImportError("InfoTest imported: " + name)
    return _real(name, globals, locals, fromlist, level)
builtins.__import__ = _guard
manifest = json.load(open({str(ENGINE / "MANIFEST.json")!r}, encoding="utf-8"))
for entry in manifest["modules"]:
    importlib.import_module(entry["engine_module"])
print(len(manifest["modules"]))
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert int(proc.stdout.strip()) == len(_manifest()["modules"])


@pytest.mark.skipif(not HAS_INFOTEST or not INFOTEST_PYTHON.is_file(),
                    reason="对拍需要 InfoTest 检出和它的 venv（INFOTEST_ROOT / INFOTEST_PYTHON）")
def test_infotest_tests_give_the_same_results_on_the_extracted_engine(tmp_path):
    full = os.environ.get("CEX_ENGINE_PARITY") == "full"
    cmd = [sys.executable, str(REPO_ROOT / "tools" / "engine_parity.py"),
           "--infotest-root", str(INFOTEST_ROOT), "--python", str(INFOTEST_PYTHON),
           "--mode", "faithful", "--report", str(tmp_path / "report.json")]
    if full:
        listing = subprocess.run(
            ["git", "grep", "-lE", "|".join(e["module"].rsplit(".", 1)[-1]
                                            for e in _manifest()["modules"]), "--", "tests/"],
            cwd=INFOTEST_ROOT, capture_output=True, text=True, check=True).stdout.split()
        tests = sorted(p for p in listing if Path(p).name.startswith("test_") and p.endswith(".py"))
        (tmp_path / "tests.txt").write_text("\n".join(tests), encoding="utf-8")
        cmd += ["--tests-file", str(tmp_path / "tests.txt")]
    else:
        cmd += PARITY_SUBSET
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600 if full else 600)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["not_aliased"] == [] and report["aliased_modules"] == len(_manifest()["modules"])
    assert report["tests"] > 100
    assert report["diffs"] == [], proc.stdout


def test_externalized_identities_are_out_of_the_code_and_fail_closed_without_the_file():
    """生产身份字面不进生成代码：值在不入库的 _identities.json，缺它时一读就报错（不当成空集）。"""
    manifest = _manifest()
    tracked = subprocess.run(["git", "ls-files", "cex_core/engine"], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    assert "cex_core/engine/_identities.json" not in tracked
    script = f'''
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_core.engine._root import IdentityListUnavailable, _Unavailable
gone = _Unavailable("x")
for probe in (lambda: "a" in gone, lambda: sorted(gone), lambda: gone.intersection({{"a"}}),
              lambda: bool(gone), lambda: len(gone)):
    try:
        probe()
    except IdentityListUnavailable:
        continue
    raise SystemExit("an unavailable identity list answered instead of failing")
print("closed")
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0 and proc.stdout.strip() == "closed", proc.stderr[-1500:]
    if HAS_INFOTEST and (ENGINE / "_identities.json").is_file():
        table = json.loads((ENGINE / "_identities.json").read_text(encoding="utf-8"))
        assert sorted(table) == manifest["externalized"]
        for key, values in table.items():
            rel, name = key.rsplit(":", 1)
            source = (INFOTEST_ROOT / rel).read_text(encoding="utf-8")
            assert all(value in source for value in values), key
            assert name in source
