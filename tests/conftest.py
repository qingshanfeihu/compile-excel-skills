"""测试公共设置：发行根进 sys.path；定位同级的 InfoTest 与 compile-excel-server 检出（对拍与联调用）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

INFOTEST_ROOT = Path(os.environ.get("INFOTEST_ROOT")
                     or REPO_ROOT.parent / "InfoTest_Engine").resolve()
SERVER_ROOT = Path(os.environ.get("CES_SERVER_ROOT")
                   or REPO_ROOT.parent / "compile-excel-server").resolve()
