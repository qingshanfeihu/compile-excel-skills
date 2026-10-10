#!/usr/bin/env node
// 生成：tools/extract_engine.py ← InfoTest scripts/maintenance/build_package_advisories.py（sha256 feba41498e6e6f19）。不在这里手改。
import path from "node:path";
import { _cex_data_path } from "../../_root";
import { HISTORICAL_TARGET_COUNT, build_package_advisories, write_json_atomic } from "../../case_compiler/package_advisories";

function _parseArgs(argv: string[]): { historical_target: number; output: string } {
  const args = { historical_target: HISTORICAL_TARGET_COUNT, output: path.join("knowledge", "data", "compile_ref", "package_advisories_10.5.json") };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--historical-target" && i + 1 < argv.length) {
      args.historical_target = parseInt(argv[++i], 10);
    } else if (argv[i] === "--output" && i + 1 < argv.length) {
      args.output = argv[++i];
    }
  }
  return args;
}

export function write_package_advisories(): number {
  const args = _parseArgs(process.argv.slice(2));
  const root = _cex_data_path("");
  const payload = build_package_advisories(
    path.join(root, "knowledge", "framework", "verified"),
    path.join(root, "knowledge", "framework", "mirror_precedent_provenance.json"),
    {
      poison_root: path.join(root, "tests", "fixtures", "precedents", "poisoned"),
      retro_scan_path: null,
      historical_target_count: args.historical_target,
    }
  );
  const output = path.isAbsolute(args.output) ? args.output : path.join(root, args.output);
  write_json_atomic(output, payload);
  const baseline = payload.baseline;
  const source = payload.source;
  console.log(`wrote ${output}: certified=${baseline.certified} unverified=${baseline.unverified} current=${source.current_manifest_count} historical_target=${source.historical_target_count} population_complete=${source.population_complete}`);
  return 0;
}

export function main(): number {
  return write_package_advisories();
}

if (require.main === module) {
  process.exit(main());
}
