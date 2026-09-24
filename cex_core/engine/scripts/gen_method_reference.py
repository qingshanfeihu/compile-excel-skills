# 生成：tools/extract_engine.py ← InfoTest scripts/gen_method_reference.py（sha256 8f0c88b1ec821864）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import sys
from pathlib import Path
ROOT = _cex_data_path('')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cex_core.engine.scripts.gen_capability_atlas import _parse_cert_methods, _execute_actions_legacy as _execute_actions, main
__all__ = ['_parse_cert_methods', '_execute_actions', 'main']
if __name__ == '__main__':
    main()
