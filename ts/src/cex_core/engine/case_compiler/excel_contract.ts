import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import * as ExcelJS from "exceljs";
import { accepts_schema, write_schema } from "../common/schema_identity";
import { read_regular_nofollow, validate_json_budget, validate_xlsx_zip_budget } from "./_sealed_io";

export class ExcelContractError extends Error {}

const XLSX_CELL_MAX = 32767;

function _requireText(value: any, label: string): string {
  const text = String(value ?? "").trim();
  if (!text) throw new ExcelContractError(`${label}不能为空`);
  return text;
}

function _clipCell(value: string, label: string): string {
  if (value.length > XLSX_CELL_MAX) {
    throw new ExcelContractError(`${label}超过Excel单元格上限（32767字符）`);
  }
  return value;
}

function _stableHash(value: any): string {
  return crypto.createHash("sha256").update(JSON.stringify(value, Object.keys(value).sort())).digest("hex");
}

export const GENESIS_HASH = _stableHash({ genesis: "ist-excel-case-contract", version: 1 });

const _GENESIS_STATUS_VALUES = ["pending", "in_progress", "completed", "cancelled"];
const _GENESIS_STATUS_ALIASES: Record<string, string> = { planned: "pending", running: "in_progress", done: "completed", closed: "cancelled", canceled: "cancelled" };
const _GENESIS_LABELS = ["status", "category", "dependency"];

function _normalizeGenesisStatus(value: any): string {
  const text = String(value ?? "").trim().toLowerCase();
  const normalized = _GENESIS_STATUS_ALIASES[text] ?? text;
  if (!text) throw new ExcelContractError("status不能为空");
  if (!_GENESIS_STATUS_VALUES.includes(normalized)) throw new ExcelContractError(`status取值非法：${text}`);
  return normalized;
}

function _normalizeGenesisCategory(value: any): string {
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) throw new ExcelContractError("category不能为空");
  if (!/^[a-z][a-z0-9_-]{0,63}$/.test(text)) throw new ExcelContractError(`category取值非法：${text}`);
  return text;
}

function _normalizeGenesisDependency(value: any): string {
  const text = String(value ?? "").trim();
  if (text.includes("|")) throw new ExcelContractError("dependency字段不能包含|分隔符");
  return text;
}

function _cellLines(cell: any): string[] {
  return String(cell ?? "").replace(/\r\n?/g, "\n").split("\n");
}

function _parseGenesisBundle(cell: any, opts: { sheet: string; row_number: number }): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of _cellLines(cell).slice(1)) {
    const text = line.trim();
    if (!text) continue;
    if (!text.includes("=")) throw new ExcelContractError(`sheets.${opts.sheet}[${opts.row_number}].genesis_bundle 行格式非法：${text}`);
    const [label, value] = text.split("=", 2);
    const normalizedLabel = String(label ?? "").trim().toLowerCase();
    if (!_GENESIS_LABELS.includes(normalizedLabel)) throw new ExcelContractError(`sheets.${opts.sheet}[${opts.row_number}].genesis_bundle 标签非法：${label}`);
    if (normalizedLabel in out) throw new ExcelContractError(`sheets.${opts.sheet}[${opts.row_number}].genesis_bundle 重复标签：${normalizedLabel}`);
    out[normalizedLabel] = value;
  }
  if (!out["status"]) throw new ExcelContractError(`sheets.${opts.sheet}[${opts.row_number}].genesis_bundle 缺少status`);
  out["status"] = _normalizeGenesisStatus(out["status"]);
  out["category"] = _normalizeGenesisCategory(out["category"]);
  if (out["dependency"] !== undefined) out["dependency"] = _normalizeGenesisDependency(out["dependency"]);
  return out;
}

export function parse_genesis_case_bundle(cell: any): Record<string, any> {
  const lines = _cellLines(cell);
  const intent = _requireText(lines[0], "E表用例标题（首行）");
  return { intent, ..._parseGenesisBundle(cell, { sheet: "E", row_number: 0 }) };
}

export function build_genesis_bundle_cell(caseTitle: string, status: string, opts: { category?: string; dependency?: string; extra_lines?: Iterable<string> } = {}): string {
  const lines = [_clipCell(_requireText(caseTitle, "用例标题"), "用例标题"), `status=${_normalizeGenesisStatus(status)}`, `category=${_normalizeGenesisCategory(opts.category ?? "")}`];
  if (opts.dependency) lines.push(`dependency=${_normalizeGenesisDependency(opts.dependency)}`);
  for (const extra of opts.extra_lines ?? []) lines.push(String(extra));
  return lines.join("\n");
}

export const GENESIS_E_HEADER = ["用例标题\nstatus=pending|in_progress|completed|cancelled\ncategory=ui|api|integration\ndependency=…", "前置条件", "预期结果", "测试环境要求\n(test_env)", "测试数据\n(test_data)", "标签"];
export const GENESIS_G_HEADER = ["用例标题\nstatus=pending|in_progress|completed|cancelled\ncategory=ui|api|integration\ndependency=…", "前置条件", "预期结果", "测试环境要求\n(test_env)", "测试数据\n(test_data)", "标签", "创建人", "更新人"];
export const EXPECTATIONS_SHEET_NAME = "F表_期望清单";
export const EXPECTATIONS_HEADER = ["autoid", "step_ref", "expectation_text", "semantic_key", "value_source_kind", "expect_kind", "resolver_ref", "expect_value_digest"];
export const FIELDS_SHEET_NAME = "G表_字段规范";
export const FIELDS_HEADER = ["autoid", "step_ref", "expectation_text", "field_name", "field_spec", "resolver_ref"];
export const ASSERTION_HINTS_SHEET_NAME = "H表_断言提示";
export const ASSERTION_HINTS_HEADER = ["autoid", "step_ref", "expectation_text", "hint_text", "hint_source"];
export const SCAFFOLD_FOOTER = "— IST 编译区（由 ist compile 自动维护，请勿手改） —";
export const SCAFFOLD_MARKER = "‼ IST-SCAFFOLD — 编译区由 ist compile 管理，请勿修改";

