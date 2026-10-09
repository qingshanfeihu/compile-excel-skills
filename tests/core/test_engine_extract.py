"""cex_core/engine：从 InfoTest 抽取的判据引擎。

- 与同级 InfoTest 源重新抽取的结果一致（改判据先改 InfoTest，再跑 tools/extract_engine.py）；
- 不带内部实证记录（批次名、用例号、个人路径）：docstring、说明文字字面里换成占位；
- 数据根没设时读不到任何数据，照引擎自己的"不可达"路径失败关闭；也写不进任何地方（包目录里
  不会长出文件），没设数据根时就算过路径的模块由 modules_bound_while_unset() 报出来；
- 外置的身份表按 CEX_ENGINE_IDENTITIES 取，取不到时一读就报错；
- 对拍：InfoTest 自己的测试跑抽取副本，逐条结果与跑原模块一致（tools/engine_parity.py）。
  默认跑一小批；CEX_ENGINE_PARITY=full 跑全部相关测试文件（约 1 万条，十来分钟）。
"""

from __future__ import annotations

import ast
import importlib.util
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
         "--infotest-root", str(INFOTEST_ROOT), "--check", "--code-only"],
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
    # 人名缩写批次同 tools/extract_engine.py：名单来自环境（公开 CI 无名单则该项不查）
    handles = [h.strip() for h in os.environ.get("CEX_INTERNAL_HANDLES", "").split(",") if h.strip()]
    handle_alt = "|".join(handles)
    pattern = re.compile((handle_alt + "|" if handle_alt else "")
                         + r"RUN_20\d{2}|/U[s]ers/"
                         + r"|\b(?!999999999999999\b|990000000000000001\b)\d{12,20}\b",
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
    """faithful：闭包外的延迟 import 回落 InfoTest，逐条结果必须一致。默认小批再跑一轮客户端模式
    （standalone，闭包外的 import 照客户端的样子失败）：结果变了的只许是撞上 MANIFEST 登记的
    边界模块（客户端本来就走不到那里）。全量时客户端模式不断言：被 try/except 包住的边界 import
    会悄悄换分支，这类差异在客户端预期存在（docs/engine-parity.md §7）。"""
    full = os.environ.get("CEX_ENGINE_PARITY") == "full"
    tool = [sys.executable, str(REPO_ROOT / "tools" / "engine_parity.py"),
            "--infotest-root", str(INFOTEST_ROOT), "--python", str(INFOTEST_PYTHON)]
    if full:
        listing = subprocess.run(
            ["git", "grep", "-lE", "|".join(e["module"].rsplit(".", 1)[-1]
                                            for e in _manifest()["modules"]), "--", "tests/"],
            cwd=INFOTEST_ROOT, capture_output=True, text=True, check=True).stdout.split()
        tests = sorted(p for p in listing if Path(p).name.startswith("test_") and p.endswith(".py"))
        (tmp_path / "tests.txt").write_text("\n".join(tests), encoding="utf-8")
        selection = ["--tests-file", str(tmp_path / "tests.txt")]
    else:
        selection = PARITY_SUBSET
    baseline = tmp_path / "baseline.xml"
    proc = subprocess.run(tool + ["--mode", "faithful", "--report", str(tmp_path / "report.json"),
                                  "--save-baseline", str(baseline)] + selection,
                          capture_output=True, text=True, timeout=3600 if full else 600,
                          check=False)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["not_aliased"] == [] and report["aliased_modules"] == len(_manifest()["modules"])
    assert report["tests"] > 100
    assert report["diffs"] == [], proc.stdout
    if full:
        return
    client = subprocess.run(tool + ["--mode", "standalone", "--baseline", str(baseline),
                                    "--report", str(tmp_path / "client.json")] + selection,
                            capture_output=True, text=True, timeout=600, check=False)
    report = json.loads((tmp_path / "client.json").read_text(encoding="utf-8"))
    assert report["not_aliased"] == [] and report["tests"] > 100
    assert report["diffs"] == [], client.stdout
    boundary = set(_manifest()["boundary_targets"])
    assert all(any(t == d["boundary"] or t.startswith(d["boundary"] + ".") for t in boundary)
               for d in report["boundary_diffs"])


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


def _run(script: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full = {k: v for k, v in os.environ.items()
            if k not in ("CEX_ENGINE_DATA_ROOT", "CEX_ENGINE_IDENTITIES")}
    full.update(env or {})
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=180, env=full, check=False)


def test_an_unset_data_root_cannot_be_written_and_the_bound_modules_are_reported():
    """数据根没设：写盘在操作系统那一层失败，包目录里不长出文件；导入时就按它算过路径的模块
    由 modules_bound_while_unset() 报出来（客户端据此拒绝在同一进程里接着用引擎）。"""
    script = f'''
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
package = Path({str(REPO_ROOT / "cex_core")!r})
def listing():
    return {{p for p in package.rglob("*") if "__pycache__" not in p.parts}}
before = listing()
from cex_core.engine import data_root, modules_bound_while_unset
assert modules_bound_while_unset() == (), modules_bound_while_unset()
from cex_core.engine import knowledge_paths
from cex_core.engine.case_compiler import package_advisories
bound = modules_bound_while_unset()
assert {{"cex_core.engine.knowledge_paths",
         "cex_core.engine.case_compiler.package_advisories"}} <= set(bound), bound
assert package not in data_root().parents and not data_root().exists()
attempts = (knowledge_paths.user_output_dir,
            lambda: package_advisories.write_json_atomic(
                package_advisories.PACKAGE_ADVISORIES_PATH, {{"x": 1}}))
for attempt in attempts:
    try:
        attempt()
    except OSError:
        continue
    raise SystemExit("a write under the unset data root succeeded")
assert listing() == before, sorted(map(str, listing() - before))[:5]
print("closed")
'''
    proc = _run(script)
    assert proc.returncode == 0 and proc.stdout.strip() == "closed", proc.stderr[-2000:]


def test_modules_imported_after_the_root_is_set_are_not_reported(tmp_path):
    script = f'''
import os, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_core.engine import data_root_configured, modules_bound_while_unset
assert data_root_configured()
from cex_core.engine import knowledge_paths
assert modules_bound_while_unset() == ()
print(knowledge_paths.PROJECT_ROOT)
'''
    proc = _run(script, {"CEX_ENGINE_DATA_ROOT": str(tmp_path)})
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert Path(proc.stdout.strip()) == tmp_path.resolve()


_IMPORT_ALL = f'''
import builtins, importlib, json, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
_real = builtins.__import__
def _guard(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name.split(".")[0] in ("main", "scripts"):
        raise ImportError("InfoTest imported: " + name)
    return _real(name, globals, locals, fromlist, level)
builtins.__import__ = _guard
failed = {{}}
for entry in json.load(open({str(ENGINE / "MANIFEST.json")!r}, encoding="utf-8"))["modules"]:
    try:
        importlib.import_module(entry["engine_module"])
    except Exception as exc:
        failed[entry["engine_module"]] = type(exc).__name__
print(json.dumps(failed, sort_keys=True))
'''


def test_an_unset_root_breaks_no_more_imports_than_a_missing_data_directory(tmp_path):
    """/dev/null 底下读文件报的是 NotADirectoryError：导入时就读数据的模块，失败面必须与
    "数据根指向一个不存在的目录"完全一样（同一批模块、同一种异常），不因为换了哨兵多坏一个。"""
    unset = _run(_IMPORT_ALL)
    missing = _run(_IMPORT_ALL, {"CEX_ENGINE_DATA_ROOT": str(tmp_path / "missing")})
    assert unset.returncode == 0 and missing.returncode == 0, unset.stderr[-1500:] + missing.stderr
    assert json.loads(unset.stdout) == json.loads(missing.stdout)
    assert not (tmp_path / "missing").exists()


_IDENTITY_KEY = "main/case_compiler/package_advisories.py:DENIED_668_AUTOIDS"


def test_identities_come_from_the_configured_table(tmp_path):
    table = tmp_path / "identities.json"
    table.write_text(json.dumps({_IDENTITY_KEY: ["111111111111111111"]}), encoding="utf-8")
    script = f'''
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_core.engine.case_compiler import package_advisories as pa
assert pa.DENIED_668_AUTOIDS == frozenset({{"111111111111111111"}}), sorted(pa.DENIED_668_AUTOIDS)
assert pa.package_rejection(autoid="111111111111111111", projection={{}}).startswith(
    pa.PACKAGE_REFERENCE_ERROR)
assert pa.package_rejection(autoid="222222222222222222", projection={{}}) == ""
print("ok")
'''
    proc = _run(script, {"CEX_ENGINE_IDENTITIES": str(table)})
    assert proc.returncode == 0 and proc.stdout.strip() == "ok", proc.stderr[-1500:]


@pytest.mark.parametrize("content", [None, "{not json", json.dumps({"other": ["1"]}),
                                     json.dumps({_IDENTITY_KEY: "111"})])
def test_an_unusable_identity_table_fails_closed_on_use_not_on_import(tmp_path, content):
    """表不在、读不成、缺这一项、形状不对：导入照常，一用就报 IdentityListUnavailable，
    消息点名该设的环境变量；package_rejection 不会把"查不了"当成"没封禁"。"""
    table = tmp_path / "identities.json"
    if content is not None:
        table.write_text(content, encoding="utf-8")
    script = f'''
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_core.engine._root import IDENTITIES_ENV, IdentityListUnavailable
from cex_core.engine.case_compiler import package_advisories as pa
for probe in (lambda: "1" in pa.DENIED_668_AUTOIDS,
              lambda: pa.package_rejection(autoid="1", projection={{}})):
    try:
        probe()
    except IdentityListUnavailable as exc:
        assert IDENTITIES_ENV in str(exc), exc
        continue
    raise SystemExit("an unusable identity table answered")
print("closed")
'''
    proc = _run(script, {"CEX_ENGINE_IDENTITIES": str(table)})
    assert proc.returncode == 0 and proc.stdout.strip() == "closed", proc.stderr[-1500:]


def _extractor():
    spec = importlib.util.spec_from_file_location("cex_extract_engine_under_test",
                                                  REPO_ROOT / "tools" / "extract_engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extraction_scrubs_records_in_prose_literals_and_lab_addresses_in_docstrings():
    extractor = _extractor()
    source = '''
def _subnet(cidr):
    """`172.16.33.215/24` → `172.16.33.0/24`；跳板机 10.4.127.103。"""
    return cidr

MESSAGE = "check_point has G/H/I all empty (044605 evidence: one on-device round wasted)"
PINNED = "46aa14dfffbe767ec486dc6b186d582458d666de8a8f6aec2294f920077a45f9"
TFTP = "certificates come from TFTP 172.16.35.215 unless the name ends in .pem"
'''
    body, _rewrites, _ids = extractor.transform(source, "main/x.py")
    tree = ast.parse(body)
    values = {node.targets[0].id: node.value.value for node in tree.body
              if isinstance(node, ast.Assign)}
    assert "<case> evidence" in values["MESSAGE"] and "044605" not in body
    assert values["PINNED"] == "46aa14dfffbe767ec486dc6b186d582458d666de8a8f6aec2294f920077a45f9"
    # 字面里的地址是床事实，不在抽取时改（留给泄漏守门逐条放行）
    assert "172.16.35.215" in values["TFTP"]
    doc = ast.get_docstring(tree.body[0])
    assert "198.18.33.215/24" in doc and "198.19.127.103" in doc and "172.16" not in doc


def test_extraction_refuses_a_run_record_in_a_short_literal(monkeypatch):
    monkeypatch.setenv("CEX_INTERNAL_HANDLES", "internala")
    extractor = _extractor()
    with pytest.raises(extractor.ExtractError, match="short string literal"):
        extractor.transform('BATCH = "internala_final1"\n', "main/x.py")
    with pytest.raises(extractor.ExtractError, match="short string literal"):
        extractor.transform('KNOWN = {"044605": 1}\n', "main/x.py")
