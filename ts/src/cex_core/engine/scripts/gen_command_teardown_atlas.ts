// 生成：tools/extract_engine.py ← InfoTest scripts/gen_command_teardown_atlas.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "command_teardown_atlas.json");
const SCHEMA = "ist.command-teardown-atlas";

export class CommandTeardownAtlasError extends Error {}

export function build_teardown_atlas(): Record<string, any> {
  const { load_vendor_stdlib } = require("../case_compiler/vendor_stdlib") as any;
  const { matching_credential_literal_count, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;

  const inventory = load_vendor_stdlib();
  if (!inventory || typeof inventory !== "object") {
    throw new CommandTeardownAtlasError("vendor stdlib is unavailable");
  }

  const headers = inventory.headers ?? {};
  const entries: Array<Record<string, any>> = [];
  for (const [head, entry] of Object.entries(headers)) {
    if (typeof entry !== "object" || entry === null) {
      continue;
    }
    const args = (entry as any).args ?? [];
    const argVariants = (entry as any).arg_variants ?? [];
    entries.push({
      head,
      pmax: (entry as any).pmax ?? 0,
      arg_count: args.length,
      arg_variant_count: argVariants.length,
      origin: (entry as any).origin ?? "unknown",
      src: (entry as any).src ?? "",
    });
  }

  entries.sort((a, b) => a.head.localeCompare(b.head));

  const payload = {
    schema: SCHEMA,
    version: inventory.version ?? "",
    device_os_build: inventory.device_os_build ?? "",
    entries,
    stats: {
      total_heads: entries.length,
      total_args: entries.reduce((sum, e) => sum + e.arg_count, 0),
    },
    generated_from: "scripts/gen_command_teardown_atlas.py",
  };

  const serialized = JSON.stringify(payload);
  const credentialValues = mirror_credential_literals();
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount > 0) {
    throw new CommandTeardownAtlasError(`command teardown atlas contains credential literals (count=${hitCount})`);
  }

  return payload;
}

export function main(): number {
  const payload = build_teardown_atlas();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