const _KNOWN_SHEETS = [
  { sheet: "A", header: ["用例编号", "状态", "分类", "依赖"] },
  { sheet: "B", header: ["用例编号", "前置条件"] },
  { sheet: "C", header: ["用例编号", "预期结果"] },
  { sheet: "D", header: ["用例编号", "步骤", "动作"] },
  { sheet: "E", header: ["用例编号", "环境要求", "测试数据"] },
  { sheet: "F", header: ["用例编号", "标签"] },
  { sheet: "G", header: ["用例编号", "创建人", "更新人"] },
  { sheet: EXPECTATIONS_SHEET_NAME, header: EXPECTATIONS_HEADER },
  { sheet: FIELDS_SHEET_NAME, header: FIELDS_HEADER },
  { sheet: ASSERTION_HINTS_SHEET_NAME, header: ASSERTION_HINTS_HEADER },
];

export function header_only_workbook(): any {
  const workbook = new ExcelJS.Workbook();
  for (const spec of _KNOWN_SHEETS) {
    const ws = workbook.addWorksheet(spec.sheet);
    ws.addRow(spec.header);
  }
  return workbook;
}

export function load_contract_xlsx(filePath: string): any {
  const encoded = read_regular_nofollow(filePath, {
    errorType: ExcelContractError,
    invalid_message: "contract xlsx path is invalid",
    directory_message: "contract xlsx directory is unavailable",
    open_message: "contract xlsx is unavailable",
    bounds_message: "contract xlsx exceeds its sealed size boundary",
    changed_message: "contract xlsx changed while being read",
    max_bytes: 128 * 1024 * 1024,
  });
  const payload = Buffer.isBuffer(encoded) ? encoded : Buffer.from(encoded as any);
  validate_xlsx_zip_budget(payload, { errorType: ExcelContractError, message: "contract xlsx exceeds its sealed zip budget" });
  const workbook = new ExcelJS.Workbook();
  return workbook.xlsx.load(payload as any).then(() => workbook);
}

export function read_sheet_rows(workbook: any, sheet: string): string[][] {
  const ws = workbook.getWorksheet(sheet);
  if (!ws) throw new ExcelContractError(`sheet not found: ${sheet}`);
  const rows: string[][] = [];
  ws.eachRow((row: any) => {
    rows.push((row.values as any[]).slice(1).map((cell: any) => String(cell ?? "")));
  });
  return rows;
}

export function enabled_fs_by_e(caseId: string, workbook: any): string[] {
  const ws = workbook.getWorksheet("E");
  if (!ws) return [];
  const out: string[] = [];
  ws.eachRow((row: any, rowNumber: number) => {
    if (rowNumber === 1) return;
    const id = String(row.getCell(1).value ?? "").trim();
    if (id === caseId) {
      for (let col = 2; col <= 6; col++) {
        const val = String(row.getCell(col).value ?? "").trim();
        if (val) out.push(val);
      }
    }
  });
  return out;
}

export function contract_sha256(contract: Record<string, any>): string {
  return crypto.createHash("sha256").update(JSON.stringify(contract, Object.keys(contract).sort())).digest("hex");
}

import { _cex_data_path } from "../_root";
import { stat_regular_nofollow } from "./_sealed_io";
import { XlsxLayout } from "./config";
import { P } from "../_py";

export const SCHEMA = "ist.excel.function-contract";
export const EXECUTION_HEADERS = ["自动化ID", "优先级", "语句类型", "描述", "测试对象", "方法", "数据", "临时保存期望结果", "输入变量"];
export const EXECUTION_SHEET_MARKER = "IST_EXECUTION_SHEET";
export const CONTRACT_MARKER = "IST_EXCEL_CONTRACT";
const _CONTRACT_ROOT = _cex_data_path("");
const _MIRROR_ROOT = path.join(_CONTRACT_ROOT, "knowledge", "framework", "mirror");
const _DEFAULT_CONTRACT_PATH = path.join(_CONTRACT_ROOT, "knowledge", "data", "compile_ref", "excel_contract.json");
const _STATUS = new Set(["enabled", "disabled", "internal"]);
const _ENTRY_FIELDS = new Set(["e", "f", "python_symbol", "signature", "g_syntax", "h_semantics", "i_semantics", "dispatch", "status", "reason", "source", "minimum_runtime", "status_authority"]);
type _ContractFileIdentity = [number, number, number, number, number];
type _ContractSourceIdentities = Array<[string, _ContractFileIdentity]>;
const _CONTRACT_CACHE = new Map<string, [_ContractFileIdentity, _ContractSourceIdentities, any]>();
const _CONTRACT_CACHE_MAX = 8;
const _CONTRACT_MAX_BYTES = 16 * 1024 * 1024;
const _SOURCE_MAX_BYTES = 64 * 1024 * 1024;

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _canonicalContractPayload(contract: Record<string, any>): Buffer {
  const body: Record<string, any> = JSON.parse(JSON.stringify(contract));
  delete body.contract_sha256;
  delete body.generated_at;
  const sortKeys = (v: any): any => {
    if (Array.isArray(v)) return v.map(sortKeys);
    if (_isMapping(v)) {
      const out: Record<string, any> = {};
      for (const k of Object.keys(v).sort()) out[k] = sortKeys(v[k]);
      return out;
    }
    return v;
  };
  return Buffer.from(JSON.stringify(sortKeys(body)), "utf8");
}

function _overlayBytes(relativePath: string, sourceOverlays: Record<string, Buffer> | null | undefined): Buffer | null {
  if (!sourceOverlays || !(relativePath in sourceOverlays)) return null;
  const source = sourceOverlays[relativePath];
  if (Buffer.isBuffer(source)) return source;
  throw new ExcelContractError(`contract source overlay must be sealed bytes: ${JSON.stringify(relativePath)}`);
}

