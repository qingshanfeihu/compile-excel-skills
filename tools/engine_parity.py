#!/usr/bin/env python3
"""对拍：InfoTest 自己的测试分别跑原模块与 cex_core/engine 抽取副本，逐条比结果。

  python3 tools/engine_parity.py --infotest-root ../InfoTest_Engine \\
      --python ~/.venvs/infotest-engine/bin/python --mode faithful [--tests-file F | tests…]

- faithful：抽取副本里指向闭包外的延迟 import 回落到 InfoTest 原模块，逐条结果
  （passed/failed/error/skipped，失败时再比异常类型）必须完全一致；
- standalone（客户端模式）：那些 import 照客户端的样子失败。结果变了的测试里，失败原因是
  "找不到 MANIFEST 登记的边界模块"的记进 boundary_diffs（客户端本来就走不到那里）；其余的
  才算差异。被 try/except 包住的边界 import 会悄悄换分支，不一定报 ModuleNotFoundError：
  在全量测试上这类差异预期存在（见 docs/engine-parity.md），默认小批里没有。

每条测试的结果按 (classname, name) 对齐；抽取副本那一轮必须留下别名生效的证据
（CEX_ALIAS_MARKER），否则判失败——插件没装上时两轮必然"完全一致"，那不是对拍。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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
    "tests.case_compiler.test_engine_defect_not_author_problem"
    "::test_recompose_quarantine_is_classified_as_engine_defect": ("ValueError", _UNPARSED),
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
# 预检的修复提示按生成器的模块名拼 `python -m …`：抽取副本里是 cex_core.engine.scripts.…
_GENERATOR_MODULE_NAME = ("the preflight repair hint spells `python -m <generator module>`; the "
                          "extracted generator's module name is cex_core.engine.scripts.…")
EXPECTED_DIFFS.update({
    "tests.ist_core.compile_engine.test_env_preflight_cache::" + test:
        (("passed", ""), ("failed", "AssertionError"), _GENERATOR_MODULE_NAME)
    for test in (
        "test_missing_projection_is_reported_without_inventing_a_drift_digest",
        *(f"test_preflight_names_the_actual_drifted_projection_and_its_generator[{case}]" for case in (
            "capability_usage_index.json-scripts.gen_capability_usage_index",
            "device_behavior_examples.json-scripts.gen_device_behavior_examples",
            "language_docs_index.json-scripts.maintenance.build_language_docs_index",
            "package_advisories_10.5.json-scripts.maintenance.build_package_advisories")),
    )
})
# 按 InfoTest 模块名模拟导入失败（改 builtins.__import__ 只拦 main.* 这个名字）：抽取副本导入的是
# cex_core.engine.* 这个名字，模拟的失败根本不触发，走到的是后面的正常判据
_SIMULATED_IMPORT_FAILURE = ("simulates an import failure for the InfoTest module name (patching "
                             "builtins.__import__ or sys.modules['main.…']); the extracted code "
                             "imports the engine name, so the simulated failure never fires")
EXPECTED_DIFFS.update({
    test: (("passed", ""), ("failed", ""), _SIMULATED_IMPORT_FAILURE) for test in (
        "tests.ist_core.tools.test_tau_coverage_gate"
        "::test_gate_import_failure_cannot_silently_pass",
        "tests.ist_core.tools.test_command_existence_gate"
        "::test_gate_command_existence_import_failure_refuses",
    )
})
_EXC = re.compile(r"^\s*([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning|Failed|Skipped))\b")
_MISSING_ENGINE_MODULE = re.compile(r"No module named '(cex_core\.engine(?:\.[\w]+)*)'")


def _results(junit: Path) -> dict[tuple[str, str], tuple[str, str, str]]:
    """(classname, name) → (结果, 异常类型, 失败/报错消息)。"""
    out: dict[tuple[str, str], tuple[str, str, str]] = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        key = (case.get("classname") or "", case.get("name") or "")
        state, kind, message = "passed", "", ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                state = {"failure": "failed"}.get(tag, tag)
                if tag != "skipped":
                    message = node.get("message") or ""
                    match = _EXC.match(message)
                    kind = match.group(1).rsplit(".", 1)[-1] if match else ""
                break
        out[key] = (state, kind, message)
    return out


def _outcomes(junit: Path) -> dict[tuple[str, str], tuple[str, str]]:
    return {key: (state, kind) for key, (state, kind, _message) in _results(junit).items()}


def _boundary_hit(message: str, boundary_targets: set[str]) -> str:
    """消息是"找不到 MANIFEST 登记的边界模块（或它的上级包）"时返回那个模块的 InfoTest 名。"""
    match = _MISSING_ENGINE_MODULE.search(message or "")
    if match is None:
        return ""
    engine_name = match.group(1)
    if engine_name == "cex_core.engine.scripts" or engine_name.startswith("cex_core.engine.scripts."):
        name = "scripts" + engine_name[len("cex_core.engine.scripts"):]
    else:
        name = "main" + engine_name[len("cex_core.engine"):]
    hit = any(target == name or target.startswith(name + ".") for target in boundary_targets)
    return name if hit else ""


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
            baseline: Path | None = None, save_baseline: Path | None = None) -> dict:
    manifest = json.loads((SKILLS_ROOT / "cex_core" / "engine" / "MANIFEST.json")
                          .read_text(encoding="utf-8"))
    boundary_targets = set(manifest["boundary_targets"])
    with tempfile.TemporaryDirectory(prefix="cex-parity-") as tmp:
        tmpdir = Path(tmp)
        base_xml = baseline or tmpdir / "base.xml"
        if baseline is None:
            _run(python, root, tests, base_xml, workers, None, plugin=False)
        if save_baseline is not None:
            shutil.copyfile(base_xml, save_baseline)
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
        base, cex = _outcomes(base_xml), _results(cex_xml)
    diffs, expected, boundary = [], [], []
    for key in sorted(set(base) | set(cex)):
        a = base.get(key)
        b = cex[key][:2] if key in cex else None
        if a == b:
            continue
        test = "::".join(key)
        known = EXPECTED_DIFFS.get(test)
        if known and (a, b) == (known[0], known[1]):
            expected.append({"test": test, "reason": known[2]})
            continue
        missing = _boundary_hit(cex[key][2], boundary_targets) \
            if mode == "standalone" and key in cex and b[0] in ("failed", "error") else ""
        if missing:
            boundary.append({"test": test, "infotest": a, "extracted": b, "boundary": missing})
            continue
        diffs.append({"test": test, "infotest": a, "extracted": b})
    counts = {}
    for state, _kind in base.values():
        counts[state] = counts.get(state, 0) + 1
    return {"mode": mode, "tests": len(base), "baseline_counts": counts,
            "aliased_modules": len(aliased), "not_aliased": not_aliased, "diffs": diffs,
            "expected_diffs": expected, "boundary_diffs": boundary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--infotest-root", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--mode", choices=("faithful", "standalone"), default="faithful")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tests-file")
    parser.add_argument("--baseline", help="reuse a baseline junit report")
    parser.add_argument("--save-baseline", help="keep the baseline junit report here (for a "
                                                "second mode over the same tests)")
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
                     args.workers, Path(args.baseline) if args.baseline else None,
                     Path(args.save_baseline) if args.save_baseline else None)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(f"{report['mode']}: {report['tests']} tests, {len(report['diffs'])} differ, "
          f"{len(report['boundary_diffs'])} stop at the closure boundary, "
          f"aliased {report['aliased_modules']} modules, not aliased {report['not_aliased']}")
    return 0 if not report["diffs"] and not report["not_aliased"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
