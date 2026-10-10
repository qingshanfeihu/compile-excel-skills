#!/usr/bin/env node
// 生成：tools/extract_engine.py ← InfoTest scripts/maintenance/build_language_docs_index.py（sha256 5ce2e6b852d1960a）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../../_root";

const ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(ROOT, "knowledge", "data", "compile_ref", "language_docs_index.json");

function _sha256(filePath: string): string {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function _python_entry(root: string, filePath: string, category: string): Record<string, any> {
  const content = fs.readFileSync(filePath, "utf8");
  const symbols: string[] = [];
  const symbolRe = /^(?:async\s+)?(?:def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)/gm;
  let match: RegExpExecArray | null;
  while ((match = symbolRe.exec(content)) !== null) {
    if (!match[1].startsWith("_")) {
      symbols.push(match[1]);
    }
  }
  symbols.sort();
  const docMatch = /^"""([^"]*)"""/.exec(content);
  const doc = docMatch ? docMatch[1].split(/\r?\n/)[0] : "";
  return {
    id: `${category}:${path.parse(filePath).name}`,
    category,
    path: path.relative(root, filePath).replace(/\\/g, "/"),
    symbols,
    summary: doc,
    sha256: _sha256(filePath),
  };
}

function _json(filePath: string): Record<string, any> {
  const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    throw new Error(`${filePath} must contain an object`);
  }
  return payload;
}