function _mirrorSourcePath(relativePath: string): string {
  const relative = new P(relativePath);
  if (relative.is_absolute() || relative.parts.length === 0 || relative.parts.some((p) => p === "" || p === "." || p === "..")) {
    throw new ExcelContractError(`source path escapes framework mirror: ${JSON.stringify(relativePath)}`);
  }
  return path.join(_MIRROR_ROOT, ...relative.parts);
}

function _sourceSha256(relativePath: string, sourceOverlays?: Record<string, Buffer> | null): string {
  const overlay = _overlayBytes(relativePath, sourceOverlays);
  if (overlay !== null) {
    return crypto.createHash("sha256").update(overlay).digest("hex");
  }
  const payload = _readBoundFile(_mirrorSourcePath(relativePath), { label: `contract source ${JSON.stringify(relativePath)}`, max_bytes: _SOURCE_MAX_BYTES })[0];
  return crypto.createHash("sha256").update(payload).digest("hex");
}

function _boundFileIdentity(p: string, opts: { label: string; max_bytes: number }): _ContractFileIdentity {
  return stat_regular_nofollow(p, {
    errorType: ExcelContractError,
    invalid_message: `${opts.label} path is invalid`,
    directory_message: `${opts.label} parent is unavailable`,
    open_message: `${opts.label} is unavailable`,
    bounds_message: `${opts.label} must be a bounded single-link regular file`,
    max_bytes: opts.max_bytes,
    min_bytes: 1,
  }) as _ContractFileIdentity;
}

function _readBoundFile(p: string, opts: { label: string; max_bytes: number }): [Buffer, _ContractFileIdentity] {
  const result = read_regular_nofollow(p, {
    errorType: ExcelContractError,
    invalid_message: `${opts.label} path is invalid`,
    directory_message: `${opts.label} parent is unavailable`,
    open_message: `${opts.label} is unavailable`,
    bounds_message: `${opts.label} must be a bounded single-link regular file`,
    changed_message: `${opts.label} changed while being read`,
    max_bytes: opts.max_bytes,
    min_bytes: 1,
    return_identity: true,
  }) as [Buffer, _ContractFileIdentity];
  return result;
}

function _sourceIdentities(paths: readonly string[]): _ContractSourceIdentities {
  return paths.map((relative) => [relative, _boundFileIdentity(_mirrorSourcePath(relative), { label: `contract source ${JSON.stringify(relative)}`, max_bytes: _SOURCE_MAX_BYTES })]);
}

function _readSourceClosure(paths: readonly string[]): [Record<string, Buffer>, _ContractSourceIdentities] {
  const overlays: Record<string, Buffer> = {};
  const identities: _ContractSourceIdentities = [];
  for (const relative of paths) {
    const [payload, identity] = _readBoundFile(_mirrorSourcePath(relative), { label: `contract source ${JSON.stringify(relative)}`, max_bytes: _SOURCE_MAX_BYTES });
    overlays[relative] = payload;
    identities.push([relative, identity]);
  }
  return [overlays, identities];
}

export function clear_excel_contract_cache(): void {
  _CONTRACT_CACHE.clear();
}

function _validateSignature(signature: any, pair: [string, string]): void {
  if (!_isMapping(signature)) throw new ExcelContractError(`${JSON.stringify(pair)} signature must be an object`);
  const parameters = signature.parameters;
  if (!Array.isArray(parameters)) throw new ExcelContractError(`${JSON.stringify(pair)} signature.parameters must be a list`);
  const names = new Set<string>();
  for (const parameter of parameters) {
    if (!_isMapping(parameter)) throw new ExcelContractError(`${JSON.stringify(pair)} contains a malformed parameter`);
    const name = parameter.name;
    if (typeof name !== "string" || !name || names.has(name)) throw new ExcelContractError(`${JSON.stringify(pair)} contains a duplicate/empty parameter`);
    names.add(name);
    if (!["positional_only", "positional_or_keyword", "var_positional", "keyword_only", "var_keyword"].includes(parameter.kind)) {
      throw new ExcelContractError(`${JSON.stringify(pair)} contains an unknown parameter kind`);
    }
    if (typeof parameter.required !== "boolean") throw new ExcelContractError(`${JSON.stringify(pair)} parameter.required must be boolean`);
    if (!("default" in parameter)) throw new ExcelContractError(`${JSON.stringify(pair)} parameter has no default-presence record`);
    if (parameter.required && parameter.default !== null) throw new ExcelContractError(`${JSON.stringify(pair)} required parameter cannot have a default`);
    if (!parameter.required && !["var_positional", "var_keyword"].includes(parameter.kind) && typeof parameter.default !== "string") {
      throw new ExcelContractError(`${JSON.stringify(pair)} optional parameter default must be serialized`);
    }
  }
}

