"""仓内逐字抽取的判据代码必须与同级 InfoTest 源重新抽取的结果一致；InfoTest 改了判据就在这里红。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import INFOTEST_ROOT, REPO_ROOT


@pytest.mark.skipif(not (INFOTEST_ROOT / "main").is_dir(),
                    reason=f"找不到 InfoTest 检出 {INFOTEST_ROOT}（设 INFOTEST_ROOT）")
def test_extracted_code_matches_infotest_source():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "sync_from_infotest.py"),
         "--infotest-root", str(INFOTEST_ROOT), "--check"],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, "运行 tools/sync_from_infotest.py 重新抽取：\n" + proc.stdout
