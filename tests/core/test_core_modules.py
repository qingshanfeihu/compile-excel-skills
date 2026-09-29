"""cex_core 里手写与逐字抽取模块的回归：

- ist_emit 的按需导出相对本包解析：cex_core 被网关 vendor 成 gateway.vendor.cex_core 也找得到，
  不去碰顶层的 ist_emit / cex_core；
- security_scrub 的项目根只认真实的发行根：/opt/cex_core/ 这类浅装位置、HOME=/ 时不拿 "/"
  去做子串替换；
- tools/sync_from_infotest.py 逐字复制时注释里的内部实证记录换成占位，代码与字符串一字不动。
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT


def _python(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=120, check=False)


def test_ist_emit_lazy_exports_resolve_inside_the_package():
    script = f'''
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_core import ist_emit
assert ist_emit.CaseIR.__module__ == "cex_core.ist_emit.case_ir"
assert ist_emit.resolve_execution_sheet.__module__ == "cex_core.ist_emit.excel_contract"
assert ist_emit.PINNED_CONTRACT_SHA256
assert "ist_emit" not in sys.modules
print("ok")
'''
    proc = _python(script)
    assert proc.returncode == 0 and proc.stdout.strip() == "ok", proc.stderr[-1500:]


def test_ist_emit_lazy_exports_work_from_a_vendored_copy(tmp_path):
    """网关把 cex_core 放在 gateway/vendor/ 下当子包用：按需导出不许跑去找顶层包。"""
    vendor = tmp_path / "vend"
    shutil.copytree(REPO_ROOT / "cex_core" / "ist_emit", vendor / "cex_core" / "ist_emit",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (vendor / "__init__.py").write_text("", encoding="utf-8")
    (vendor / "cex_core" / "__init__.py").write_text("", encoding="utf-8")
    script = f'''
import sys
sys.path.insert(0, {str(tmp_path)!r})
from vend.cex_core import ist_emit
assert ist_emit.Step.__module__ == "vend.cex_core.ist_emit.case_ir"
assert ist_emit.ExcelContractError.__module__ == "vend.cex_core.ist_emit.excel_contract"
assert "cex_core" not in sys.modules and "ist_emit" not in sys.modules
print("ok")
'''
    proc = _python(script)
    assert proc.returncode == 0 and proc.stdout.strip() == "ok", proc.stderr[-1500:]


def _scrubber(module_file: str, monkeypatch, home: str):
    """把 cex_core/security_scrub.py 当成装在 module_file 那里的副本加载（不必真的写到那里）。"""
    monkeypatch.setenv("HOME", home)
    source = (REPO_ROOT / "cex_core" / "security_scrub.py").read_text(encoding="utf-8")
    namespace = {"__file__": module_file, "__name__": "cex_security_scrub_probe"}
    exec(compile(source, module_file, "exec"), namespace)  # noqa: S102 — 本仓自己的模块源码
    return namespace


def test_a_shallow_install_or_root_home_does_not_mangle_paths(monkeypatch):
    text = "see /usr/lib/x.so and C:/y; also /optional/z and https://example.invalid/p"
    scrub = _scrubber("/opt/cex_core/security_scrub.py", monkeypatch, "/")
    assert scrub["_path_roots"]() == ("", "")
    assert scrub["scrub_text"](text) == scrub["scrub_text"](text, scrub_paths=False) == text


def test_a_real_distribution_root_and_home_are_still_replaced(tmp_path, monkeypatch):
    dist = tmp_path / "share" / "compile-excel" / "current"
    home = tmp_path / "home" / "someone"
    scrub = _scrubber(str(dist / "cex_core" / "security_scrub.py"), monkeypatch, str(home))
    project, user_home = scrub["_path_roots"]()
    assert project == str(dist.resolve()) and user_home == str(home)
    out = scrub["scrub_text"](f"failed at {dist.resolve()}/cex_core/x.py and {home}/notes")
    assert "<project-root>/cex_core/x.py" in out and "<user-home>/notes" in out


def _sync_tool():
    tools = str(REPO_ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    spec = importlib.util.spec_from_file_location("cex_sync_from_infotest_under_test",
                                                  REPO_ROOT / "tools" / "sync_from_infotest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synced_copies_scrub_run_records_in_comments_only(monkeypatch):
    # 人名缩写批次名单从环境注入（公开仓不携带真实名单）
    monkeypatch.setenv("CEX_INTERNAL_HANDLES", "internala")
    sync = _sync_tool()
    source = ('def f(x):\n'
              '    # 比对器误报（internala 内部工单/内部工单），实证 202609240000000001 的尾号 223344；床 10.4.127.103\n'
              '    return x == "internala keeps 223344"  # RUN_20260924_a\n')
    out = sync._scrub_comments(source)
    assert '"internala keeps 223344"' in out
    comments = [line.split("#", 1)[1] for line in out.splitlines() if "# " in line]
    assert comments and all("internala" not in c and "223344" not in c and "RUN_2026" not in c
                            and "10.4.127.103" not in c for c in comments)
    assert "<batch>" in out and "<case>" in out and "<run>" in out and "198.19.127.103" in out
    assert Path(REPO_ROOT / "cex_core" / "vendor_cmd.py").read_text(encoding="utf-8") \
        .count("internala") == 0
