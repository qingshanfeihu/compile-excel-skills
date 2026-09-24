#!/usr/bin/env python3
"""preflight: 环境绑定检查（读 env → 校验键完整性 → TCP 探活）。

设计原则：
- 非交互：只输出结构化 JSON，问答是 agent（Setup 向导）的事
- 三级查找：$COMPILE_EXCEL_ENV → <cwd>/.circle/compile-excel.env → ~/.config/compile-excel/env
- 退出码：0 = 可编译；2 = 未绑定（需走 Setup）；1 = 探活失败

用法：python preflight.py [--quiet]
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

REQUIRED_KEYS = ("KMS_ADDR", "JUMPHOST_IP")
OPTIONAL_DEFAULTS = {"JUMPHOST_PORT": "22"}


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get("COMPILE_EXCEL_ENV")
    if explicit:
        paths.append(Path(explicit).expanduser())
    paths.append(Path.cwd() / ".circle" / "compile-excel.env")
    paths.append(Path.home() / ".config" / "compile-excel" / "env")
    return paths


def load_env() -> tuple[dict[str, str], Path | None]:
    for path in _candidate_paths():
        if path.is_file():
            data: dict[str, str] = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                data[key.strip()] = value.strip()
            return data, path
    return {}, None


def _tcp_check(label: str, host: str, port: int, timeout: float = 3.0) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"name": label, "ok": True, "detail": f"{host}:{port} 可连接"}
    except OSError as exc:
        return {"name": label, "ok": False, "detail": f"{host}:{port} 不可达: {exc}"}


def _split_host_port(raw: str, default_port: int) -> tuple[str, int]:
    host, sep, port = raw.partition(":")
    return host.strip(), (int(port) if sep else default_port)


def main() -> int:
    env, source = load_env()
    checks: list[dict] = []

    if source is None:
        print(json.dumps({
            "ok": False,
            "env_source": None,
            "missing": list(REQUIRED_KEYS),
            "checks": [],
            "hint": "未找到环境绑定，请走 SKILL.md 的 Setup 流程",
        }, ensure_ascii=False, indent=2))
        return 2

    missing = [key for key in REQUIRED_KEYS if not env.get(key)]
    for key, value in OPTIONAL_DEFAULTS.items():
        env.setdefault(key, value)

    if missing:
        print(json.dumps({
            "ok": False,
            "env_source": str(source),
            "missing": missing,
            "checks": [],
            "hint": "env 文件缺少必填键，请补全后重跑",
        }, ensure_ascii=False, indent=2))
        return 2

    kms_host, kms_port = _split_host_port(env["KMS_ADDR"], 443)
    checks.append(_tcp_check("kms", kms_host, kms_port))
    jump_host, jump_port = _split_host_port(env["JUMPHOST_IP"], int(env["JUMPHOST_PORT"]))
    checks.append(_tcp_check("jumphost", jump_host, jump_port))

    ok = all(c["ok"] for c in checks)
    print(json.dumps({
        "ok": ok,
        "env_source": str(source),
        "missing": [],
        "checks": checks,
        "hint": "" if ok else "探活未通过，修正 env 后重跑；禁止带病编译",
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
