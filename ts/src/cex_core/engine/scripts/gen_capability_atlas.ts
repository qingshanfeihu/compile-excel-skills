// 生成：tools/extract_engine.py ← InfoTest scripts/gen_capability_atlas.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";
import { WindowedProjectionError, build_method_reference_window } from "./compile_ref_windowed";

const _ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(_ROOT, "knowledge", "data", "compile_ref", "capability_atlas.json");
const SCHEMA = "ist.capability-atlas";

export class CapabilityAtlasError extends Error {}

export function build_capability_atlas(): Record<string, any> {
  const { mirror_src, LIFECYCLE_FS, APV_CMD_PRIMITIVE_FS, SEG_CMD_PRIMITIVE_FS, CMD_PRIMITIVE_FS, valid_es, valid_fs_by_e, execute_action_registry, execute_action_registry_by_dispatch, host_slot_es, norm_action } = require("../case_compiler/apv_lang") as any;
  const { SCHEMA: EXCEL_CONTRACT_SCHEMA, contract_sha256, validate_excel_contract } = require("../case_compiler/excel_contract") as any;
  const { ValidatedReceiptSet, load_receipt_directory, passed_receipt_groups } = require("../case_compiler/excel_capability_receipts") as any;
  const { FRAMEWORK_PROJECTION_SOURCE_PATHS, FrameworkProjectionIdentityError, build_framework_source_identity } = require("../case_compiler/framework_projection_identity") as any;
  const { matching_credential_literal_count, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;

  const contract = validate_excel_contract();
  const contractSha = contract_sha256(contract);
  const receipts = load_receipt_directory();
  const passedGroups = passed_receipt_groups(receipts);
  const identity = build_framework_source_identity();

  const lifecycle = new Set<string>(LIFECYCLE_FS);
  const apvCmd = new Set<string>(APV_CMD_PRIMITIVE_FS);
  const segCmd = new Set<string>(SEG_CMD_PRIMITIVE_FS);
  const cmdPrimitive = new Set<string>(CMD_PRIMITIVE_FS);

  const entries: Array<Record<string, any>> = [];
  for (const [e, fsList] of Object.entries(valid_fs_by_e)) {
    for (const f of fsList as string[]) {
      const norm = norm_action(f);
      const isLifecycle = lifecycle.has(f);
      const isApvCmd = apvCmd.has(f);
      const isSegCmd = segCmd.has(f);
      const isCmdPrimitive = cmdPrimitive.has(f);
      entries.push({
        e,
        f,
        normalized: norm,
        lifecycle: isLifecycle,
        apv_cmd_primitive: isApvCmd,
        seg_cmd_primitive: isSegCmd,
        cmd_primitive: isCmdPrimitive,
        has_receipt: passedGroups.has(`${e}:${f}`),
        host_slot: host_slot_es.has(e),
      });
    }
  }

  const actions = execute_action_registry();
  const actionEntries = Object.entries(actions).map(([name, spec]: [string, any]) => ({
    action: name,
    e: spec.e,
    f: spec.f,
    description: spec.description ?? "",
  }));

  const dispatchEntries = Object.entries(execute_action_registry_by_dispatch()).map(([dispatch, action]) => ({
    dispatch,
    action,
  }));

  const payload = {
    schema: SCHEMA,
    contract_sha256: contractSha,
    identity,
    entries,
    execute_actions: actionEntries,
    dispatch_entries: dispatchEntries,
    stats: {
      total_entries: entries.length,
      with_receipt: entries.filter((e) => e.has_receipt).length,
      lifecycle_count: entries.filter((e) => e.lifecycle).length,
      apv_cmd_count: entries.filter((e) => e.apv_cmd_primitive).length,
      seg_cmd_count: entries.filter((e) => e.seg_cmd_primitive).length,
      cmd_primitive_count: entries.filter((e) => e.cmd_primitive).length,
    },
  };

  const serialized = JSON.stringify(payload);
  const credentialValues = mirror_credential_literals();
  const hitCount = matching_credential_literal_count(serialized, credentialValues);
  if (hitCount > 0) {
    throw new CapabilityAtlasError(`capability atlas projection contains credential literals (count=${hitCount})`);
  }

  return payload;
}

export function render_projection(payload: Record<string, any>): string {
  return JSON.stringify(payload, null, 2) + "\n";
}

export function main(): number {
  const payload = build_capability_atlas();
  const rendered = render_projection(payload);
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(_ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}


export function _parse_cert_methods(): Record<string, string[]> {
  return {};
}

export function _execute_actions(): Record<string, any> {
  const { execute_action_registry, execute_action_registry_by_dispatch } = require("../case_compiler/apv_lang");
  const registry = execute_action_registry();
  const byDispatch = execute_action_registry_by_dispatch();
  const capabilities: Record<string, any> = {};
  for (const [dispatch, action] of Object.entries(byDispatch)) {
    capabilities[dispatch + ":" + action] = { original: action, canonical: action, dispatcher: dispatch, allowed_es: [], origin: dispatch + "_action_mapping", source: "", source_function: action, payload_schema: {}, status: "", reason: "", status_authority: "" };
  }
  return { registry, capabilities, counts: { total_normalized: Object.keys(registry).length, total_normalized_legacy_names: Object.keys(registry).length, total_dispatch_capabilities: Object.keys(capabilities).length }, note: "" };
}

if (require.main === module) {
  process.exit(main());
}
