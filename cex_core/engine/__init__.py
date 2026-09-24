"""从 InfoTest 抽取的编译判据引擎（tools/extract_engine.py 生成，不在这里手改）。

模块树与 InfoTest ``main`` 包一一对应：``cex_core.engine.case_compiler.apv_lang`` 就是
``main/case_compiler/apv_lang.py``。数据根见 ``_root``；抽取范围、每个文件的源哈希与
闭包边界见 MANIFEST.json。
"""

from cex_core.engine._root import DATA_ROOT_ENV, data_root, data_root_configured

__all__ = ["DATA_ROOT_ENV", "data_root", "data_root_configured"]
