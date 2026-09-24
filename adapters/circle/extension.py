"""compile-excel 的 circle 扩展：经 circle 扩展 API 注册 cex_* 工具。

circle 按 `register(api)` 加载扩展。这里用到的接口：
- `api.register_tool(name, description, parameters, execute, read_only=)`：parameters 是 JSON Schema，
  execute 收参数 dict、返回结果；
- `api.ToolError`：execute 抛它表示这次调用失败，消息原样交给模型并标成错误。

工具说明与参数 schema 直接读 cex_client/tool_specs.json；执行时用子进程调发行根的 bin/cex_tool，
与 pi 扩展、Claude Code 插件走同一个解释器和同一份依赖，circle 自己的进程里不加载 cex_* 代码。
cex_tool 退出码：0 成功（含 pending）；1 工具返回 ok:false；2 用法错误。
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

# 单次调用上限：登录/扫码等待最长 300 秒，一次上机可以更久，按最长的给
TIMEOUT_S = 45 * 60


def dist_root() -> Path:
    """发行根：本文件在 <根>/adapters/circle/ 下；CEX_HOME 可覆盖。"""
    override = os.environ.get("CEX_HOME")
    if override and (Path(override) / "bin" / "cex_tool").is_file():
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def load_specs(root: Path) -> list[dict[str, Any]]:
    return json.loads((root / "cex_client" / "tool_specs.json").read_text(encoding="utf-8"))["tools"]


def make_executor(root: Path, name: str, tool_error: type[Exception]) -> Callable[[dict], dict]:
    python = os.environ.get("CEX_PYTHON") or "python3"
    cex_tool = str(root / "bin" / "cex_tool")

    def execute(args: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            proc = subprocess.run([python, cex_tool, name, json.dumps(args or {}, ensure_ascii=False)],
                                  capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise tool_error(f"{name} timed out after {TIMEOUT_S}s") from None
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            tail = (proc.stderr or proc.stdout)[-800:]
            raise tool_error(f"{name} returned no JSON (exit {proc.returncode}): {tail}") from None
        if proc.returncode != 0:
            raise tool_error(json.dumps(payload, ensure_ascii=False, indent=1))
        return payload

    return execute


def register(api: Any) -> None:
    root = dist_root()
    for spec in load_specs(root):
        api.register_tool(
            name=spec["name"],
            description=spec["description"],
            parameters=spec["input_schema"],
            execute=make_executor(root, spec["name"], api.ToolError),
            read_only=bool(spec.get("read_only")),
        )
