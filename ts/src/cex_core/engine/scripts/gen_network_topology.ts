// 生成：tools/extract_engine.py ← InfoTest scripts/gen_network_topology.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "network_topology.json");
const SCHEMA = "ist.network-topology";

export class NetworkTopologyError extends Error {}

export function build_network_topology(): Record<string, any> {
  const { matching_credential_literal_count, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;

  const payload = {
    schema: SCHEMA,
    nodes: [],
    edges: [],
    generated_from: "scripts/gen_network_topology.py",
  };

  const serialized = JSON.stringify(payload);
  const credentialValues = mirror_credential_literals();
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount > 0) {
    throw new NetworkTopologyError(`network topology projection contains credential literals (count=${hitCount})`);
  }

  return payload;
}

export function main(): number {
  const payload = build_network_topology();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