export function build_language_docs_index(root: string = ROOT): Record<string, any> {
  const entries: Array<Record<string, any>> = [];
  for (const [category, directory] of [
    ["checker", path.join(root, "main", "case_compiler", "checkers")],
    ["skill_library", path.join(root, "main", "case_compiler", "skill_lib")],
  ] as const) {
    if (!fs.statSync(directory).isDirectory()) {
      continue;
    }
    for (const fileName of fs.readdirSync(directory).filter((f) => f.endsWith(".py")).sort()) {
      if (fileName !== "__init__.py") {
        entries.push(_python_entry(root, path.join(directory, fileName), category));
      }
    }
  }
  const methodPath = path.join(root, "knowledge", "data", "compile_ref", "method_reference.json");
  const method = _json(methodPath);
  entries.push({
    id: "reference:method_reference",
    category: "method_reference",
    path: path.relative(root, methodPath).replace(/\\/g, "/"),
    sections: (method.sections ?? []).filter((s: any) => typeof s === "object" && s !== null && s.name).map((s: any) => String(s.name)),
    shards: (method.sections ?? []).filter((s: any) => typeof s === "object" && s !== null).reduce((sum: number, s: any) => sum + (s.shards?.length ?? 0), 0),
    query: "lang_query(kind='signature'|'dispatch'|'usage'|'nearest'|'prompt_pattern'|'docs')",
    sha256: _sha256(methodPath),
  });
  const blocksSchemaPath = path.join(root, "knowledge", "data", "compile_ref", "blocks_schema.json");
  const blocksSchema = _json(blocksSchemaPath);
  entries.push({
    id: "language:blocks_schema",
    category: "blocks_schema",
    path: path.relative(root, blocksSchemaPath).replace(/\\/g, "/"),
    schema: String(blocksSchema.schema ?? ""),
    kinds: (blocksSchema.closed_sets ?? {}).kinds ?? [],
    expander: String((blocksSchema._meta ?? {}).expander ?? ""),
    resolution: "fs_read",
    summary: "Per-kind blocks field contract parsed from the expander source: required/optional, value domains, assertion-identity carrier position, and every verbatim refusal.",
    sha256: _sha256(blocksSchemaPath),
  });
  const contractPath = path.join(root, "knowledge", "data", "compile_ref", "excel_contract.json");
  const contract = _json(contractPath);
  entries.push({
    id: "language:excel_contract",
    category: "excel_contract",
    path: path.relative(root, contractPath).replace(/\\/g, "/"),
    schema: String(contract.schema ?? ""),
    objects: (contract.objects ?? []).length,
    entries: (contract.entries ?? []).length,
    execute_actions: (contract.execute_actions ?? []).length,
    query: "lang_query(kind='contract'[, domain=<E>][, name=<F>])",
    summary: "The only machine-readable authority for E/F values, signatures, G/H/I semantics, enablement and execute action grammar.",
    sha256: _sha256(contractPath),
  });
  const referencePath = path.join(root, "knowledge", "data", "compile_ref", "EXCEL_FUNCTIONS.md");
  entries.push({
    id: "language:excel_functions",
    category: "excel_language_reference",
    path: path.relative(root, referencePath).replace(/\\/g, "/"),
    sections: fs.readFileSync(referencePath, "utf8").split(/\r?\n/).filter((line) => line.startsWith("## ")).map((line) => line.replace(/^#+\s*/, "").trim()),
    resolution: "fs_read",
    summary: "Mechanics of the A-I execution language and the typed blocks: what each column means, per-kind field contracts, assertion identity and locators. Carries no function list by design.",
    sha256: _sha256(referencePath),
  });
  const grammarPath = path.join(root, "knowledge", "data", "compile_ref", "domain_grammar.json");
  const grammar = _json(grammarPath);
  entries.push({
    id: "grammar:domain_grammar",
    category: "domain_grammar",
    path: path.relative(root, grammarPath).replace(/\\/g, "/"),
    sections: Object.keys(grammar).filter((k) => k !== "_meta").sort(),
    sha256: _sha256(grammarPath),
  });
  const criterionPath = path.join(root, "knowledge", "data", "compile_ref", "criterion_rules.json");
  const criterion = _json(criterionPath);
  entries.push({
    id: "language:criterion_rules",
    category: "criterion_rules",
    path: path.relative(root, criterionPath).replace(/\\/g, "/"),
    schema: String(criterion.schema ?? ""),
    criterion_types: (criterion.criterion_types ?? []).filter((r: any) => typeof r === "object" && r !== null && r.criterion_type).map((r: any) => String(r.criterion_type)),
    rule_count: (criterion.rules ?? []).length,
    pending_proposal_count: (criterion.pending_proposals ?? []).length,
    resolution: "fs_read",
    summary: "Generated criterion-type catalogue and identity-bound verdict-shape rules; pending author proposals are explicitly non-rules.",
    sha256: _sha256(criterionPath),
  });
  const behaviorExamplesPath = path.join(root, "knowledge", "data", "compile_ref", "device_behavior_examples.json");
  const behaviorExamples = _json(behaviorExamplesPath);
  const translationVocabulary = behaviorExamples.translation_shape_vocabulary ?? {};
  entries.push({
    id: "facts:device_behavior_examples",
    category: "device_behavior_examples",
    path: path.relative(root, behaviorExamplesPath).replace(/\\/g, "/"),
    schema: String(behaviorExamples.schema ?? ""),
    status: String(behaviorExamples.status ?? "unavailable"),
    unavailable_reason: String(behaviorExamples.unavailable_reason ?? ""),
    missing_required_entry_count: (behaviorExamples.missing_required_entries ?? []).length,
    rule_ids: (behaviorExamples.entries ?? []).filter((r: any) => typeof r === "object" && r !== null && r.id).map((r: any) => String(r.id)),
    fact_count: (behaviorExamples.entries ?? []).length,
    translation_shape_count: (translationVocabulary.entries ?? []).length,
    translation_shape_axes: translationVocabulary.axes ?? [],
    expected_authority: false,
    resolution: "fs_read",
    summary: "Generated actual-only device behavior, translation examples and translation-shape supply from verified workbooks, attribution receipts, and identity-marked K_ought adjudications; never expected-value authority.",
    sha256: _sha256(behaviorExamplesPath),
  });
  const footprintRoot = path.join(root, "knowledge", "footprints", "nodes");
  entries.push({
    id: "facts:footprint",
    category: "footprint",
    path: path.relative(root, footprintRoot).replace(/\\/g, "/"),
    status: "runtime_resolved",
    resolution: "kb_footprint",
    query: "kb_footprint",
  });
  const ledgerRegistryPath = path.join(root, "knowledge", "shadow_exec", "echo_corpus.jsonl");
  const ledgerManifestPath = path.join(root, "knowledge", "shadow_exec", "manifest.json");
  const ledgerManifest = _json(ledgerManifestPath);
  const fixtureValidation = ledgerManifest.behavior_ledger_projection ?? {};
  const corpusIdentity = ledgerManifest.artifact_identity ?? {};
  entries.push({
    id: "fixture:behavior_ledger",
    category: "behavior_ledger",
    path: path.relative(root, ledgerRegistryPath).replace(/\\/g, "/"),
    status: "tracked_projection",
    resolution: "local_replay / lookup_flip_baseline",
    device_os_build: String(fixtureValidation.device_os_build ?? ""),
    record_count: Number(fixtureValidation.entry_count ?? 0),
    query: "local_replay / lookup_flip_baseline",
    source_manifest: path.relative(root, ledgerManifestPath).replace(/\\/g, "/"),
    source_manifest_sha256: _sha256(ledgerManifestPath),
    registry: path.relative(root, ledgerRegistryPath).replace(/\\/g, "/"),
    registry_schema: String(corpusIdentity.schema ?? ""),
    registry_sha256: String(corpusIdentity.corpus_sha256 ?? ""),
  });
  const pipelinePaths = ["main/ist_core/worker_device_context.py", "main/ist_core/tools/knowledge/behavior_tool.py", "main/case_compiler/provenance_ir.py"];
  entries.push({
    id: "pipeline:probe_to_config_binding",
    category: "evidence_pipeline",
    path: pipelinePaths[0],
    stages: [
      { name: "hypothesis_and_controlled_probe", path: pipelinePaths[0] },
      { name: "verified_fact_writeback", path: pipelinePaths[1] },
      { name: "config_binding_reference", path: pipelinePaths[2] },
    ],
    complete: pipelinePaths.every((p) => fs.statSync(path.join(root, p)).isFile()),
  });
  entries.push({
    id: "reference:vendor_command_tree",
    category: "vendor_command_tree",
    path: "runtime/command_tree",
    status: "runtime_resolved",
    resolution: "vendor_stdlib.load_vendor_stdlib()",
    query: "lang_query(kind='param', name=<command>)",
    summary: "设备命令树投影:命令存在性/参数契约(position/type/optional/help)。",
  });
  const manualRoot = path.join(root, "knowledge", "data", "manual");
  const scanned = fs.statSync(manualRoot).isDirectory()
    ? fs.readdirSync(manualRoot)
        .filter((name) => !name.startsWith(".") && fs.statSync(path.join(manualRoot, name)).isDirectory())
        .sort((a, b) => {
          const pa = a.split(".").map((s): [number, string | number] => (s.match(/^\d+$/) ? [0, parseInt(s, 10)] : [1, s]));
          const pb = b.split(".").map((s): [number, string | number] => (s.match(/^\d+$/) ? [0, parseInt(s, 10)] : [1, s]));
          for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
            const ta = pa[i] ?? [0, 0];
            const tb = pb[i] ?? [0, 0];
            if (ta[0] !== tb[0]) return (ta[0] as number) - (tb[0] as number);
            if (ta[1] !== tb[1]) return String(ta[1]) < String(tb[1]) ? -1 : 1;
          }
          return 0;
        })
    : [];
  entries.push({
    id: "reference:cli_app_manuals",
    category: "vendor_manual",
    path: "knowledge/data/manual",
    versions: scanned,
    versions_source: "local_scan",
    versions_note: "本机扫描结果，非随投影分发的事实——该目录不入 git（.gitignore）。清单为空只说明本机没有同步过手册语料（跑 python -m main.apv_doc_sync），不代表产品没有这些版本；换机重生成本投影会得到该机自己的清单。",
    files_per_version: ["cli_cn.md", "app_cn.md"],
    status: "tracked_projection",
    resolution: "fs_grep(signature) → fs_read(offset=<line>) / apv_lang.manual_param_excerpt",
    query: "lang_query(kind='param', name=<command>)",
    summary: "CLI/APP 手册(manual/<version>/{cli,app}_cn.md,单体文件):参数取值域与含义原文。按 identity.device_build 选版本;先 grep 签名行再按行号读窗口。",
  });
  return { schema: "ist.ide.language-docs", entries: entries.sort((a, b) => a.id.localeCompare(b.id)) };
}

export function write_language_docs_index(output: string = DEFAULT_OUTPUT, root: string = ROOT): Record<string, any> {
  const payload = build_language_docs_index(root);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  if (fs.lstatSync(output).isSymbolicLink()) {
    throw new Error("language docs projection path is a symbolic link");
  }
  const temp = path.join(path.dirname(output), `.${path.basename(output)}.tmp`);
  try {
    fs.writeFileSync(temp, JSON.stringify(payload, null, 2) + "\n", "utf8");
    fs.renameSync(temp, output);
  } catch (exc) {
    try {
      fs.unlinkSync(temp);
    } catch {
      // ignore
    }
    throw exc;
  }
  return payload;
}

export function main(): number {
  write_language_docs_index();
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
