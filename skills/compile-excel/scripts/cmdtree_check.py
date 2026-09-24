#!/usr/bin/env python3
"""cmdtree_check: 编译期命令 grounding —— cases.json 里的每条 APV 命令必须在命令树中存在。

把「设备不支持这个命令」从上机期（烧一轮床才发现 % invalid）提前到编译期。
对齐引擎口径：命令在不在这个 build 上，由命令树投影单方面说了算——查不到就拒绝，
不管规格书或用例怎么写。

判定来源：--projection 显式路径，否则工作区已同步数据包（cex_sync）里的命令树投影
（vendor_stdlib_*.json）；只有显式给了 --tree 才读原始 cmdtree XML（本地调试用）。
投影判定用 cex_core.vendor_cmd.resolve_vendor_command——与引擎同一个判定函数（逐字抽取），
既判命令头在不在，也判参数是否合契约。服务端只下发投影，不下发原始 XML
（原始 XML 带参数默认值，含凭据默认值）。

检查语义：
- 每条 E=APV_* / F=cmd* 的步骤命令，剥掉前导 "no " 后在树中做贪心路径匹配；
- 全路径命中 = ok；部分命中（0<depth<len）= unknown_tail（多半是拼写/单复数，
  附同前缀兄弟节点作建议——portlist→portlists 就是这么抓的）；零命中 = unknown_head；
- show/get/clear 等观察类命令同样在树内校验；
- 树的 build（文件名 _585 等）与工作区 device_build 不一致时警告（不阻断）。

用法：
  python3 scripts/cmdtree_check.py --cases cases.json [--projection vendor_stdlib_x.json]
  python3 scripts/cmdtree_check.py --xlsx compile_outputs/<batch>/case.xlsx
退出码：0 = 全部命中；1 = 存在未知命令（应修 cases.json 再编译）；2 = 树缺失/不可解析。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPORT_SCHEMA = "ist.excel.cmdtree-check"

_BUILD_RE = re.compile(r"cmdtree[_\-]?(\w+)\.xml$", re.I)
_SENTINEL_AUTOID = "999999999999999"

# 剥掉后不查树的纯框架词（不出现在设备命令树里的执行器指令）
_FRAMEWORK_WORDS = {"page"}


def _workspace(start: Path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _cex_path  # noqa: F401,E402 — 发行根进 sys.path

    from cex_client import workspace as wsmod

    return wsmod.find(start)


def _find_tree(explicit: str) -> tuple[Path | None, str]:
    """返回 (树路径, build 标签)。原始 XML 只认显式路径，不在任何目录里自动找。"""
    path = Path(explicit).expanduser()
    if not path.is_file():
        return None, ""
    m = _BUILD_RE.search(path.name)
    return path, (m.group(1) if m else "")


def _find_projection(explicit: str, workspace: Path) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None
    ws = _workspace(workspace)
    if ws is None:
        return None
    from cex_client import bundle

    try:
        return bundle.entry_path(ws, "cmdtree", "vendor_stdlib_")
    except Exception:  # noqa: BLE001 — 工作区坏了按“没有投影”处理，由调用方报 exit 2
        return None


def _check_with_projection(steps: list[dict], projection_path: Path, report: dict) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _cex_path  # noqa: F401,E402 — 发行根进 sys.path

    from cex_core.vendor_cmd import load_projection, resolve_vendor_command

    projection = load_projection(projection_path)
    for s in steps:
        cmd = str(s.get("g", "")).strip()
        if not cmd:
            continue
        negated = cmd.lower().startswith("no ")
        probe = cmd[3:].strip() if negated else cmd
        report["checked"] += 1
        if not probe or probe.lower() in _FRAMEWORK_WORDS:
            report["ok"] += 1
            continue
        verdict = resolve_vendor_command(probe, projection)
        if verdict.get("hit"):
            report["ok"] += 1
            continue
        if not verdict.get("decided"):
            report["warnings"].append(f"{cmd!r}: 投影无法判定（不是以命令词开头的行）")
            report["ok"] += 1
            continue
        report["unknown"].append({
            "autoid": s.get("autoid", ""),
            "command": cmd,
            "matched_prefix": verdict.get("head", ""),
            "reason": ("参数不合投影记录的契约" if verdict.get("reason_code")
                       == "parameter_contract_violation" else "命令头不在投影里"),
            "reason_code": verdict.get("reason_code", ""),
            "parameter_error": verdict.get("parameter_error"),
        })


def _tree_paths(xml_path: Path) -> tuple[dict, dict]:
    """返回 (路径→is_item 叶命令, 每个前缀的直接子节点)。

    匹配语义：命令 head = 树中一条路径；head 之后的 token 全是运行期参数，不校验。
    head 必须落在 item（叶命令）上——只到 menu 不算完整命令（如 `slb virtual`）。
    """
    root = ET.parse(str(xml_path)).getroot()
    is_item: dict = {}
    children: dict = {}

    def walk(node, prefix):
        for child in node:
            name = (child.get("name") or "").strip().lower()
            if not name:
                continue
            p = prefix + (name,)
            leaf = child.tag == "item"
            if leaf:
                is_item[p] = True
            else:
                is_item.setdefault(p, False)
                walk(child, p)
            children.setdefault(prefix, set()).add(name)

    for scope in root:
        walk(scope, ())
    return is_item, children


def _steps_from_cases(cases_path: Path) -> list[dict]:
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    out = []
    for case in data.get("cases", []):
        for s in case.get("steps", []):
            e = str(s.get("e", "")).strip()
            f = str(s.get("f", "")).strip()
            if e.startswith("APV") and f.startswith("cmd") and str(s.get("g", "")).strip():
                out.append({"autoid": case.get("autoid", ""), **s})
    return out


def _steps_from_xlsx(xlsx: Path) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from openpyxl import load_workbook

    import _cex_path  # noqa: F401,E402 — 发行根进 sys.path

    from cex_core.ist_emit.excel_contract import resolve_execution_sheet

    wb = load_workbook(xlsx, read_only=True, data_only=True)
    ws, _ = resolve_execution_sheet(wb, allow_legacy=False)
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    out, autoid = [], ""
    for row in rows:
        a = str(row[0]).strip() if row and row[0] is not None else ""
        if a.isdigit() and len(a) >= 12 and a != _SENTINEL_AUTOID:
            autoid = a
        e = str(row[4] or "").strip() if len(row) > 4 else ""
        f = str(row[5] or "").strip() if len(row) > 5 else ""
        g = str(row[6] or "").strip() if len(row) > 6 else ""
        if e.startswith("APV") and f.startswith("cmd") and g:
            out.append({"autoid": autoid, "e": e, "f": f, "g": g})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="编译期命令存在性校验（cmdtree grounding）")
    ap.add_argument("--cases")
    ap.add_argument("--xlsx")
    ap.add_argument("--projection", default="", help="命令树投影 JSON（缺省从工作区数据包找）")
    ap.add_argument("--tree", default="", help="原始 cmdtree XML（只在显式给出时使用）")
    args = ap.parse_args()
    if not args.cases and not args.xlsx:
        print(json.dumps({"ok": False, "error": "--cases 或 --xlsx 必填其一"},
                         ensure_ascii=False))
        return 2

    src = Path(args.cases or args.xlsx).expanduser().resolve()
    if not src.exists():
        print(json.dumps({"ok": False, "error": f"输入不存在: {src}"},
                         ensure_ascii=False))
        return 2

    steps = (_steps_from_cases if args.cases else _steps_from_xlsx)(src)
    if not args.tree:
        projection = _find_projection(args.projection, src.parent)
        if projection is None:
            print(json.dumps({
                "ok": False,
                "error": "找不到命令树投影：先 cex_sync 同步数据包，或用 --projection 指定",
            }, ensure_ascii=False))
            return 2
        report = {"schema": REPORT_SCHEMA, "projection": str(projection), "source": str(src),
                  "checked": 0, "ok": 0, "unknown": [], "warnings": []}
        try:
            _check_with_projection(steps, projection, report)
        except ValueError as exc:
            print(json.dumps({"ok": False, "error": f"投影不可用: {exc}"}, ensure_ascii=False))
            return 2
        report["ok_flag"] = not report["unknown"]
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if report["ok_flag"] else 1

    tree_path, build = _find_tree(args.tree)
    if tree_path is None:
        print(json.dumps({"ok": False, "error": f"--tree 指定的文件不存在: {args.tree}"},
                         ensure_ascii=False))
        return 2

    try:
        is_item, children = _tree_paths(tree_path)
    except ET.ParseError as exc:
        print(json.dumps({"ok": False, "error": f"命令树解析失败: {exc}"},
                         ensure_ascii=False))
        return 2

    report = {"schema": REPORT_SCHEMA, "tree": str(tree_path), "tree_build": build,
              "source": str(src), "checked": 0, "ok": 0, "unknown": [], "warnings": []}

    ws = _workspace(src.parent)
    want_build = ws.device_build if ws is not None else ""
    if build and want_build and build.lower() not in want_build.lower():
        report["warnings"].append(
            f"树 build={build} 与工作区 device_build={want_build} 不一致——"
            "树判定可能不代表床固件，建议换对应 build 的树"
        )

    for s in steps:
        cmd = str(s.get("g", "")).strip()
        if not cmd:
            continue
        negated = cmd.lower().startswith("no ")
        probe = cmd[3:].strip() if negated else cmd
        if not probe or probe.lower() in _FRAMEWORK_WORDS:
            report["checked"] += 1
            report["ok"] += 1
            continue
        toks = probe.lower().split()
        # 贪心最深路径；之后的 token 全是参数，不校验
        depth = 0
        for d in range(len(toks), 0, -1):
            if tuple(toks[:d]) in is_item:
                depth = d
                break
        if depth and is_item[tuple(toks[:depth])]:
            report["checked"] += 1
            report["ok"] += 1
            continue
        report["checked"] += 1
        prefix = tuple(toks[:depth]) if depth else ()
        sibs = sorted(children.get(prefix, set()))
        last = toks[depth] if depth < len(toks) else ""
        # 近似优先：前缀命中 / 单复数之差 / 包含关系排前，其余字典序截断
        def _rank(s: str) -> tuple:
            near = (
                s.startswith(last[:3])
                or s.rstrip("s") == last.rstrip("s")
                or last.rstrip("s") in s
            )
            return (0 if near else 1, s)
        sibs = [s for _, s in sorted((_rank(s), s) for s in sibs)][:8]
        report["unknown"].append({
            "autoid": s.get("autoid", ""),
            "command": cmd,
            "match_depth": depth,
            "tokens": len(toks),
            "matched_prefix": " ".join(prefix),
            "reason": "head 只到 menu 不是完整命令" if depth else "head 不在树中",
            "suggestions": sibs,
        })

    report["ok_flag"] = not report["unknown"]
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["ok_flag"] else 1


if __name__ == "__main__":
    sys.exit(main())