function _validateContract(payload: any, opts: { source_overlays?: Record<string, Buffer> | null } = {}): any {
  const sourceOverlays = opts.source_overlays ?? null;
  if (!_isMapping(payload)) throw new ExcelContractError("Excel function contract must be a JSON object");
  if (!accepts_schema(payload.schema, SCHEMA)) throw new ExcelContractError(`Excel function contract schema mismatch: ${JSON.stringify(payload.schema)}`);
  if (payload.complete !== true) throw new ExcelContractError("Excel function contract is not complete");
  const sources = payload.source_hashes;
  if (!_isMapping(sources) || Object.keys(sources).length === 0) throw new ExcelContractError("Excel function contract has no source hash closure");
  for (const [relativePath, expected] of Object.entries(sources).sort()) {
    if (!/^[0-9a-f]{64}$/.test(String(expected))) throw new ExcelContractError("Excel function contract contains a malformed source hash");
    const actual = _sourceSha256(relativePath, sourceOverlays);
    if (actual !== expected) throw new ExcelContractError(`Excel function contract source drift: ${JSON.stringify(relativePath)}`);
  }
  const runtime = payload.runtime;
  if (!_isMapping(runtime)) throw new ExcelContractError("Excel function contract has no runtime identity");
  if (!accepts_schema(runtime.minimum_version, "ist.excel.runtime")) throw new ExcelContractError("Excel function contract runtime version mismatch");
  const runnerSource = runtime.runner_source;
  const runnerSha = runtime.runner_sha256;
  if (
    typeof runnerSource !== "string" ||
    !(runnerSource in sources) ||
    !/^[0-9a-f]{64}$/.test(String(runnerSha)) ||
    sources[runnerSource] !== runnerSha ||
    typeof runtime.found_times_supported !== "boolean"
  ) {
    throw new ExcelContractError("Excel function contract runner identity is invalid");
  }
  const entries = payload.entries;
  if (!Array.isArray(entries) || entries.length === 0) throw new ExcelContractError("Excel function contract has no entries");
  const seen = new Set<string>();
  let certifiedEntryCount = 0;
  const sourcePaths = new Set(Object.keys(sources));
  for (const entry of entries) {
    if (!_isMapping(entry) || ![..._ENTRY_FIELDS].every((k) => k in entry)) throw new ExcelContractError("Excel function contract contains a malformed entry");
    const e = entry.e;
    const f = entry.f;
    if (typeof e !== "string" || !e || typeof f !== "string" || !f) throw new ExcelContractError("Excel function contract contains an empty E/F value");
    const pair = `${e} ${f}`;
    if (seen.has(pair)) throw new ExcelContractError(`duplicate Excel function contract entry: ${JSON.stringify([e, f])}`);
    seen.add(pair);
    if (!_STATUS.has(entry.status)) throw new ExcelContractError(`${JSON.stringify([e, f])} has an unknown status`);
    if (typeof entry.reason !== "string") throw new ExcelContractError(`${JSON.stringify([e, f])} reason must be a string`);
    if (typeof entry.status_authority !== "string" || !entry.status_authority) throw new ExcelContractError(`${JSON.stringify([e, f])} has no status authority`);
    if (typeof entry.python_symbol !== "string" || !entry.python_symbol) throw new ExcelContractError(`${JSON.stringify([e, f])} has no Python symbol`);
    _validateSignature(entry.signature, [e, f]);
    const source = entry.source;
    if (!_isMapping(source) || !sourcePaths.has(String(source.path)) || typeof source.line !== "number" || !Number.isInteger(source.line) || source.line < 1) {
      throw new ExcelContractError(`${JSON.stringify([e, f])} has invalid source provenance`);
    }
    for (const key of ["g_syntax", "h_semantics", "i_semantics", "dispatch", "minimum_runtime"]) {
      if (typeof entry[key] !== "string" || !entry[key]) throw new ExcelContractError(`${JSON.stringify([e, f])} has an empty ${key}`);
    }
    if (entry.minimum_runtime !== runtime.minimum_version) throw new ExcelContractError(`${JSON.stringify([e, f])} runtime version does not match the contract`);
    const certificationCandidate = entry.certification_candidate;
    if (certificationCandidate !== null && certificationCandidate !== undefined) {
      if (certificationCandidate !== true) throw new ExcelContractError(`${JSON.stringify([e, f])} has an invalid certification candidate flag`);
      if (entry.status === "enabled") {
        if (!String(entry.status_authority).startsWith("device_receipt_set:")) throw new ExcelContractError(`${JSON.stringify([e, f])} is enabled without a device certification authority`);
        certifiedEntryCount += 1;
      } else if (entry.status !== "disabled") {
        throw new ExcelContractError(`${JSON.stringify([e, f])} certification candidate has an invalid status`);
      }
    }
  }
  const foundTimes = entries.find((entry) => entry.e === "check_point" && entry.f === "found_times");
  if (!foundTimes || (foundTimes.status === "enabled") !== runtime.found_times_supported) {
    throw new ExcelContractError("found_times status does not match the runner capability");
  }
  const objects = payload.objects;
  if (!Array.isArray(objects) || objects.length === 0) throw new ExcelContractError("Excel function contract has no object list");
  const requiredObjectFields = ["e", "python_type", "mro", "status", "reason", "status_authority", "source"];
  const objectNamesList: string[] = [];
  for (const item of objects) {
    if (!_isMapping(item) || !requiredObjectFields.every((k) => k in item)) throw new ExcelContractError("Excel function contract contains a malformed object");
    const eValue = item.e;
    if (typeof eValue !== "string" || !eValue) throw new ExcelContractError("Excel function contract contains an empty object name");
    objectNamesList.push(eValue);
    if (!_STATUS.has(item.status) || typeof item.reason !== "string") throw new ExcelContractError(`object ${JSON.stringify(item.e)} has invalid status/reason`);
    if (typeof item.status_authority !== "string" || !item.status_authority) throw new ExcelContractError(`object ${JSON.stringify(item.e)} has no status authority`);
    if (typeof item.python_type !== "string" || !item.python_type || !Array.isArray(item.mro) || item.mro.some((n: any) => typeof n !== "string" || !n)) {
      throw new ExcelContractError(`object ${JSON.stringify(item.e)} has invalid Python type/MRO`);
    }
    const source = item.source;
    if (!_isMapping(source) || !sourcePaths.has(String(source.path)) || typeof source.line !== "number" || !Number.isInteger(source.line) || source.line < 1) {
      throw new ExcelContractError(`object ${JSON.stringify(item.e)} has invalid source provenance`);
    }
  }
  const objectNames = new Set(objectNamesList);
  if (objectNames.size !== objectNamesList.length) throw new ExcelContractError("Excel function contract contains a duplicate object");
  const seenEs = new Set(entries.map((entry) => entry.e));
  if (seenEs.size !== objectNames.size || ![...seenEs].every((e) => objectNames.has(e))) {
    throw new ExcelContractError("Excel function contract object/entry closure mismatch");
  }
  const objectStatus = new Map(objects.map((item) => [item.e, item.status]));
  const leaked = entries.filter((entry) => objectStatus.get(entry.e) === "disabled" && entry.status === "enabled").map((entry) => [entry.e, entry.f]);
  if (leaked.length) throw new ExcelContractError(`disabled object exposes enabled function entries: ${JSON.stringify(leaked)}`);
  const actions = payload.execute_actions;
  if (!Array.isArray(actions)) throw new ExcelContractError("Excel function contract execute_actions must be a list");
  const actionKeys = new Set<string>();
  let certifiedActionCount = 0;
  const actionFields = ["name", "normalized", "canonical", "equivalent_originals", "dispatcher", "allowed_es", "python_symbol", "signature", "payload_schema", "g_syntax", "h_semantics", "i_semantics", "minimum_runtime", "source", "status", "reason", "status_authority"];
  for (const action of actions) {
    if (!_isMapping(action) || !actionFields.every((k) => k in action)) throw new ExcelContractError("Excel function contract contains a malformed execute action");
    const dispatcher = action.dispatcher;
    const normalized = action.normalized;
    if (!["apv", "client"].includes(dispatcher) || typeof normalized !== "string" || !normalized) {
      throw new ExcelContractError("Excel function contract contains an invalid execute action key");
    }
    const key = `${dispatcher} ${normalized}`;
    if (actionKeys.has(key)) throw new ExcelContractError(`duplicate execute action contract entry: ${JSON.stringify([dispatcher, normalized])}`);
    actionKeys.add(key);
    if (!_STATUS.has(action.status) || typeof action.reason !== "string") throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has invalid status/reason`);
    if (typeof action.status_authority !== "string" || !action.status_authority) throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has no status authority`);
    if (
      typeof action.name !== "string" ||
      !action.name ||
      action.name.toLowerCase().replace(/\s+/g, "") !== normalized ||
      typeof action.canonical !== "string" ||
      !action.canonical ||
      !Array.isArray(action.equivalent_originals) ||
      !action.equivalent_originals.includes(action.name) ||
      action.equivalent_originals.some((n: any) => typeof n !== "string" || !n)
    ) {
      throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has invalid names`);
    }
    const allowedEs = action.allowed_es;
    if (!Array.isArray(allowedEs) || allowedEs.length === 0 || allowedEs.some((e: any) => typeof e !== "string" || !objectNames.has(e)) || new Set(allowedEs).size !== allowedEs.length) {
      throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has an invalid E closure`);
    }
    const candidateEs = action.candidate_allowed_es;
    if (candidateEs !== null && candidateEs !== undefined) {
      if (
        !Array.isArray(candidateEs) ||
        candidateEs.length === 0 ||
        candidateEs.some((e: any) => typeof e !== "string" || !objectNames.has(e)) ||
        new Set(candidateEs).size !== candidateEs.length ||
        !(allowedEs as string[]).every((e) => (candidateEs as string[]).includes(e)) ||
        action.status !== "enabled" ||
        !String(action.status_authority ?? "").startsWith("device_receipt_set:")
      ) {
        throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has an invalid certified E projection`);
      }
      certifiedActionCount += 1;
    }
    if (typeof action.python_symbol !== "string" || !action.python_symbol) throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has no Python symbol`);
    _validateSignature(action.signature, [dispatcher, normalized]);
    const payloadSchema = action.payload_schema;
    if (
      !_isMapping(payloadSchema) ||
      payloadSchema.status !== "classified" ||
      typeof payloadSchema.required !== "boolean" ||
      payloadSchema.separator !== "：" ||
      typeof payloadSchema.min_length !== "number" ||
      !Number.isInteger(payloadSchema.min_length) ||
      payloadSchema.min_length < 0 ||
      (payloadSchema.required && payloadSchema.min_length < 1) ||
      payloadSchema.cell_mode !== "unsplit_single_argument" ||
      typeof payloadSchema.argument_count !== "number" ||
      !Number.isInteger(payloadSchema.argument_count) ||
      payloadSchema.argument_count < 0 ||
      !Array.isArray(payloadSchema.split_delimiters) ||
      payloadSchema.split_delimiters.some((v: any) => typeof v !== "string") ||
      !Array.isArray(payloadSchema.regex_patterns) ||
      payloadSchema.regex_patterns.some((v: any) => typeof v !== "string")
    ) {
      throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has an invalid payload schema`);
    }
    if (typeof action.g_syntax !== "string" || !action.g_syntax) throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has no G syntax`);
    for (const field of ["h_semantics", "i_semantics", "minimum_runtime"]) {
      if (typeof action[field] !== "string" || !action[field]) throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has no ${field}`);
    }
    if (action.minimum_runtime !== runtime.minimum_version) throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} runtime version does not match the contract`);
    const source = action.source;
    if (!_isMapping(source) || !sourcePaths.has(String(source.path)) || typeof source.line !== "number" || !Number.isInteger(source.line) || source.line < 1) {
      throw new ExcelContractError(`execute action ${JSON.stringify([dispatcher, normalized])} has invalid source provenance`);
    }
  }
  const certification = payload.certification;
  if (certification !== null && certification !== undefined) {
    if (!_isMapping(certification)) throw new ExcelContractError("Excel certification metadata must be an object");
    const requiredCertification = ["schema", "basis_contract_sha256", "basis_contract_file_sha256", "deployment_receipt_sha256", "receipt_set_sha256", "receipt_count"];
    if (
      !requiredCertification.every((k) => k in certification) ||
      !accepts_schema(certification.schema, "ist.excel.capability-certification-set") ||
      ["basis_contract_sha256", "basis_contract_file_sha256", "deployment_receipt_sha256", "receipt_set_sha256"].some((field) => typeof certification[field] !== "string" || !/^[0-9a-f]{64}$/.test(certification[field])) ||
      typeof certification.receipt_count !== "number" ||
      !Number.isInteger(certification.receipt_count) ||
      certification.receipt_count < 1
    ) {
      throw new ExcelContractError("Excel certification metadata is incomplete");
    }
    if (certifiedActionCount === 0 && certifiedEntryCount === 0) {
      const leakedAuthority = actions.some((action) => String(action.status_authority ?? "").startsWith("device_receipt_set:"));
      if (leakedAuthority) throw new ExcelContractError("certification authority has no certified action");
    }
  } else if (certifiedActionCount || certifiedEntryCount) {
    throw new ExcelContractError("certified capabilities have no receipt-set metadata");
  }
  const stored = payload.contract_sha256;
  const computed = crypto.createHash("sha256").update(_canonicalContractPayload(payload)).digest("hex");
  if (stored !== computed) throw new ExcelContractError("Excel function contract digest mismatch");
  return payload;
}

