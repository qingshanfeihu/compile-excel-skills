// 生成：tools/extract_engine.py ← InfoTest scripts/gen_device_behavior_examples.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "device_behavior_examples.json");
const SCHEMA = "ist.device-behavior-examples";

export class DeviceBehaviorExamplesError extends Error {}

export function build_behavior_examples(): Record<string, any> {
  const { load_vendor_stdlib } = require("../case_compiler/vendor_stdlib") as any;
  const { matching_credential_literal_count, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;

  const inventory = load_vendor_stdlib();
  if (!inventory || typeof inventory !== "object") {
    throw new DeviceBehaviorExamplesError("vendor stdlib is unavailable");
  }

  const headers = inventory.headers ?? {};
  const entries: Array<Record<string, any>> = [];
  for (const [head, entry] of Object.entries(headers)) {
    if (typeof entry !== "object" || entry === null) {
      continue;
    }
    entries.push({
      id: head.replace(/\s+/g, "_").toLowerCase(),
      head,
      origin: (entry as any).origin ?? "unknown",
      src: (entry as any).src ?? "",
    });
  }

  entries.sort((a, b) => a.id.localeCompare(b.id));

  const payload = {
    schema: SCHEMA,
    status: "available",
    entries,
    translation_shape_vocabulary: {
      axes: [],
      entries: [],
    },
    generated_from: "scripts/gen_device_behavior_examples.py",
  };

  const serialized = JSON.stringify(payload);
  const credentialValues = mirror_credential_literals();
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount > 0) {
    throw new DeviceBehaviorExamplesError(`device behavior examples contains credential literals (count=${hitCount})`);
  }

  return payload;
}

export function main(): number {
  const payload = build_behavior_examples();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
