// 生成：tools/extract_engine.py ← InfoTest scripts/gen_criterion_rules.py（sha256 f7915346876f1389）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "criterion_rules.json");
const SCHEMA = "ist.criterion-rules";

export class CriterionRulesError extends Error {}

export function build_criterion_rules(): Record<string, any> {
  const { ENGINE_TRACK_SCHEMAS } = require("../common/engine_track_schema") as any;
  const { matching_credential_literal_count, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;

  const rules: Array<Record<string, any>> = [];
  for (const [name, decl] of Object.entries(ENGINE_TRACK_SCHEMAS as Record<string, any>)) {
    if (name.includes("criterion") || name.includes("rule")) {
      rules.push({
        criterion_type: name,
        schema: name,
        description: decl.description ?? "",
        version: decl.version ?? "",
      });
    }
  }

  const payload = {
    schema: SCHEMA,
    criterion_types: rules.map((r) => r.criterion_type),
    rules,
    pending_proposals: [],
    rule_count: rules.length,
    generated_from: "scripts/gen_criterion_rules.py",
  };

  const serialized = JSON.stringify(payload);
  const credentialValues = mirror_credential_literals();
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount > 0) {
    throw new CriterionRulesError(`criterion rules projection contains credential literals (count=${hitCount})`);
  }

  return payload;
}

export function main(): number {
  const payload = build_criterion_rules();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