export function load_excel_contract(p?: string | null, opts: { source_overlays?: Record<string, Buffer> | null } = {}): any {
  const sourceOverlays = opts.source_overlays ?? null;
  const contractPath = p ?? _DEFAULT_CONTRACT_PATH;
  const readPayload = (): [any, _ContractFileIdentity] => {
    try {
      const [raw, identity] = _readBoundFile(contractPath, { label: "Excel function contract", max_bytes: _CONTRACT_MAX_BYTES });
      validate_json_budget(raw, { errorType: ExcelContractError, message: "Excel function contract exceeds the JSON structure budget" });
      return [JSON.parse(raw.toString("utf8")), identity];
    } catch (exc) {
      if (exc instanceof ExcelContractError) throw exc;
      throw new ExcelContractError(`Excel function contract is unavailable: ${contractPath}`);
    }
  };
  if (sourceOverlays !== null) {
    const [payload] = readPayload();
    return _validateContract(payload, { source_overlays: sourceOverlays });
  }
  const cacheKey = path.resolve(contractPath);
  const contractIdentity = _boundFileIdentity(contractPath, { label: "Excel function contract", max_bytes: _CONTRACT_MAX_BYTES });
  const cached = _CONTRACT_CACHE.get(cacheKey);
  const identityEquals = (a: _ContractFileIdentity, b: _ContractFileIdentity): boolean => a.every((v, i) => v === b[i]);
  if (cached && identityEquals(cached[0], contractIdentity)) {
    const sourcePaths = cached[1].map(([relative]) => relative);
    const current = _sourceIdentities(sourcePaths);
    if (current.length === cached[1].length && current.every(([rel, id], i) => rel === cached[1][i][0] && identityEquals(id, cached[1][i][1]))) {
      return cached[2];
    }
  }
  for (let attempt = 0; attempt < 2; attempt++) {
    const [payload, readContractIdentity] = readPayload();
    const rawSources = _isMapping(payload) ? payload.source_hashes : null;
    const sourcePaths = _isMapping(rawSources) && Object.keys(rawSources).every((relative) => typeof relative === "string") ? Object.keys(rawSources).sort() : [];
    const [sourceBytes, readSources] = sourcePaths.length ? _readSourceClosure(sourcePaths) : [{}, []] as [Record<string, Buffer>, _ContractSourceIdentities];
    const validated = _validateContract(payload, { source_overlays: sourceBytes });
    const afterContract = _boundFileIdentity(contractPath, { label: "Excel function contract", max_bytes: _CONTRACT_MAX_BYTES });
    const afterSources = _sourceIdentities(sourcePaths);
    if (
      identityEquals(readContractIdentity, afterContract) &&
      readSources.length === afterSources.length &&
      readSources.every(([rel, id], i) => rel === afterSources[i][0] && identityEquals(id, afterSources[i][1]))
    ) {
      if (_CONTRACT_CACHE.size >= _CONTRACT_CACHE_MAX) {
        const firstKey = _CONTRACT_CACHE.keys().next().value;
        if (firstKey !== undefined) _CONTRACT_CACHE.delete(firstKey);
      }
      _CONTRACT_CACHE.set(cacheKey, [afterContract, afterSources, validated]);
      return validated;
    }
  }
  throw new ExcelContractError("Excel function contract changed while being validated");
}

