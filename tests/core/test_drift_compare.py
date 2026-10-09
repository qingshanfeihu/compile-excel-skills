"""--code-only 的判定（tools/drift_compare.py）：注释、文档字符串不比；代码结构必须一致；
字符串常量只在登记过的脱敏位置上允许不同，正则这类判据字符串改了仍然报。"""

from __future__ import annotations

import sys

from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
import drift_compare  # noqa: E402

FRESH = '''"""模块说明：出处 docs/forensics/R1.md。"""
import re

PATTERN = re.compile(r"^clear\\s+config\\s+all")  # 判据
SOURCE = "docs/forensics/R1.md"


def check(text):
    """按 #56 规则判定。"""
    return bool(PATTERN.match(text))
'''


def _ours(**swap):
    text = FRESH
    for old, new in swap.items():
        text = text.replace(old, new)
    return text


def test_comments_and_docstrings_do_not_count():
    ours = (FRESH.replace("# 判据", "# 判据（出处已脱敏）")
            .replace("出处 docs/forensics/R1.md。", "出处已脱敏。")
            .replace("按 #56 规则", "按 内部工单 规则"))
    assert drift_compare.same_code("m.py", ours, FRESH, {})


def test_a_sanitized_literal_counts_only_where_it_is_registered():
    ours = FRESH.replace('SOURCE = "docs/forensics/R1.md"', 'SOURCE = "内部取证文档（已脱敏）"')
    positions = drift_compare.literal_differences(ours, FRESH)
    assert positions and len(positions) == 1
    assert not drift_compare.same_code("m.py", ours, FRESH, {})
    assert drift_compare.same_code("m.py", ours, FRESH, {"m.py": positions})
    assert not drift_compare.same_code("other.py", ours, FRESH, {"m.py": positions})


def test_a_changed_rule_string_is_still_drift():
    changed = FRESH.replace("config\\s+all", "config\\s+everything")
    assert changed != FRESH
    ours = FRESH.replace('SOURCE = "docs/forensics/R1.md"', 'SOURCE = "内部取证文档（已脱敏）"')
    registered = {"m.py": drift_compare.literal_differences(ours, FRESH)}
    assert not drift_compare.same_code("m.py", ours, changed, registered)


def test_a_code_change_is_drift():
    changed = FRESH.replace("bool(PATTERN.match(text))", "PATTERN.search(text) is not None")
    assert drift_compare.literal_differences(FRESH, changed) is None
    assert not drift_compare.same_code("m.py", FRESH, changed, {"m.py": list(range(99))})


def test_non_python_files_are_compared_byte_for_byte():
    assert not drift_compare.same_code("a.json", '{"a": 1}', '{"a": 2}', {})
    assert drift_compare.same_code("a.json", '{"a": 1}', '{"a": 1}', {})


def test_the_registry_holds_positions_only():
    for rel, positions in drift_compare.load_registry().items():
        assert rel.startswith("cex_core/") and rel.endswith(".py")
        assert all(isinstance(p, int) and p >= 0 for p in positions)
