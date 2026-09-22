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
    except ist_client.ClientError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    except ConnectionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    verification_uri = flow.get("verification_uri_complete") or flow["verification_uri"]
    print(f"请在浏览器完成授权：{verification_uri}", flush=True)
    print(f"设备码：{flow['user_code']}", flush=True)
    print(f"DEVICE_FLOW user_code={flow['user_code']} verification_uri={verification_uri}",
          flush=True)
    if not args.no_browser:
        try:
            webbrowser.open(verification_uri)
        except Exception:  # noqa: BLE001 — 打不开浏览器不影响流程
            pass

    def _pending() -> None:
        print("等待授权中…（在浏览器页面点击授权）", flush=True)

    try:
        issued = ist_client.poll_device_token(
            flow["device_code"],
            interval=int(flow.get("interval") or 1),
            expires_in=int(flow.get("expires_in") or 600),
            on_pending=_pending,
        )
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