export function validate_excel_contract(payload: Record<string, any>, opts: { source_overlays?: Record<string, Buffer> | null } = {}): any {
  return _validateContract({ ...payload }, { source_overlays: opts.source_overlays ?? null });
}

function _resolveContract(contract?: Record<string, any> | null): any {
  return contract === null || contract === undefined ? load_excel_contract() : _validateContract(JSON.parse(JSON.stringify(contract)));
}

export function contract_entry(e: string, f: string, contract?: Record<string, any> | null): Record<string, any> | null {
  const payload = _resolveContract(contract);
  for (const entry of payload.entries) {
    if (entry.e === e && entry.f === f) return entry;
  }
  return null;
}

export function contract_enabled_fs_by_e(contract?: Record<string, any> | null): Record<string, Set<string>> {
  const payload = _resolveContract(contract);
  const grouped: Record<string, Set<string>> = {};
  for (const item of payload.objects) grouped[item.e] = new Set();
  for (const entry of payload.entries) {
    if (entry.status === "enabled") grouped[entry.e].add(entry.f);
  }
  return grouped;
}

function _splitParameterParts(text: string): string[] {
  const parts: string[] = [];
  let current = "";
  let quote: string | null = null;
  let escaped = false;
  for (const char of text) {
    if (escaped) {
      current += char;
      escaped = false;
      continue;
    }
    if (char === "\\") {
      current += char;
      escaped = true;
      continue;
    }
    if (quote !== null) {
      current += char;
      if (char === quote) quote = null;
      continue;
    }
    if (char === '"' || char === "'") {
      current += char;
      quote = char;
      continue;
    }
    if (char === ",") {
      const part = current.trim();
      if (part) parts.push(part);
      current = "";
      continue;
    }
    current += char;
  }
  if (quote !== null) throw new ExcelContractError("G contains an unclosed quote");
  const tail = current.trim();
  if (tail) parts.push(tail);
  return parts;
}

function _unquoteParameter(value: string): string {
  const text = value.trim();
  if (text.length >= 2 && (text[0] === '"' || text[0] === "'") && text[text.length - 1] === text[0]) {
    return text.slice(1, -1).trim();
  }
  return text;
}

