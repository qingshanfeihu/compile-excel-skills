#!/usr/bin/env node
// 生成：tools/extract_engine.py ← InfoTest scripts/gen_vendor_pacing_usage.py（sha256 e9c6edcfb9aa0a85）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import ExcelJS from "exceljs";
import { _cex_data_path } from "../_root";
import { parse_g_arguments, strip_apv_command_kwargs, ExcelContractError } from "../case_compiler/excel_contract";
import { norm_command_tokens, vendor_stdlib_path } from "../case_compiler/vendor_stdlib";

const ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(ROOT, "knowledge", "data", "compile_ref", "vendor_pacing_usage.json");
const ENGINE_STAGING_PREFIX = "ist_staging_";

export interface PacingUsageOptions {
  mirror_root?: string;
  projection_path?: string;
  version?: string;
  device_build?: string;
}

export async function build_usage(options: PacingUsageOptions = {}): Promise<Record<string, any>> {
  const mirror = options.mirror_root ?? path.join(ROOT, "knowledge", "framework", "mirror");
  const projection = options.projection_path ?? vendor_stdlib_path(options.version ?? "10.5", options.device_build ?? "585");
  const sourceBytes = fs.readFileSync(projection);
  const source = JSON.parse(sourceBytes.toString("utf8"));
  const headers = source.headers;
  if (typeof headers !== "object" || headers === null || !Object.keys(headers).length) {
    throw new Error("command-tree projection has no headers");
  }
  const heads = new Map<string[], string>();
  for (const head of Object.keys(headers)) {
    heads.set(norm_command_tokens(head), head);
  }
  const maxHead = Math.max(...[...heads.keys()].map((t) => t.length));
  const manifest: Record<string, string> = {};
  const byHead: Record<string, { values: Map<string, number>; files: Set<string> }> = {};
  const sleeps = new Map<string, number>();
  const prompts = new Map<string, number>();
  let unresolved = 0;
  const unreadable: Array<{ file: string; error_type: string }> = [];
  let timeoutArgumentRows = 0;
  let unmappedTimeoutRows = 0;
  let engineStagingExcluded = 0;

  async function* walk(dir: string): AsyncGenerator<string> {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        yield* walk(full);
      } else if (entry.isFile() && entry.name.endsWith(".xlsx")) {
        yield full;
      }
    }
  }

  for await (const filePath of walk(mirror)) {
    const rel = path.relative(mirror, filePath).replace(/\\/g, "/");
    const parts = rel.split("/");
    if (parts.some((p) => p.startsWith(ENGINE_STAGING_PREFIX))) {
      engineStagingExcluded += 1;
      continue;
    }
    if (fs.lstatSync(filePath).isSymbolicLink() || !fs.statSync(filePath).isFile()) {
      throw new Error("pacing source must be a regular workbook");
    }
    const raw = fs.readFileSync(filePath);
    manifest[rel] = crypto.createHash("sha256").update(raw).digest("hex");
    let workbook: ExcelJS.Workbook;
    try {
      workbook = new ExcelJS.Workbook();
      await workbook.xlsx.load(raw as unknown as ExcelJS.Buffer);
    } catch (exc) {
      unreadable.push({ file: rel, error_type: (exc as Error).name });
      continue;
    }
    try {
      for (const sheet of workbook.worksheets) {
        let previousMethod = "";
        let previousCase = "";
        for (let rowNumber = 1; rowNumber <= sheet.rowCount; rowNumber++) {
          const row = sheet.getRow(rowNumber);
          const values = row.values as any[];
          if (!Array.isArray(values) || values.length < 7) {
            continue;
          }
          const e = String(values[4] ?? "").trim();
          const method = String(values[5] ?? "").trim();
          const g = String(values[6] ?? "").trim();
          if (values[0] !== null && String(values[0]) !== previousCase) {
            previousMethod = "";
            previousCase = String(values[0]);
          }
          if (e === "time" && method === "sleep") {
            if (previousMethod) {
              sleeps.set(previousMethod, (sleeps.get(previousMethod) ?? 0) + 1);
            }
            previousMethod = method;
            continue;
          }
          if (!e || !method) {
            previousMethod = "";
            continue;
          }
          if (e.startsWith("APV") && ["cmd_config", "cmd_enable", "cmd"].includes(method)) {
            let args: any, kwargs: Record<string, any>;
            let command: string;
            try {
              [args, kwargs] = parse_g_arguments(g, method);
              command = strip_apv_command_kwargs(g, method);
            } catch (exc) {
              if (exc instanceof ExcelContractError) {
                unresolved += 1;
                previousMethod = method;
                continue;
              }
              throw exc;
            }
            if ("prompt" in kwargs) {
              prompts.set(method, (prompts.get(method) ?? 0) + 1);
            }
            if ("timeout" in kwargs) {
              timeoutArgumentRows += 1;
              const tokens = norm_command_tokens(command);
              let head: string | null = null;
              for (let size = Math.min(maxHead, tokens.length); size > 0; size--) {
                const prefix = tokens.slice(0, size);
                const key = prefix.join("\0");
                for (const [k, v] of heads) {
                  if (k.join("\0") === key) {
                    head = v;
                    break;
                  }
                }
                if (head) break;
              }
              if (head === null) {
                unresolved += 1;
                unmappedTimeoutRows += 1;
              } else {
                const item = byHead[head] ??= { values: new Map(), files: new Set() };
                const value = kwargs.timeout;
                if (typeof value === "number" && !Number.isNaN(value) && typeof value !== "boolean") {
                  const key = String(value);
                  item.values.set(key, (item.values.get(key) ?? 0) + 1);
                  item.files.add(rel);
                } else {
                  unresolved += 1;
                }
              }
            }
          }
          previousMethod = method;
        }
      }
    } finally {
      // ExcelJS workbooks don't need explicit close
    }
  }

  const byHeadArray = Object.entries(byHead)
    .filter(([, item]) => item.values.size > 0)
    .map(([head, item]) => ({
      head,
      timeout_count: [...item.values.values()].reduce((a, b) => a + b, 0),
      timeout_values: Object.fromEntries([...item.values.entries()].sort(([a], [b]) => parseInt(a) - parseInt(b))),
      files: [...item.files].sort(),
    }))
    .sort((a, b) => a.head.localeCompare(b.head));

  return {
    schema: "ist.vendor-pacing-usage",
    version: options.version ?? "10.5",
    device_build: options.device_build ?? "585",
    policy: "Observed workbook usage only; counts are not recommendations, default values or legal timeout limits.",
    by_head: byHeadArray,
    sleep_after: [...sleeps.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([prev_method, count]) => ({ prev_method, count })),
    prompt_usage: [...prompts.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([method, count]) => ({ method, count })),
    unresolved_rows: unresolved,
    timeout_argument_rows: timeoutArgumentRows,
    unmapped_timeout_rows: unmappedTimeoutRows,
    source: {
      files: Object.keys(manifest).length,
      present: Object.keys(manifest).length > 0,
      engine_staging_excluded: engineStagingExcluded,
      unreadable_files: unreadable,
      sha256_manifest: manifest,
      command_tree_sha256: crypto.createHash("sha256").update(sourceBytes).digest("hex"),
      generated_from: "framework_mirror_workbooks",
      generator: "scripts/gen_vendor_pacing_usage.py",
    },
  };
}

