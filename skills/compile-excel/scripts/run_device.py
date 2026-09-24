#!/usr/bin/env python3
"""run_device: 上机 —— 经跳板机网关把 case.xlsx 交给测试框架真跑，取回框架判定。

执行链路：
    工作区 xlsx → 网关（冻结、上机前闸、只读落位、sha 对账）→ 框架 pytest 在被测设备上逐 case 执行
    → 框架结果库记录每个 check_point 的判定 → 本脚本轮询任务终态，取回每个 autoid 的判定。

判定语义归框架：verdict 来自结果库；pytest 的 “1 passed” 不代表断言通过。
凭据：本机只有工作区 OAuth 令牌；跳板机与设备口令只在网关。需要先 cex_bed_lease acquire。

用法：
  python3 scripts/run_device.py --xlsx compile_outputs/<batch>/case.xlsx [--module sdns]
      [--max-s 2400] [--poll-s 10]

产出（写在 xlsx 同目录）：run_results.json（机读）、run_receipt.md（人读）。
退出码：0 = 全部真实 case pass；1 = 存在 fail/not_run；2 = 递交/协议层失败。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _cex_path  # noqa: F401,E402 — 发行根进 sys.path

from cex_client import device, workspace  # noqa: E402
from cex_client.errors import ClientError  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="case.xlsx 上机（经跳板机网关，框架真跑）")
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--module", default="")
    ap.add_argument("--max-s", type=int, default=2400)
    ap.add_argument("--poll-s", type=float, default=10)
    args = ap.parse_args()
    xlsx = Path(args.xlsx).expanduser().resolve()
    try:
        ws = workspace.require(xlsx.parent)
        out = device.run_and_wait(ws, str(xlsx), module=args.module or None,
                                  poll_s=args.poll_s, max_s=args.max_s)
    except ClientError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    if not out.get("ok") or "totals" not in out:
        print(json.dumps({"ok": False, **{k: out.get(k) for k in ("error", "problems", "task_id")
                                          if out.get(k)}}, ensure_ascii=False))
        return 2
    t = out["totals"]
    ok = t["fail"] == 0 and t["not_run"] == 0 and t["cases"] > 0
    print(json.dumps({"ok": ok, "totals": t, "task_id": out.get("task_id"),
                      "result_channel": out.get("channel"), "receipt": out.get("receipt")},
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
