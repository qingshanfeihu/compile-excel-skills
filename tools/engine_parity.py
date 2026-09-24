#!/usr/bin/env python3
"""对拍：InfoTest 自己的测试分别跑原模块与 cex_core/engine 抽取副本，逐条比结果。

  python3 tools/engine_parity.py --infotest-root ../InfoTest_Engine \\
      --python ~/.venvs/infotest-engine/bin/python --mode faithful [--tests-file F | tests…]

- faithful：抽取副本里指向闭包外的延迟 import 回落到 InfoTest 原模块，逐条结果
  （passed/failed/error/skipped，失败时再比异常类型）必须完全一致；
- standalone：那些 import 照客户端的样子失败，列出结果变了的测试和它们撞上的边界。

每条测试的结果按 (classname, name) 对齐；抽取副本那一轮必须留下别名生效的证据
（CEX_ALIAS_MARKER），否则判失败——插件没装上时两轮必然"完全一致"，那不是对拍。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[1]
# 已知且与引擎行为无关的差异：测试 id → (InfoTest 结果, 抽取副本结果, 理由)。结果对不上
# 就照常算差异——这里只放行一模一样的那一种
EXPECTED_DIFFS = {
    "tests.ist_core.tools.test_structural_gate_lesson_closure::test_no_orphan_lesson_text": (
        ("passed", ""), ("failed", "FileNotFoundError"),
        "the test reads emit_xlsx_tool.py next to structural_gate.__file__ to scan its gate "
        "codes; the extracted tree has no emit_xlsx_tool (it is outside the closure)"),
}
# 下面这些测试读的是模块源码文本，不是行为：抽取副本是 ast.unparse 的输出（字符串字面改用
# 单引号）、去了注释、文件也不在 InfoTest 仓里。行为由同一批模块的其余测试对拍。
_UNPARSED = ("reads the module source text and matches a double-quoted literal; the extracted "
             "source is ast.unparse output, which writes string literals with single quotes")
_SOURCE_TEXT = {
    "tests.ist_core.compile_engine.test_state_channel_closure"
    "::test_counts_update_keys_are_all_declared_state_channels": ("AssertionError", _UNPARSED),
    "tests.ist_core.compile_engine.test_state_channel_closure"
    "::test_gather_or_close_reads_the_dedicated_channel_counter": ("AssertionError", _UNPARSED),
    "tests.ist_core.compile_engine.test_disposition_axis_coverage"
    "::test_coverage_axis_names_are_real_counter_keys": ("AssertionError", _UNPARSED),
    "tests.ist_core.compile_engine.test_authored_conflict_followup"
    "::test_idem_key_strips_every_underscore_key_so_pid_cannot_split_a_replay":
        ("AssertionError", _UNPARSED),
    "tests.case_compiler.test_prerequisite_findings"
    "::test_the_emit_side_always_rewrites_the_sidecar_even_with_no_findings": ("", _UNPARSED),
    "tests.case_compiler.test_prerequisite_findings"
    "::test_the_read_back_cap_is_this_files_own_constant":
        ("ValueError", "resolves the module file relative to the InfoTest root and git-greps "
                       "main/; the extracted module lives in the skills repo"),
    "tests.ist_core.compile_engine.test_writeback_failure_accounting"
    "::test_writeback_failed_has_only_the_disclosure_reader":
        ("", "greps main/ under the root derived from _shared.__file__; the extracted _shared "
             "lives in the skills repo, which has no main/"),
    "tests.ist_core.compile_engine.test_mechanical_case_unproducible"
    "::test_the_code_comment_writes_down_the_boundary_against_the_device_outlet":
        ("ValueError", "reads a code comment next to the constant; the extraction strips comments"),
    # 以下两条是模块名本身：抽取副本的 __name__ 是 cex_core.engine.*
    "tests.case_compiler.test_framework_projection_identity"
    "::test_preflight_keeps_the_method_reference_producer_in_source_drift_guidance":
        ("AssertionError", "the repair hint names the generator by its module name, which in the "
                           "extracted tree is cex_core.engine.scripts.gen_capability_atlas"),
    "tests.ist_core.compile_engine.test_entry_projection_rebuild_is_freshness_gated"
    "::test_current_policy_and_catalog_keep_the_active_generation":
        ("", "raises the level of the logger named after the InfoTest module; the extracted module "
             "logs under its own name, so the INFO record is not captured"),
}
EXPECTED_DIFFS.update({test: (("passed", ""), ("failed", exc), reason)
                       for test, (exc, reason) in _SOURCE_TEXT.items()})
_EXC = re.compile(r"^\s*([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning|Failed|Skipped))\b")


def _outcomes(junit: Path) -> dict[tuple[str, str], tuple[str, str]]:
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        key = (case.get("classname") or "", case.get("name") or "")
        state, kind = "passed", ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                state = {"failure": "failed"}.get(tag, tag)
                if tag != "skipped":
                    match = _EXC.match(node.get("message") or "")
                    kind = match.group(1).rsplit(".", 1)[-1] if match else ""
                break
        out[key] = (state, kind)
    return out


def _run(python: str, root: Path, tests: list[str], junit: Path, workers: int,
         env_extra: dict[str, str] | None, plugin: bool) -> None:
    env = dict(os.environ)
    env.update(env_extra or {})
    cmd = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}",
           "-o", "junit_family=xunit1"]
    if workers > 1:
        cmd += ["-n", str(workers)]
    if plugin:
        env["PYTHONPATH"] = os.pathsep.join(
            [str(SKILLS_ROOT / "tests" / "core"), str(SKILLS_ROOT), env.get("PYTHONPATH", "")])
        cmd += ["-p", "engine_alias_plugin"]
    subprocess.run(cmd + tests, cwd=root, env=env, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    if not junit.is_file():
        raise SystemExit(f"pytest produced no junit report ({'aliased' if plugin else 'baseline'})")


def compare(root: Path, python: str, tests: list[str], mode: str, workers: int = 4,
            baseline: Path | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="cex-parity-") as tmp:
        tmpdir = Path(tmp)
        base_xml = baseline or tmpdir / "base.xml"
        if baseline is None:
            _run(python, root, tests, base_xml, workers, None, plugin=False)
        marker = tmpdir / "alias.json"
        cex_xml = tmpdir / "cex.xml"
        _run(python, root, tests, cex_xml, workers, {
            "CEX_SKILLS_ROOT": str(SKILLS_ROOT), "CEX_ALIAS_MODE": mode,
            "CEX_ALIAS_MARKER": str(marker), "CEX_ENGINE_DATA_ROOT": str(root)}, plugin=True)
        if not marker.is_file():
            raise SystemExit("alias plugin left no marker: the extracted copy was not exercised")
        aliased = json.loads(marker.read_text(encoding="utf-8"))
        engine_dir = str(SKILLS_ROOT / "cex_core" / "engine")
        not_aliased = sorted(k for k, v in aliased.items() if not str(v).startswith(engine_dir))
        base, cex = _outcomes(base_xml), _outcomes(cex_xml)
    diffs, expected = [], []
    for key in sorted(set(base) | set(cex)):
        a, b = base.get(key), cex.get(key)
        if a == b:
            continue
        test = "::".join(key)
        known = EXPECTED_DIFFS.get(test)
        if mode == "faithful" and known and (a, b) == (known[0], known[1]):
            expected.append({"test": test, "reason": known[2]})
            continue
        diffs.append({"test": test, "infotest": a, "extracted": b})
    counts = {}
    for state, _kind in base.values():
        counts[state] = counts.get(state, 0) + 1
    return {"mode": mode, "tests": len(base), "baseline_counts": counts,
            "aliased_modules": len(aliased), "not_aliased": not_aliased, "diffs": diffs,
            "expected_diffs": expected}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--infotest-root", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--mode", choices=("faithful", "standalone"), default="faithful")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tests-file")
    parser.add_argument("--baseline", help="reuse a baseline junit report")
    parser.add_argument("--report", help="write the JSON report here")
    parser.add_argument("tests", nargs="*")
    args = parser.parse_args(argv)
    tests = list(args.tests)
    if args.tests_file:
        tests += [ln.strip() for ln in Path(args.tests_file).read_text(encoding="utf-8").splitlines()
                  if ln.strip()]
    if not tests:
        parser.error("no tests given")
    report = compare(Path(args.infotest_root).resolve(), args.python, tests, args.mode,
                     args.workers, Path(args.baseline) if args.baseline else None)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(f"{report['mode']}: {report['tests']} tests, {len(report['diffs'])} differ, "
          f"aliased {report['aliased_modules']} modules, not aliased {report['not_aliased']}")
    return 0 if not report["diffs"] and not report["not_aliased"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
