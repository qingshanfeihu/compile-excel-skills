// 生成：tools/extract_engine.py ← InfoTest scripts/gen_command_teardown_atlas.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "command_teardown_atlas.json");
const SCHEMA = "ist.command-teardown-atlas";

export class CommandTeardownAtlasError extends Error {}


export function load_command_teardown_atlas(opts: { expected_build?: string; path?: string } = {}): Record<string, any> {
  const atlasPath = opts.path ?? DEFAULT_OUTPUT;
  let raw: Buffer;
  try {
    raw = fs.readFileSync(atlasPath);
  } catch {
    throw new CommandTeardownAtlasError(`command teardown atlas is unavailable: ${atlasPath}`);
  }
  let atlas: any;
  try {
    atlas = JSON.parse(raw.toString("utf8"));
  } catch {
    throw new CommandTeardownAtlasError("command teardown atlas is not valid JSON");
  }
  if (!atlas || typeof atlas !== "object" || atlas.schema !== SCHEMA) {
    throw new CommandTeardownAtlasError(`command teardown atlas schema mismatch (expected ${SCHEMA})`);
  }
  const expectedBuild = opts.expected_build;
  if (expectedBuild !== undefined && expectedBuild !== null && String(expectedBuild) !== "" &&
      String(atlas.device_build ?? "") !== String(expectedBuild)) {
    throw new CommandTeardownAtlasError(`command teardown atlas build mismatch: atlas=${atlas.device_build} expected=${expectedBuild}`);
  }
  return atlas;
}

export function verify_atlas_source_identity(atlas: any): boolean {
  if (!atlas || typeof atlas !== "object" || !atlas.identity || typeof atlas.identity !== "object") {
    throw new CommandTeardownAtlasError("command teardown atlas carries no source identity");
  }
  return true;
}

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