function _parseArgs(argv: string[]): { check: boolean; output: string; version: string; device_build: string } {
  const args = { check: false, output: DEFAULT_OUTPUT, version: "10.5", device_build: "585" };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--check") {
      args.check = true;
    } else if (argv[i] === "--output" && i + 1 < argv.length) {
      args.output = argv[++i];
    } else if (argv[i] === "--version" && i + 1 < argv.length) {
      args.version = argv[++i];
    } else if (argv[i] === "--device-build" && i + 1 < argv.length) {
      args.device_build = argv[++i];
    }
  }
  return args;
}

export async function main(argv?: string[]): Promise<number> {
  const args = _parseArgs(argv ?? process.argv.slice(2));
  const payload = await build_usage({ version: args.version, device_build: args.device_build });
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  if (args.check) {
    if (!fs.statSync(args.output).isFile() || fs.readFileSync(args.output, "utf8") !== rendered) {
      console.log("vendor pacing usage projection is stale");
      return 1;
    }
  } else {
    fs.mkdirSync(path.dirname(args.output), { recursive: true });
    if (!fs.statSync(args.output).isFile() || fs.readFileSync(args.output, "utf8") !== rendered) {
      fs.writeFileSync(args.output, rendered, "utf8");
    }
  }
  return 0;
}

if (require.main === module) {
  main().then((code) => process.exit(code));
}
