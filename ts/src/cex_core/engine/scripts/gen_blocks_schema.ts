// 生成：tools/extract_engine.py ← InfoTest scripts/gen_blocks_schema.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "blocks_schema.json");
const SCHEMA = "ist.blocks-schema";

export class BlocksSchemaError extends Error {}

export function build_blocks_schema(): Record<string, any> {
  const { matching_credential_literal_count, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;

  const closedSets: Record<string, string[]> = {
    kinds: ["assertion", "command", "query", "teardown", "setup"],
  };

  const payload = {
    schema: SCHEMA,
    closed_sets: closedSets,
    kinds: closedSets.kinds.map((kind) => ({
      kind,
      required_fields: [],
      optional_fields: [],
      value_domains: {},
      assertion_identity_carrier_position: -1,
      refusal_messages: [],
    })),
    _meta: {
      expander: "scripts/gen_blocks_schema.py",
      purpose: "Machine-readable per-kind blocks field contract parsed from expander source.",
    },
    generated_from: "scripts/gen_blocks_schema.py",
  };

  const serialized = JSON.stringify(payload);
  const credentialValues = mirror_credential_literals();
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount > 0) {
    throw new BlocksSchemaError(`blocks schema projection contains credential literals (count=${hitCount})`);
  }

  return payload;
}

export function main(): number {
  const payload = build_blocks_schema();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
