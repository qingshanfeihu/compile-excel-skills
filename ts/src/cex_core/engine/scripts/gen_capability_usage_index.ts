// 生成：tools/extract_engine.py ← InfoTest scripts/gen_capability_usage_index.py（sha256 21ed7a23c7bf7a03）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "capability_usage_index.json");
const SCHEMA = "ist.capability-usage-index";

export class CapabilityUsageIndexError extends Error {}

export function build_usage_index(): Record<string, any> {
  const { load_receipt_directory, passed_receipt_groups } = require("../case_compiler/excel_capability_receipts") as any;
  const { matching_credential_literal_count, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;

  const receipts = load_receipt_directory();
  const passedGroups = passed_receipt_groups(receipts);

  const usage: Record<string, any> = {};
  for (const group of passedGroups) {
    const [e, f] = group.split(":");
    if (!usage[e]) {
      usage[e] = { count: 0, fs: [] };
    }
    usage[e].count += 1;
    usage[e].fs.push(f);
  }

  const payload = {
    schema: SCHEMA,
    usage,
    total_groups: passedGroups.size,
    unique_es: Object.keys(usage).length,
    generated_from: "scripts/gen_capability_usage_index.py",
  };

  const serialized = JSON.stringify(payload);
  const credentialValues = mirror_credential_literals();
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount > 0) {
    throw new CapabilityUsageIndexError(`capability usage index contains credential literals (count=${hitCount})`);
  }

  return payload;
}

export function main(): number {
  const payload = build_usage_index();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
