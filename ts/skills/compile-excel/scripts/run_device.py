#!/usr/bin/env python3
"""run_device: 上机 —— 经跳板机网关把 case.xlsx 交给测试框架真跑，取回框架判定。

执行链路：
    工作区 xlsx → 网关（冻结、上机前闸、只读落位、sha 对账）→ 框架 pytest 在被测设备上逐 case 执行
    → 框架结果库记录每个 check_point 的判定 → 本脚本轮询任务终态，取回每个 autoid 的判定。

判定语义归框架：verdict 来自结果库；pytest 的 “1 passed” 不代表断言通过。
凭据：本机只有工作区 OAuth 令牌；跳板机与设备口令只在网关。需要先 cex_bed_lease acquire；
轮询期间每 --heartbeat-s 秒续一次租约。

一投递成功就先往 stderr 打一行 task_id：脚本中途被打断、或等超时了，拿它接着
cex_case_status / cex_case_results，不要重投（重投会再跑一遍整卷）。投递之后的每个失败输出都带 task_id。

用法：
  python3 scripts/run_device.py --xlsx compile_outputs/<batch>/case.xlsx [--module sdns]
      [--max-s 2400] [--poll-s 10] [--heartbeat-s 300]

产出（写在 xlsx 同目录）：run_results.json（机读）、run_receipt.md（人读）。
判定：pass / fail 要有本案日志里框架的收尾作证，否则是 broken（这一轮停在了本案里，库里那行是
占位值）；判 pass 但日志里有本案断言并不在等的执行失败回显，也是 broken（空真）。
退出码：0 = 跑完且全部真实 case pass（fail 0、broken 0、not_run 0）；
        1 = 跑完但有 fail / broken / not_run（或没有任何 case 判定）；
        2 = 没投递上：网关拒收这份工作簿（problems 列出原因）或投递调用本身失败；
        3 = 已投递、--max-s 内没跑完：任务还在跑，按 task_id 轮询 cex_case_status，结束后 cex_case_results；
        4 = 已投递，但轮询或取结果失败：按 task_id 重试 cex_case_status / cex_case_results；
        5 = 已投递，但这一轮丢了（runner 没记下结束就死了：网关重启、OOM、人工 kill）：不会有判定，重投。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _cex_path  # noqa: F401,E402 — 发行根进 sys.path

from cex_client import device, gateway, workspace  # noqa: E402
from cex_client.errors import ClientError  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_REFUSED, EXIT_TIMEOUT, EXIT_FETCH_FAILED, EXIT_LOST = 0, 1, 2, 3, 4, 5


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="case.xlsx 上机（经跳板机网关，框架真跑）")
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--module", default="")
    ap.add_argument("--max-s", type=float, default=2400)
    ap.add_argument("--poll-s", type=float, default=10)
    ap.add_argument("--heartbeat-s", type=float, default=300)
    args = ap.parse_args(argv)
    xlsx = Path(args.xlsx).expanduser().resolve()

    try:
        ws = workspace.require(xlsx.parent)
        submitted = device.submit(ws, str(xlsx), args.module or None)
    except ClientError as exc:
        _emit({"ok": False, "stage": "submit", "error": str(exc)})
        return EXIT_REFUSED
    if not submitted.get("ok") or not submitted.get("task_id"):
        _emit({"ok": False, "stage": "submit",
               **{k: submitted.get(k) for k in ("error", "problems") if submitted.get(k)}})
        return EXIT_REFUSED
    task_id = str(submitted["task_id"])
    print(f"run_device: submitted task_id={task_id} (if this script stops, continue with "
          "cex_case_status / cex_case_results for this task_id; do not resubmit)",
          file=sys.stderr, flush=True)

    deadline = time.monotonic() + max(args.max_s, 0)
    last_beat = time.monotonic()
    finished = False
    try:
        while time.monotonic() < deadline:
            state = device.status(ws, task_id).get("state")
            if state == "lost":
                _emit({"ok": False, "stage": "wait", "task_id": task_id, "state": "lost",
                       "error": device.RUNNER_LOST})
                return EXIT_LOST
            if state == "done":
                finished = True
                break
            if time.monotonic() - last_beat > args.heartbeat_s:
                gateway.lease(ws, "heartbeat")
                last_beat = time.monotonic()
            time.sleep(args.poll_s)
    except ClientError as exc:
        _emit({"ok": False, "stage": "status", "task_id": task_id, "error": str(exc)})
        return EXIT_FETCH_FAILED
    if not finished:
        _emit({"ok": False, "stage": "wait", "task_id": task_id,
               "error": (f"the run did not finish within {int(args.max_s)}s and is still going; poll "
                         "cex_case_status with this task_id, then cex_case_results")})
        return EXIT_TIMEOUT

    try:
        out = device.results(ws, task_id)
    except ClientError as exc:
        _emit({"ok": False, "stage": "results", "task_id": task_id, "error": str(exc)})
        return EXIT_FETCH_FAILED
    if not out.get("ok") or "totals" not in out:
        _emit({"ok": False, "stage": "results", "task_id": task_id,
               **{k: out.get(k) for k in ("error", "problems", "channel") if out.get(k)}})
        return EXIT_FETCH_FAILED
    t = out["totals"]
    ok = t["fail"] == 0 and t.get("broken", 0) == 0 and t["not_run"] == 0 and t["cases"] > 0
    _emit({"ok": ok, "totals": t, "task_id": task_id, "rc": out.get("rc"),
           "result_channel": out.get("channel"), "receipt": out.get("receipt")})
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
