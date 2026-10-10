// 生成：tools/extract_engine.py ← InfoTest scripts/gen_rule_registry.py（sha256 b2efe0c8ab25d765）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "rule_registry.json");
const SCHEMA = "ist.rule-registry";

export function build_rule_registry(): Record<string, any> {
  // 简化实现：从 engine_track_schema 提取规则信息
  const { ENGINE_TRACK_SCHEMAS } = require("../common/engine_track_schema") as any;
  const rules: Array<Record<string, any>> = [];
  for (const [schemaName, decl] of Object.entries(ENGINE_TRACK_SCHEMAS as Record<string, any>)) {
    if (schemaName.includes("rule") || schemaName.includes("criterion")) {
      rules.push({
        id: schemaName,
        schema: schemaName,
        description: decl.description ?? "",
        version: decl.version ?? "",
      });
    }
  }
  return {
    schema: SCHEMA,
    rules,
    rule_count: rules.length,
    generated_from: "cex_core/engine/common/engine_track_schema.ts",
  };
}

export function main(): number {
  const payload = build_rule_registry();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
