# 生成：tools/extract_engine.py ← InfoTest scripts/gen_package_advisories.py（sha256 629f71d83701254f）。不在这里手改。
"""按裁决源和归档资产生成先例封禁投影。"""
from cex_core.engine._root import _cex_data_path
import sys
from pathlib import Path
sys.path.insert(0, str(_cex_data_path('')))
from cex_core.engine.scripts.maintenance.build_package_advisories import main
if __name__ == '__main__':
    raise SystemExit(main())
