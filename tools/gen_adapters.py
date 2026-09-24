#!/usr/bin/env python3
"""从 cex_client/tool_specs.json 生成适配器里需要静态 schema 的那部分（改工具先改 specs，再跑本脚本）。

  python3 tools/gen_adapters.py [--check]

- adapters/pi/tools.generated.ts：pi 扩展的 TypeBox 参数定义与说明。
Claude Code 插件（stdio MCP 代理）与 circle 扩展在运行时直接读 tool_specs.json，不需要生成。
--check 只比对不写，有差异退出码 1（tests/test_adapters.py 用它）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SPECS = REPO_ROOT / "cex_client" / "tool_specs.json"
PI_OUT = REPO_ROOT / "adapters" / "pi" / "tools.generated.ts"

_HEADER = """\
// 由 tools/gen_adapters.py 从 cex_client/tool_specs.json 生成，不在这里手改（--check 查漂移）。
import { StringEnum } from "@mariozechner/pi-ai";
import { type TSchema, Type } from "typebox";

export interface CexToolSpec {
\tname: string;
\tlabel: string;
\tdescription: string;
\tsnippet: string;
\treadOnly: boolean;
\tparameters: TSchema;
}

"""


def _options(schema: dict[str, Any], keys: tuple[str, ...]) -> str:
    picked = {k: schema[k] for k in keys if k in schema}
    return json.dumps(picked, ensure_ascii=False) if picked else ""


def _typebox(schema: dict[str, Any]) -> str:
    kind = schema.get("type")
    known = {"type", "description", "enum", "minimum", "maximum", "items", "maxItems"}
    unknown = set(schema) - known
    if unknown:
        raise SystemExit(f"tool_specs 用了生成器不认识的 schema 字段 {sorted(unknown)}，先扩展本脚本")
    if kind == "string" and "enum" in schema:
        values = json.dumps(schema["enum"], ensure_ascii=False)
        opts = _options(schema, ("description",))
        return f"StringEnum({values} as const{', ' + opts if opts else ''})"
    simple = {"string": "String", "number": "Number", "integer": "Integer", "boolean": "Boolean"}
    if kind in simple:
        opts = _options(schema, ("description", "minimum", "maximum"))
        return f"Type.{simple[kind]}({opts})"
    if kind == "array":
        opts = _options(schema, ("description", "maxItems"))
        return f"Type.Array({_typebox(schema['items'])}{', ' + opts if opts else ''})"
    if kind == "object" and "properties" not in schema:
        # 不定形对象（如机械脑图的案）：字段由工具那头的判据核，不在 schema 里重复一份
        opts = _options(schema, ("description",))
        return f"Type.Record(Type.String(), Type.Unknown(){', ' + opts if opts else ''})"
    raise SystemExit(f"tool_specs 用了生成器不认识的类型 {kind!r}，先扩展本脚本")


def _parameters(schema: dict[str, Any], indent: str) -> str:
    if schema.get("type") != "object":
        raise SystemExit("每个工具的 input_schema 必须是 object")
    required = set(schema.get("required") or [])
    lines = []
    for name, prop in schema["properties"].items():
        expr = _typebox(prop)
        if name not in required:
            expr = f"Type.Optional({expr})"
        lines.append(f"{indent}\t{json.dumps(name)}: {expr},")
    closing = (", { additionalProperties: false }"
               if schema.get("additionalProperties") is False else "")
    return "Type.Object({\n" + "\n".join(lines) + f"\n{indent}}}{closing})"


def _label(name: str) -> str:
    words = name.removeprefix("cex_").replace("_", " ")
    return "CEX " + words


def _snippet(description: str) -> str:
    first = description.split(". ", 1)[0].rstrip(".")
    return first + "."


def render_pi(specs: list[dict[str, Any]]) -> str:
    out = [_HEADER, "export const CEX_TOOLS: CexToolSpec[] = [\n"]
    for spec in specs:
        out.append("\t{\n")
        out.append(f"\t\tname: {json.dumps(spec['name'])},\n")
        out.append(f"\t\tlabel: {json.dumps(_label(spec['name']))},\n")
        out.append(f"\t\tdescription: {json.dumps(spec['description'], ensure_ascii=False)},\n")
        out.append(f"\t\tsnippet: {json.dumps(_snippet(spec['description']), ensure_ascii=False)},\n")
        out.append(f"\t\treadOnly: {'true' if spec.get('read_only') else 'false'},\n")
        out.append(f"\t\tparameters: {_parameters(spec['input_schema'], chr(9) * 2)},\n")
        out.append("\t},\n")
    out.append("];\n")
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 tool_specs.json 生成适配器 schema")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    specs = json.loads(SPECS.read_text(encoding="utf-8"))["tools"]
    wanted = {PI_OUT: render_pi(specs)}
    drift = []
    for path, content in wanted.items():
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        drift.append(path.relative_to(REPO_ROOT).as_posix())
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    for rel in drift:
        print(("不一致: " if args.check else "已生成: ") + rel)
    return 1 if (args.check and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