function _keywordSplit(part: string): [string, string] | null {
  let quote: string | null = null;
  let escaped = false;
  for (let index = 0; index < part.length; index++) {
    const char = part[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === "\\") {
      escaped = true;
      continue;
    }
    if (quote !== null) {
      if (char === quote) quote = null;
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (char === "=") {
      const key = part.slice(0, index).trim();
      if (/^[A-Za-z_]\w*$/.test(key)) {
        return [key, part.slice(index + 1).trim()];
      }
      return null;
    }
  }
  return null;
}

export function parse_g_arguments(raw: any, method: string): [any[], Record<string, any>] {
  if (raw === null || raw === undefined || (typeof raw === "string" && !raw.trim())) {
    return [[], {}];
  }
  const text = String(raw);
  if (method === "cmd_config" && (text.includes("\n") || text.includes("\r"))) {
    throw new ExcelContractError("cmd_config rejects multiline G; use cmds_config");
  }
  if (method === "execute" || method === "cmds_config") {
    return [[text], {}];
  }
  if (text.includes("\n") || text.includes("\r")) {
    _splitParameterParts(text);
    return [[text], {}];
  }
  const args: any[] = [];
  const kwargs: Record<string, any> = {};
  for (const part of _splitParameterParts(text)) {
    const keyword = _keywordSplit(part);
    if (keyword === null) {
      args.push(_unquoteParameter(part));
      continue;
    }
    const [key, rawValue] = keyword;
    if (key in kwargs) throw new ExcelContractError(`G contains duplicate keyword: ${key}`);
    let value: any = _unquoteParameter(rawValue);
    if (/^\d+$/.test(value)) value = parseInt(value, 10);
    kwargs[key] = value;
  }
  if (method === "sleep") {
    if (args.length !== 1 || Object.keys(kwargs).length > 0) {
      throw new ExcelContractError("sleep requires exactly one integer argument");
    }
    const parsed = parseInt(String(args[0]), 10);
    if (!Number.isInteger(parsed)) throw new ExcelContractError("sleep requires exactly one integer argument");
    args[0] = parsed;
  }
  return [args, kwargs];
}

export function strip_apv_command_kwargs(raw: any, method: string): string {
  const text = String(raw ?? "");
  if (!["cmd", "cmd_enable", "cmd_config"].includes(method)) {
    return text;
  }
  const [args] = parse_g_arguments(text, method);
  if (args.length !== 1 || typeof args[0] !== "string") {
    throw new ExcelContractError("APV command requires exactly one command string");
  }
  return args[0];
}

function _bindContractSignature(signature: Record<string, any>, args: any[], kwargs: Record<string, any>): void {
  const parameters = [...(signature.parameters ?? [])];
  const positional = parameters.filter((item) => ["positional_only", "positional_or_keyword"].includes(item.kind));
  const varPositional = parameters.find((item) => item.kind === "var_positional") ?? null;
  const varKeyword = parameters.find((item) => item.kind === "var_keyword") ?? null;
  if (args.length > positional.length && varPositional === null) {
    throw new ExcelContractError("G arity supplies too many positional arguments");
  }
  const bound = new Set<string>(positional.slice(0, args.length).map((item) => item.name));
  const byName = new Map<string, any>(parameters.map((item) => [item.name, item]));
  for (const key of Object.keys(kwargs)) {
    const parameter = byName.get(key);
    if (parameter === undefined) {
      if (varKeyword === null) throw new ExcelContractError(`G supplies unexpected keyword: ${key}`);
      continue;
    }
    if (parameter.kind === "positional_only") throw new ExcelContractError(`G supplies positional-only parameter by keyword: ${key}`);
    if (bound.has(key)) throw new ExcelContractError(`G supplies parameter more than once: ${key}`);
    if (["var_positional", "var_keyword"].includes(parameter.kind)) {
      if (varKeyword === null) throw new ExcelContractError(`G supplies unexpected keyword: ${key}`);
      continue;
    }
    bound.add(key);
  }
  const missing = parameters.filter((item) => item.required && !["var_positional", "var_keyword"].includes(item.kind) && !bound.has(item.name)).map((item) => item.name);
  if (missing.length) {
    throw new ExcelContractError(`G arity is missing required parameters: ${missing.join(", ")}`);
  }
}

export function execute_action_name(raw: any): string {
  const text = raw === null || raw === undefined ? "" : String(raw);
  const idx = text.lastIndexOf("：");
  return idx >= 0 ? text.slice(0, idx) : text;
}

export function validate_execute_action(e: string, raw: any, contract?: Record<string, any> | null): Record<string, any> {
  const payload = _resolveContract(contract);
  const text = raw === null || raw === undefined ? "" : String(raw);
  const sepIdx = text.lastIndexOf("：");
  const separator = sepIdx >= 0;
  const actionPayload = separator ? text.slice(sepIdx + 1) : "";
  const action = execute_action_name(text);
  const normalized = action.toLowerCase().replace(/\s+/g, "");
  const matches = payload.execute_actions.filter((item: any) => item.status === "enabled" && item.allowed_es.includes(e) && item.normalized === normalized);
  if (matches.length !== 1) {
    const dispatchers = [...new Set<string>(payload.execute_actions.filter((item: any) => item.allowed_es.includes(e)).map((item: any) => item.dispatcher))].sort();
    const registry = dispatchers.length ? dispatchers.join("/") : "E-bound";
    throw new ExcelContractError(`execute action ${JSON.stringify(action.trim())} is not in the exact enabled ${registry} action registry for E=${JSON.stringify(e)}`);
  }
  const actionContract = matches[0];
  const schema = actionContract.payload_schema;
  const required = Boolean(schema.required);
  const minimum = Number(schema.min_length);
  if (required && (!separator || actionPayload.trim().length < minimum)) {
    throw new ExcelContractError(`execute action ${JSON.stringify(action.trim())} requires a non-empty payload after the full-width separator`);
  }
  return actionContract;
}

export function validate_g_arguments_for_entry(entry: Record<string, any>, raw: any): void {
  const [args, kwargs] = parse_g_arguments(raw, String(entry.f ?? ""));
  const signature = entry.signature;
  if (!_isMapping(signature)) throw new ExcelContractError("contract entry has no valid signature");
  _bindContractSignature(signature, args, kwargs);
}

export function validate_g_for_entry(entry: Record<string, any>, raw: any, contract?: Record<string, any> | null): void {
  if (entry.status !== "enabled") {
    throw new ExcelContractError(`function ${entry.e}::${entry.f} is not enabled`);
  }
  const dispatch = entry.dispatch;
  if (dispatch === "checkpoint_v2_three_argument") return;
  if (dispatch === "checkpoint_two_argument") return;
  if (dispatch === "execute_registry") {
    validate_execute_action(String(entry.e ?? ""), raw, contract);
  }
  validate_g_arguments_for_entry(entry, raw);
}

function _normalizedHeader(row: any[]): string[] {
  return row.map((value) => (value === null || value === undefined ? "" : String(value).trim()));
}

function _unquoteSheetName(name: string): string {
  if (name.length >= 2 && name[0] === "'" && name[name.length - 1] === "'") {
    return name.slice(1, -1).replace(/''/g, "'");
  }
  return name;
}

function _definedNameDestinations(workbook: any): Array<[string, string]> | null {
  const names = workbook.definedNames;
  if (names === null || names === undefined) return null;
  let marker: any = null;
  try {
    marker = typeof names.get === "function" ? names.get(EXECUTION_SHEET_MARKER) : null;
  } catch {
    marker = null;
  }
  if (!marker) return null;
  try {
    const destinations = marker.ranges ?? marker.destinations ?? [];
    return destinations.map((ref: string) => {
      const idx = ref.lastIndexOf("!");
      const sheet = idx >= 0 ? ref.slice(0, idx) : "";
      const range = idx >= 0 ? ref.slice(idx + 1) : ref;
      return [sheet, range] as [string, string];
    });
  } catch {
    throw new ExcelContractError("execution-sheet marker is malformed");
  }
}

export function resolve_execution_sheet(workbook: any, opts: { allow_legacy?: boolean; contract?: Record<string, any> | null } = {}): [any, XlsxLayout] {
  const allowLegacy = opts.allow_legacy ?? true;
  const matches: Array<[any, number]> = [];
  for (const worksheet of workbook.worksheets ?? []) {
    let rowNo = 0;
    worksheet.eachRow({ includeEmpty: true }, (row: any, rowNumber: number) => {
      rowNo = rowNumber;
      const values = (row.values as any[]).slice(1, EXECUTION_HEADERS.length + 1);
      const normalized = _normalizedHeader(values);
      if (normalized.length === EXECUTION_HEADERS.length && normalized.every((v, i) => v === EXECUTION_HEADERS[i])) {
        matches.push([worksheet, rowNumber]);
      }
    });
  }
  if (matches.length !== 1) {
    throw new ExcelContractError(`expected exactly one complete A-I execution header, found ${matches.length}`);
  }
  const [worksheet, headerRow] = matches[0];
  const destinations = _definedNameDestinations(workbook);
  const markers: Array<[any, number, any[]]> = [];
  for (const candidate of workbook.worksheets ?? []) {
    candidate.eachRow((row: any, rowNumber: number) => {
      const values = (row.values as any[]).slice(1, 4);
      if (values.length && String(values[0] ?? "").trim() === CONTRACT_MARKER) {
        markers.push([candidate, rowNumber, values]);
      }
    });
  }
  if (destinations === null && markers.length === 0) {
    if (!allowLegacy) {
      throw new ExcelContractError(`current workbook is missing ${JSON.stringify(EXECUTION_SHEET_MARKER)} and ${JSON.stringify(CONTRACT_MARKER)} markers`);
    }
  } else {
    if (destinations === null) {
      throw new ExcelContractError(`current workbook is missing ${JSON.stringify(EXECUTION_SHEET_MARKER)} marker`);
    }
    const expectedRef = `$A${headerRow}:$I${headerRow}`;
    const normalized = destinations.map(([sheet, ref]) => [_unquoteSheetName(sheet), ref.toUpperCase()]);
    if (normalized.length !== 1 || normalized[0][0] !== worksheet.name || normalized[0][1] !== expectedRef) {
      throw new ExcelContractError(`${JSON.stringify(EXECUTION_SHEET_MARKER)} does not target the unique A-I header`);
    }
    if (markers.length !== 1) {
      throw new ExcelContractError(`expected exactly one ${JSON.stringify(CONTRACT_MARKER)} identity marker, found ${markers.length}`);
    }
    const [markerSheet, markerRow, markerValues] = markers[0];
    if (markerSheet !== worksheet || markerRow >= headerRow) {
      throw new ExcelContractError(`${JSON.stringify(CONTRACT_MARKER)} must precede the unique A-I header`);
    }
    const activeContract = _resolveContract(opts.contract ?? null);
    const markerVersion = String(markerValues[1] ?? "").trim();
    const markerSha = String(markerValues[2] ?? "").trim();
    if (!accepts_schema(markerVersion, activeContract.runtime.minimum_version)) {
      throw new ExcelContractError(`workbook runtime identity does not match the current contract (workbook ${JSON.stringify(markerVersion)} vs current ${JSON.stringify(activeContract.runtime.minimum_version)})`);
    }
    const currentSha = crypto.createHash("sha256").update(_canonicalContractPayload(activeContract)).digest("hex");
    if (markerSha !== currentSha && !allowLegacy) {
      throw new ExcelContractError(`workbook contract identity does not match the current contract (workbook sha ${markerSha.slice(0, 12)}… vs current ${currentSha.slice(0, 12)}…)`);
    }
  }
  const layout = new XlsxLayout();
  layout.header_row = headerRow;
  layout.data_start = headerRow + 1;
  layout.header_anchor = EXECUTION_HEADERS[0];
  layout.n_cols = EXECUTION_HEADERS.length;
  return [worksheet, layout];
}
