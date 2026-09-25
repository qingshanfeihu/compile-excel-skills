#!/usr/bin/env python3
"""compile_excel: cases JSON → FileIR → emit_xlsx → case.xlsx。

分工：结构由本脚本 + ist_emit 包保证（执行页定位、表头、列语义、契约 marker、
fd 级原子写盘），内容由调用方（agent）决定。上游对齐：
- InfoTest_Engine main/case_compiler/xlsx_emit.py（emit_xlsx）
- InfoTest_Engine main/ist_core/tools/device/emit_xlsx_tool.py 的
  `_steps_to_caseir`（步骤五元组 → CaseIR，含 test_env 小写归一、
  check_point 捕获比较归一、check_point 必备门槛）与文件级 init 语义
  （`Row(APV_0, cmds_config, 共享前置块)`）。
行为差异声明见 reference/excel-contract.md。

用法：
    python compile_excel.py --cases cases.json [--out DIR] [--no-sentinel]

cases.json 契约：
    {
      "batch": "批次名",                 # 必填，单段路径成分，决定输出子目录
      "init_commands": ["...", "..."],   # 可选，文件级共享前置（合为一条 cmds_config 块）
      "cases": [
        {
          "autoid": "202609236683010001",   # 必填：12-24 位纯数字（生产惯例 18 位）
          "priority": "P1",              # 可选，缺省 P1
          "description": "用例标题",      # 可选，进 CaseIR.title（不落卷面）
          "steps": [                      # 必填，非空；每步一行
            {"e": "APV_0", "f": "cmd_config", "g": "show version",
             "h": "", "i": "", "desc": "查看版本"}
          ]
        }
      ]
    }
列语义见 reference/column-semantics.md。键名 e/f/g/h/i 与 E/F/G/H/I 等价。
末尾自动垫一条哨兵 case（autoid=999999999999999, sleep 1）——框架延迟执行
契约，前 N 个真 case 全执行；--no-sentinel 可关。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _cex_path  # noqa: F401,E402 — 发行根进 sys.path

from cex_core.ist_emit.case_ir import CaseIR, FileIR, Row, Step  # noqa: E402
from cex_core.ist_emit.xlsx_emit import emit_xlsx  # noqa: E402

SENTINEL_AUTOID = "999999999999999"

# InfoTest structural_gate._parse_workbook_model 按全数字且 ≥12 位识别用例行（用例边界）；
# 生产惯例 18 位机器号（lint_xlsx_case 的 _AUTOID_RE = ^\d{18}$）。低于 12 位会被
# 框架当普通行，多 case 边界退化、verdict 错归——出件前拒绝。
_AUTOID_RE = re.compile(r"^\d{12,24}$")


class CompileError(Exception):
    """产出前的所有校验失败都走这个异常，禁止带病出盘。"""


def _step_field(step: dict, lower_key: str):
    upper = {"e": "E", "f": "F", "g": "G", "h": "H", "i": "I"}[lower_key]
    if lower_key in step:
        return step[lower_key]
    return step.get(upper)


def _validate_batch(batch: str) -> str:
    batch = str(batch or "").strip()
    if not batch:
        raise CompileError("缺少 batch（批次名）")
    if "/" in batch or batch.startswith(".") or batch in {"/", "\\"}:
        raise CompileError(f"batch 名不安全: {batch!r}")
    return batch


def _steps_to_caseir(autoid: str, steps: list, *, priority: str = "P1",
                     title: str = "") -> CaseIR:
    """[{e,f,g,h?,i?,desc?}, ...] → CaseIR。

    忠实移植 emit_xlsx_tool._steps_to_caseir 的三处 correct-by-construction
    归一化与 check_point 门槛；G 列内容校验不在本层（见差异声明）。
    """
    ist_steps: list[Step] = []
    has_cp = False
    seen_vars: set[str] = set()
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise CompileError(f"用例 {autoid}: step[{i}] 不是对象")
        e = str(_step_field(s, "e") or "").strip()
        f = str(_step_field(s, "f") or "").strip()
        if not e or not f:
            raise CompileError(f"用例 {autoid}: step[{i}] 缺少 E 或 F")
        # 归一化：test_env 的 F 是触发机主机名，框架按 getattr(env, F) 分派
        # 且不转小写——强制降小写保证可分派（合法主机名均小写）。
        if e == "test_env":
            f = f.lower()
        raw_g = _step_field(s, "g")
        g_val = "" if raw_g is None else str(raw_g)
        h_val = _step_field(s, "h") or None
        i_val = (str(_step_field(s, "i"))
                 if _step_field(s, "i") is not None else None)
        # 归一化：check_point 引用前序捕获变量误放 G 列（字面）→ 移到 H 列（寄存器查找）。
        if e == "check_point" and not h_val and g_val in seen_vars:
            h_val, g_val = g_val, ""
        if e == "check_point":
            has_cp = True
            # 归一化：check_point 引用 H 寄存器作期望值时 found → abs_found
            #（框架 found() 把期望当正则；捕获值含正则元字符，连自匹配都 fail）。
            if h_val and f == "found":
                f = "abs_found"
        elif h_val:  # 非 check_point 的 H = 捕获进变量，登记供后续引用
            seen_vars.add(str(h_val))
        # found_times 框架硬契约：I 列必须是正整数次数、H 列必须空
        if e == "check_point" and f == "found_times":
            count_text = (i_val or "").strip()
            try:
                count = int(count_text)
            except ValueError as exc:
                raise CompileError(
                    f"用例 {autoid} step[{i}]: found_times 要求 I 列为正整数次数"
                ) from exc
            if count <= 0 or str(count) != count_text:
                raise CompileError(
                    f"用例 {autoid} step[{i}]: found_times 要求 I 列为正整数次数"
                )
            if h_val:
                raise CompileError(
                    f"用例 {autoid} step[{i}]: found_times 要求 H 列为空"
                )
        row = Row(test_object=e, method=f, data=g_val,
                  save_as=h_val, input_var=i_val)
        ist_steps.append(Step(stmt_type=2 + i,
                              description=str(s.get("desc") or s.get("description") or ""),
                              rows=[row]))
    if not has_cp:
        raise CompileError(
            f"用例 {autoid} 没有任何 check_point 步骤——上机必失败"
            "（pass 要求 success>0），请补一条 found 断言"
        )
    return CaseIR(autoid=autoid, priority=priority or "P1",
                  title=(title or f"agent_{autoid}"), steps=ist_steps)


def _build_sentinel() -> CaseIR:
    """末尾垫底哨兵 case；只用框架内建最短合法等待，不携带设备命令。"""
    return CaseIR(
        autoid=SENTINEL_AUTOID, priority="P9", title="sentinel-do-not-execute",
        steps=[Step(stmt_type=2, description="sentinel",
                    rows=[Row(test_object="time", method="sleep", data="1")])],
    )


def build_file_ir(doc: dict, *, sentinel: bool = True) -> FileIR:
    if not isinstance(doc, dict):
        raise CompileError("cases JSON 顶层必须是对象")
    batch = _validate_batch(doc.get("batch"))
    cases = doc.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CompileError("cases 必须是非空数组")

    case_irs: list[CaseIR] = []
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            raise CompileError(f"cases[{idx}] 不是对象")
        autoid = str(case.get("autoid") or "").strip()
        if not autoid:
            raise CompileError(f"cases[{idx}] 缺少 autoid")
        if not _AUTOID_RE.match(autoid):
            raise CompileError(
                f"cases[{idx}] autoid 必须是 12-24 位纯数字（InfoTest 框架按 ≥12 位"
                f"数字识别用例边界，生产惯例 18 位），当前 {autoid!r}")
        if any(existing.autoid == autoid for existing in case_irs):
            raise CompileError(f"autoid 重复: {autoid}")
        steps = case.get("steps")
        if not isinstance(steps, list) or not steps:
            raise CompileError(f"用例 {autoid}: steps 必须是非空数组")
        case_irs.append(_steps_to_caseir(
            autoid, steps,
            priority=str(case.get("priority") or "P1"),
            title=str(case.get("description") or ""),
        ))

    # 文件级共享前置：合为一条 cmds_config 块（上游合并通道同型）
    init_commands = [str(c) for c in (doc.get("init_commands") or []) if str(c).strip()]
    shared = "\n".join(init_commands).strip()
    init_rows = ([Row(test_object="APV_0", method="cmds_config", data=shared)]
                 if shared else [])

    cases_out = [*case_irs, _build_sentinel()] if sentinel else case_irs
    return FileIR(feature=batch, author="IST-Core-agent", init_rows=init_rows,
                  cases=cases_out, module="ist_smoke")


PROVENANCE_SCHEMA = "ist.excel.provenance"
_SOURCE_KINDS = {
    "author-verbatim", "author", "spec", "manual",
    "defectspec", "defect", "configbinding", "capabilityxml",
    # cex_author_emit 从引擎展开带出的断言出处（provenance_ir 的外部来源与派生来源）
    "intent", "defect_spec", "capability_xml", "footprint", "env_facts", "skeleton",
    "config_derived", "captured_relation", "distribution_derived", "membership_derived",
    "status_derived",
}


def _build_provenance(doc: dict, fir: FileIR) -> tuple[dict, int]:
    """逐 case check_point 的预期值来源边车（镜像引擎 ist.ide.assertion 轻量版）。

    cases.json 的 check_point 步骤可带 ``source: {"kind": ..., "ref": ...}``；
    缺省回落 author-verbatim（ref 指向脑图 autoid）并计数提示。
    """
    raw_cases = {str(c.get("autoid") or "").strip(): c for c in doc.get("cases", [])}
    prov = {"schema": PROVENANCE_SCHEMA, "batch": fir.feature, "cases": {}}
    defaulted = 0
    for case_ir in fir.cases:
        raw = raw_cases.get(case_ir.autoid) or {}
        entries = []
        for s in raw.get("steps", []):
            if str(_step_field(s, "e") or "").strip() != "check_point":
                continue
            src = s.get("source") or {}
            kind = str(src.get("kind") or "").strip().lower()
            ref = str(src.get("ref") or "").strip()
            if kind not in _SOURCE_KINDS or not ref:
                defaulted += 1
                kind, ref = "author-verbatim", f"mindmap:{case_ir.autoid}"
            entries.append({
                "E": "check_point",
                "F": str(_step_field(s, "f") or ""),
                "G": str(_step_field(s, "g") or ""),
                "source": {"kind": kind, "ref": ref},
            })
        if entries:
            prov["cases"][case_ir.autoid] = entries
    return prov, defaulted


def compile_excel(cases_path: str, out_dir: str, *, sentinel: bool = True) -> dict:
    try:
        doc = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompileError(f"cases 文件不存在: {cases_path}") from exc
    except json.JSONDecodeError as exc:
        raise CompileError(f"cases JSON 解析失败: {exc}") from exc

    fir = build_file_ir(doc, sentinel=sentinel)
    out_root = Path(out_dir).resolve()
    target = out_root / fir.feature / "case.xlsx"
    stats = emit_xlsx(fir, target, trusted_outputs_root=out_root)
    prov, defaulted = _build_provenance(doc, fir)
    (out_root / fir.feature / "provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    stats["ok"] = True
    stats["batch"] = fir.feature
    stats["init_commands"] = len(fir.init_rows)
    stats["sources_defaulted"] = defaulted
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="compile_excel: 用例 JSON → case.xlsx")
    parser.add_argument("--cases", required=True, help="cases JSON 路径")
    parser.add_argument("--out", default="compile_outputs", help="产物根目录")
    parser.add_argument("--no-sentinel", action="store_true",
                        help="不垫末尾哨兵 case（默认垫，对齐 InfoTest emit 行为）")
    args = parser.parse_args()

    try:
        result = compile_excel(args.cases, args.out, sentinel=not args.no_sentinel)
    except CompileError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:  # noqa: BLE001 — 出件层错误原样结构化转述
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
