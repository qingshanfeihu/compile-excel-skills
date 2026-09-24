#!/usr/bin/env python3
"""login：OAuth2 设备授权流登录（工作流 B）。

用法：python login.py [--no-browser]
token 落 ~/.config/compile-excel/token（0600）；可用
$COMPILE_EXCEL_SERVER 指定服务器（缺省 http://127.0.0.1:8900）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ist_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="compile-excel 设备授权登录")
    parser.add_argument("--no-browser", action="store_true", help="不自动开浏览器")
    args = parser.parse_args()

    try:
        flow = ist_client.device_authorize()
    except (ist_client.ClientError, ConnectionError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    verification_uri = flow.get("verification_uri_complete") or flow["verification_uri"]
    device_code = flow["user_code"]
    print(f"设备码：{device_code}", flush=True)
    print(f"DEVICE_FLOW user_code={device_code} verification_uri={verification_uri}",
          flush=True)

    # 默认自动开浏览器（授权页已带设备码，用户只需点【授权】）；
    # 打不开/选择不开时给出手动力指引，不阻塞轮询。
    browser_opened = False
    if not args.no_browser:
        try:
            browser_opened = webbrowser.open(verification_uri)
        except Exception:  # noqa: BLE001 — 打不开浏览器不影响流程
            browser_opened = False
    if browser_opened:
        print(f"已打开浏览器授权页（若未弹出请手动访问）：\n  {verification_uri}\n"
              f"在页面点击【授权】后，终端会自动继续。", flush=True)
    else:
        print(f"请手动打开以下 URL 完成授权（页面点击【授权】后终端自动继续）：\n"
              f"  {verification_uri}", flush=True)

    pending_shown = False

    def _pending() -> None:
        nonlocal pending_shown
        if not pending_shown:
            print("等待授权中…（在授权页点击【授权】；Ctrl+C 取消）", flush=True)
            pending_shown = True

    try:
        issued = ist_client.poll_device_token(
            flow["device_code"],
            interval=int(flow.get("interval") or 1),
            expires_in=int(flow.get("expires_in") or 600),
            on_pending=_pending,
        )
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": "已取消（未完成授权，未写入 token）"},
                         ensure_ascii=False))
        return 130
    except (ist_client.ClientError, ConnectionError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    ist_client.save_token({
        "access_token": issued["access_token"],
        "refresh_token": issued.get("refresh_token", ""),
        "expires_at": int(time.time()) + int(issued.get("expires_in") or 900),
        "server": ist_client.server_url(),
    })
    result = {
        "ok": True,
        "server": ist_client.server_url(),
        "token_path": str(ist_client.TOKEN_PATH),
        "expires_in": issued.get("expires_in"),
        "scope": issued.get("scope", ""),
    }
    # 单行紧凑 JSON（机器可读；多行会破坏调用方按行解析）
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
