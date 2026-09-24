#!/usr/bin/env python3
"""run_device: 上机 —— 把 case.xlsx 递交跳板机 pytest 框架真跑，取回框架判定。

这是 compile-excel 的「上机」阶段。excel 不是由本脚本解释执行：本脚本只是
InfoTest 引擎 FrameworkMCPClient 的无头驱动，真实执行链路是——

    本地 xlsx → SFTP 落到跳板机 ist_staging_<module>/<autoid>/case.xlsx
    → 框架把 xlsx 转成 test_xlsx.py → pytest 在被测 APV 上逐 case 执行
    → 每个 check_point 的判定写入框架 result DB
    → 本脚本轮询任务终态，从 result DB 取回每个 autoid 的判定（fail-closed）。

判定语义归框架：verdict 来自 result DB（pass 要求 fail==0 且 success>0），
pytest 的 === 1 passed === 不代表断言通过。非 pass 的 case 附框架日志尾部
（fetch_case_detail）作为归因证据。

凭据全部来自 ~/.config/compile-excel/env（跳板机 + 设备），不进对话、不进日志。

用法：
  python3 scripts/run_device.py --xlsx compile_outputs/<batch>/case.xlsx \
      [--env ~/.config/compile-excel/env] [--max-s 900] [--poll-s 10]

产出（写在 xlsx 同目录）：
  run_results.json   机读：逐 case 框架判定 + 日志尾证 + result channel 状态
  run_receipt.md     人读：上机回执
退出码：0 = 全部真实 case pass；1 = 存在 fail/not_run；2 = 递交/协议层失败。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
# 上机阶段暂借 InfoTest 的框架客户端（Phase 1 起改走跳板机网关）。引擎根只从
# 进程环境或 env 绑定里的 IST_ENGINE_ROOT 读，不再写死任何个人机器路径。
_ENGINE_CLIENT = Path("main") / "case_compiler" / "device_mcp_client.py"


def resolve_engine_root(env: dict) -> Path | None:
    raw = (os.environ.get("IST_ENGINE_ROOT") or env.get("IST_ENGINE_ROOT") or "").strip()
    if not raw:
        return None
    root = Path(raw).expanduser()
    return root if (root / _ENGINE_CLIENT).is_file() else None

RESULT_SCHEMA = "ist.excel.device-run-result"
SENTINEL_AUTOID = "999999999999999"

# 归因初版：机械标记先行，语义层不越权（对齐引擎四层归因的可静态判定子集）
_G_LAYER_MARKERS = (
    "% invalid", "% unrecognized", "% unknown", "% error",
    "syntax error", "invalid input", "command not found",
)
_TRANSIENT_MARKERS = (
    "timeout", "timed out", "read_until", "connection reset",
    "connection closed", "device_busy", "traceback", "not reachable",
)


def attribute_fail(detail_tail: str) -> dict:
    """非 pass 的机械归因：G（命令/语法层）· transient 疑似 · undetermined。

    只判协议级事实；G/E/V 语义裁决留给会话（引擎口径：机械预判只断协议事实）。
    """
    text = (detail_tail or "").lower()
    for m in _G_LAYER_MARKERS:
        if m in text:
            return {"layer": "G", "evidence": m,
                    "note": "命令/语法层——回显含 CLI 错误标记"}
    for m in _TRANSIENT_MARKERS:
        if m in text:
            return {"layer": "transient?", "evidence": m,
                    "note": "疑似瞬态（超时/连接/忙）——同签名复发则非瞬态，不升格"}
    return {"layer": "undetermined", "evidence": "",
            "note": "机械标记无法裁决，需会话按 detail_tail 语义归因（E/V/产品缺陷）"}


def _utcnow() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def load_env(env_path: Path) -> dict:
    env = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


REQUIRED_ENV = ("JUMPHOST_USER", "JUMPHOST_PASS", "RUN_JUMPHOST_IP")


def apply_engine_env(env: dict) -> None:
    """把 skill 绑定映射成引擎 IST_* 环境变量（已存在的显式值不覆盖）。"""
    mapping = {
        "IST_JUMPHOST_HOST": env.get("RUN_JUMPHOST_IP") or env.get("JUMPHOST_IP", ""),
        "IST_JUMPHOST_USER": env.get("JUMPHOST_USER", ""),
        "IST_JUMPHOST_PASS": env.get("JUMPHOST_PASS", ""),
        "IST_DEVICE_BUILD": env.get("IST_DEVICE_BUILD", ""),
        "APV_PASSWORD": env.get("APV_PASSWORD", ""),
    }
    for key, value in mapping.items():
        if value and not os.environ.get(key):
            os.environ[key] = value


def autoids_from_xlsx(xlsx: Path) -> list[str]:
    """从执行表读全部真实 case autoid（≥12 位数字，哨兵除外）。"""
    from openpyxl import load_workbook

    import _cex_path  # noqa: F401,E402 — 发行根进 sys.path

    from cex_core.ist_emit.excel_contract import EXECUTION_HEADERS, resolve_execution_sheet

    wb = load_workbook(xlsx, read_only=True, data_only=True)
    ws, _ = resolve_execution_sheet(wb, allow_legacy=False)
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    autoids = []
    for row in rows:
        a = str(row[0]).strip() if row and row[0] is not None else ""
        if a.isdigit() and len(a) >= 12 and a != SENTINEL_AUTOID and a not in autoids:
            autoids.append(a)
    return autoids


def write_receipts(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    t = result["totals"]
    lines = [
        "# 上机回执（run_receipt）",
        "",
        f"- batch: `{result['batch']}`",
        f"- xlsx: `{result['xlsx']}` (sha256 `{result['xlsx_sha256'][:16]}…`)",
        f"- bed: jumphost `{result['jumphost']}` · module `{result['module']}` · build `{result['build']}`",
        f"- task_id: `{result.get('task_id', '')}`",
        f"- 时间: {result['started']} → {result['finished']}",
        f"- 总数: {t['cases']} · pass {t['pass']} · fail {t['fail']} · not_run {t['not_run']}",
        f"- result channel: {json.dumps(result.get('result_channel', {}), ensure_ascii=False)}",
        "",
        "| autoid | 框架判定 | 证据摘录 |",
        "|---|---|---|",
    ]
    for c in result["cases"]:
        note = (c.get("detail_tail") or c.get("note") or "").replace("\n", " ⏎ ")[:160]
        att = c.get("attribution") or {}
        if att.get("layer"):
            note = f"[{att['layer']}] {note}"
        lines.append(f"| {c['autoid']} | {c['verdict']} | {note or '-'} |")
    (out_dir / "run_receipt.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _bootstrap_interpreter() -> None:
    """引擎代码需要 py≥3.10 + paramiko；不满足时自动换合适的解释器重执行。"""
    if os.environ.get("_RUN_DEVICE_REEXEC") == "1":
        return
    ok = sys.version_info >= (3, 10)
    if ok:
        try:
            import paramiko  # noqa: F401
        except Exception:
            ok = False
    if ok:
        return
    candidates = [
        os.environ.get("RUN_DEVICE_PYTHON", ""),
        # InfoTest 约定的仓外 venv（引擎依赖齐全）
        str(Path.home() / ".venvs" / "infotest-engine" / "bin" / "python"),
    ]
    for py in filter(None, candidates):
        if not os.path.exists(py):
            continue
        env = dict(os.environ, _RUN_DEVICE_REEXEC="1")
        os.execve(py, [py, str(Path(__file__).resolve()), *sys.argv[1:]], env)
    raise SystemExit(
        "找不到带 paramiko 的 py>=3.10 解释器；请先安装（pip install paramiko）"
        "或用 RUN_DEVICE_PYTHON 指定。"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="case.xlsx 上机（框架真跑）")
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--env", default=str(Path.home() / ".config/compile-excel/env"))
    ap.add_argument("--max-s", type=int, default=900,
                    help="整卷轮询预算秒数（默认 900；按 case 数自动抬到 N×45s，上限 2400）")
    ap.add_argument("--poll-s", type=int, default=10)
    args = ap.parse_args()

    _bootstrap_interpreter()

    xlsx = Path(args.xlsx).expanduser().resolve()
    if not xlsx.exists():
        print(json.dumps({"ok": False, "error": f"xlsx 不存在: {xlsx}"},
                         ensure_ascii=False))
        return 2
    env = load_env(Path(args.env).expanduser())
    missing = [k for k in REQUIRED_ENV if not env.get(k)]
    if missing:
        print(json.dumps({"ok": False, "error": f"env 缺少 {missing}（{args.env}）"},
                         ensure_ascii=False))
        return 2
    apply_engine_env(env)

    engine_root = resolve_engine_root(env)
    if engine_root is None:
        print(json.dumps({
            "ok": False,
            "error": ("上机阶段暂时依赖 InfoTest 的框架客户端：请在 env 绑定里加一行 "
                      "IST_ENGINE_ROOT=<InfoTest 仓路径>（该路径下需有 "
                      f"{_ENGINE_CLIENT.as_posix()}）。跳板机网关上线后不再需要。"),
        }, ensure_ascii=False))
        return 2
    # 引擎代码以源码树方式导入（不要求 pip install）
    sys.path.insert(0, str(engine_root))
    if str(SKILL_DIR / "scripts") not in sys.path:
        sys.path.insert(0, str(SKILL_DIR / "scripts"))

    data = xlsx.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    autoids = autoids_from_xlsx(xlsx)
    if not autoids:
        print(json.dumps({"ok": False, "error": "执行表里没有真实 case autoid"},
                         ensure_ascii=False))
        return 2

    from main.case_compiler.config import get_config
    from main.case_compiler.device_mcp_client import FrameworkMCPClient
    from main.case_compiler.staging_module_gate import resolve_staging_module

    cfg = get_config()
    build = (os.environ.get("IST_DEVICE_BUILD") or cfg.build).strip()
    try:
        module = resolve_staging_module(data, requested_module=cfg.staging_module,
                                        explicit_module="")
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": f"staging module 解析失败: {exc}"},
                         ensure_ascii=False))
        return 2

    max_s = max(args.max_s, len(autoids) * 45)
    max_s = min(max_s, 2400)

    result = {
        "schema": RESULT_SCHEMA,
        "xlsx": str(xlsx),
        "xlsx_sha256": sha256,
        "batch": xlsx.parent.name,
        "module": str(module),
        "build": build,
        "jumphost": os.environ["IST_JUMPHOST_HOST"],
        "started": _utcnow(),
        "cases": [],
    }

    submit = autoids[0]
    run: dict = {}
    try:
        with FrameworkMCPClient() as client:
            result["jumphost"] = str(getattr(client, "host", result["jumphost"]))
            contract = client.preflight_contract()
            if not (isinstance(contract, dict) and contract.get("ok") is True):
                print(json.dumps({
                    "ok": False,
                    "error": "framework result contract preflight failed",
                    "contract": contract,
                }, ensure_ascii=False))
                return 2

            dres = client.deliver_bytes(str(module), submit, data)
            if dres.get("error"):
                print(json.dumps({"ok": False,
                                  "error": f"deliver failed: {dres['error']}"},
                                 ensure_ascii=False))
                return 2
            remote_sha = str(dres.get("sha256") or "").lower()
            if remote_sha != sha256 or dres.get("bytes") != len(data):
                print(json.dumps({
                    "ok": False,
                    "error": "remote staging receipt mismatch",
                    "local_sha256": sha256, "remote": dres,
                }, ensure_ascii=False))
                return 2
            result["module"] = str(dres.get("module") or module)

            run = client.run_and_wait(str(module), submit, build,
                                      case_ids=autoids,
                                      poll_s=args.poll_s, max_s=max_s)

            # 非 pass：机械归因初版 + 框架日志尾证据
            results = run.get("results") if isinstance(run.get("results"), dict) else {}
            for autoid in autoids:
                verdict = str(results.get(autoid, "not_run"))
                entry = {"autoid": autoid, "verdict": verdict}
                if verdict != "pass":
                    try:
                        entry["detail_tail"] = client.fetch_case_detail(autoid)
                    except Exception:
                        entry["detail_tail"] = (run.get("log_tail") or "")[-600:]
                    entry["attribution"] = attribute_fail(entry["detail_tail"])
                result["cases"].append(entry)
    except Exception as exc:  # 连接/协议层失败
        print(json.dumps({"ok": False,
                          "error": f"框架递交/执行失败: {type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2

    result["task_id"] = str(run.get("task_id", ""))
    result["result_channel"] = run.get("result_channel", {})
    verdicts = [c["verdict"] for c in result["cases"]]
    layers: dict[str, int] = {}
    for c in result["cases"]:
        att = c.get("attribution")
        if att:
            layers[att["layer"]] = layers.get(att["layer"], 0) + 1
    if layers:
        result["attribution_totals"] = layers
    result["finished"] = _utcnow()
    result["totals"] = {
        "cases": len(verdicts),
        "pass": sum(1 for v in verdicts if v == "pass"),
        "fail": sum(1 for v in verdicts if v == "fail"),
        "not_run": sum(1 for v in verdicts if v not in ("pass", "fail")),
    }
    write_receipts(result, xlsx.parent)
    t = result["totals"]
    ok = t["fail"] == 0 and t["not_run"] == 0 and t["cases"] > 0
    print(json.dumps({"ok": ok, "totals": t, "task_id": result["task_id"],
                      "receipt": str(xlsx.parent / "run_receipt.md")},
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
