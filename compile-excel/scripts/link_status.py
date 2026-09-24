#!/usr/bin/env python3
"""link_status: skill 链接时检查 OAuth 和设备口令是否已经齐。

不打印任何机密值。缺什么就在 JSON 的 ask 里列出，交给 question 工具去问用户。

退出码：
  0  OAuth 可用，设备用户名和密码都在
  2  还没有环境绑定
  3  需要做 OAuth（login.py）
  4  需要向用户要设备用户名/密码
  5  OAuth 和设备口令都缺
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ist_client  # noqa: E402
from preflight import load_env  # noqa: E402

# 设备口令。都走机密通道，不进对话。用户名不掩码，密码掩码。
DEVICE_ASKS = (
    ("APV_USER", "设备用户名", True, False),
    ("APV_PASSWORD", "设备密码", True, True),
)


def _oauth_state() -> dict:
    try:
        token = ist_client.load_token()
    except ist_client.ClientError as exc:
        return {"ok": False, "reason": str(exc)}
    if not token.get("access_token"):
        return {"ok": False, "reason": "未登录，需要运行 login.py 完成设备授权"}
    expires_at = int(token.get("expires_at") or 0)
    if expires_at and expires_at < time.time() + 30:
        return {"ok": False, "reason": "token 已过期，需要重新 login"}
    return {"ok": True, "reason": "token 有效", "server": token.get("server") or ""}


def main() -> int:
    env, source = load_env()
    if source is None:
        print(json.dumps({
            "ok": False,
            "env_source": None,
            "oauth": {"ok": False, "reason": "未绑定环境"},
            "device_credentials": {"ok": False, "missing": [k for k, _, _, _ in DEVICE_ASKS]},
            "ask": [],
            "target_file": str(Path.home() / ".config" / "compile-excel" / "env"),
            "hint": "先走 SKILL.md 的环境绑定，再重新跑 link_status.py",
        }, ensure_ascii=False, indent=2))
        return 2

    target = source
    missing = [key for key, _, _, _ in DEVICE_ASKS if not env.get(key)]
    asks = [
        {
            "question": question,
            "key": key,
            "secret": secret,
            "mask": mask,
            "target_file": str(target),
        }
        for key, question, secret, mask in DEVICE_ASKS
        if key in missing
    ]
    oauth = _oauth_state()
    ok = bool(oauth["ok"]) and not missing
    messages: list[str] = []
    run: list[dict] = []
    if not oauth["ok"]:
        messages.append(f"需要重新登录：{oauth['reason']}")
        run.append({
            "script": "scripts/login.py",
            "args": ["--no-browser"],
            "status_marker": "verification_uri=",
            "status_prefix": "请打开授权页重新登录：",
            "ok_status": "重新登录完成",
            "fail_status": "重新登录未完成",
        })
    prompt = "请在下方输入设备用户名，然后是设备密码。密码不显示。" if asks else ""
    print(json.dumps({
        "ok": ok,
        "env_source": str(source),
        "oauth": oauth,
        "device_credentials": {"ok": not missing, "missing": missing},
        "messages": messages,
        "prompt": prompt,
        "run": run,
        "ask": asks,
        "target_file": str(target),
        "hint": "" if ok else "按 messages 重新登录；按 ask 向用户要设备用户名和密码",
    }, ensure_ascii=False, indent=2))
    if ok:
        return 0
    if not oauth["ok"] and missing:
        return 5
    if not oauth["ok"]:
        return 3
    return 4


if __name__ == "__main__":
    sys.exit(main())
