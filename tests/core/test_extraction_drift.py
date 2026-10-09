"""仓内逐字抽取的判据代码必须与同级 InfoTest 源重新抽取的结果一致；InfoTest 改了判据就在这里红。

另守两件事：InfoTest 检出在"本仓在 circle/ 之类中间目录里"的布局下也找得到；设了
CEX_REQUIRE_INFOTEST=1 时，找不到 InfoTest 不再静默跳过，而是失败。
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from conftest import INFOTEST_ROOT, REPO_ROOT, _sibling_checkout


@pytest.mark.skipif(not (INFOTEST_ROOT / "main").is_dir(),
                    reason=f"找不到 InfoTest 检出 {INFOTEST_ROOT}（设 INFOTEST_ROOT）")
def test_extracted_code_matches_infotest_source():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "sync_from_infotest.py"),
         "--infotest-root", str(INFOTEST_ROOT), "--check", "--code-only"],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, "运行 tools/sync_from_infotest.py 重新抽取：\n" + proc.stdout


def test_infotest_checkout_is_found_beside_the_repo_or_one_level_up(tmp_path, monkeypatch):
    monkeypatch.delenv("INFOTEST_ROOT", raising=False)
    repo = tmp_path / "work" / "circle" / "compile-excel-skills"
    repo.mkdir(parents=True)
    far = tmp_path / "work" / "InfoTest_Engine"
    (far / "main").mkdir(parents=True)
    assert _sibling_checkout("INFOTEST_ROOT", "InfoTest_Engine", "main", repo_root=repo) == far
    near = tmp_path / "work" / "circle" / "InfoTest_Engine"
    (near / "main").mkdir(parents=True)
    assert _sibling_checkout("INFOTEST_ROOT", "InfoTest_Engine", "main", repo_root=repo) == near
    monkeypatch.setenv("INFOTEST_ROOT", str(tmp_path / "elsewhere"))
    assert _sibling_checkout("INFOTEST_ROOT", "InfoTest_Engine", "main",
                             repo_root=repo) == (tmp_path / "elsewhere").resolve()


def test_require_infotest_turns_the_missing_checkout_skip_into_a_failure(tmp_path):
    target = "tests/core/test_extraction_drift.py::test_extracted_code_matches_infotest_source"
    env = {**os.environ, "INFOTEST_ROOT": str(tmp_path / "no-infotest-here")}
    env.pop("CEX_REQUIRE_INFOTEST", None)

    def run(extra: dict[str, str]) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                               target], cwd=REPO_ROOT, env={**env, **extra},
                              capture_output=True, text=True, timeout=120, check=False)

    relaxed = run({})
    assert relaxed.returncode == 0 and "1 skipped" in relaxed.stdout, relaxed.stdout[-800:]
    strict = run({"CEX_REQUIRE_INFOTEST": "1"})
    # skipif 在 setup 阶段判定，改判后 pytest 记作 setup 错误：同样是红
    assert strict.returncode != 0 and ("1 error" in strict.stdout or "1 failed" in strict.stdout), \
        strict.stdout[-800:]
    assert "CEX_REQUIRE_INFOTEST is set" in strict.stdout and "skipped" not in strict.stdout
