import { _cex_data_path, _cex_set_caller } from "../_root";
import { ExcelContractError, contract_entry, contract_enabled_fs_by_e, load_excel_contract, parse_g_arguments } from "./excel_contract";
import { KNOWLEDGE_FRAMEWORK_MIRROR } from "../knowledge_paths";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

_cex_set_caller("cex_core.engine.case_compiler.case_ir");

const _CONTRACT_WHITELIST_SLOTS: Record<string, number> = {
  VALID_TEST_OBJECTS: 0,
  VALID_CHECK_METHODS: 1,
  VALID_TEST_ENV_HOSTS: 2,
  VALID_APV_METHODS: 3,
};

let _whitelistCache: [Set<string>, Set<string>, Set<string>, Set<string>] | null = null;

export function _contract_whitelists(): [Set<string>, Set<string>, Set<string>, Set<string>] {
  const contract = load_excel_contract();
  const enabled = contract_enabled_fs_by_e(contract);
  const objects = new Set<string>((contract.objects || []).map((item: any) => String(item.e)));
  return [
    objects,
    new Set<string>([...(enabled["check_point"] ?? [])].map((v: any) => String(v))),
    new Set<string>([...(enabled["test_env"] ?? [])].map((v: any) => String(v))),
    new Set<string>([...(enabled["APV_0"] ?? [])].map((v: any) => String(v))),
  ];
}

function _getWhitelist(slot: number): Set<string> {
  if (_whitelistCache === null) {
    _whitelistCache = _contract_whitelists();
  }
  return _whitelistCache[slot];
}

export function __getattr__(name: string): Set<string> {
  const slot = _CONTRACT_WHITELIST_SLOTS[name];
  if (slot === undefined) {
    throw new Error(`module has no attribute ${JSON.stringify(name)}`);
  }
  return _getWhitelist(slot);
}

export class IInjectionSyntaxError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

const _STATIC_INJECTION_PLACEHOLDER_RE = /(?<!\{)\{(?:0)?\}(?!\})/;

function _runtimeStaticLiteralBracesSupported(): boolean {
  try {
    const contract = load_excel_contract();
    const expectedSha = String((contract.runtime || {}).runner_sha256 || "");
    const p = path.join(KNOWLEDGE_FRAMEWORK_MIRROR, "lib/test_xlsx.py");
    const raw = fs.readFileSync(p);
    if (!expectedSha || crypto.createHash("sha256").update(raw).digest("hex") !== expectedSha) {
      return false;
    }
    const text = raw.toString("utf8");
    return /def _validate_call_placeholders[\s\S]*?if not has_input:[\s\S]*?return/.test(text);
  } catch {
    return false;
  }
}

function _placeholderFields(rawValue: any, location: string): string[] {
  if (rawValue === null || rawValue === undefined) {
    return [];
  }
  const text = String(rawValue);
  const fields: string[] = [];
  // Python str.format field extraction
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === "{") {
      if (text[i + 1] === "{") {
        i += 2;
        continue;
      }
      let j = i + 1;
      let depth = 1;
      while (j < text.length && depth > 0) {
        if (text[j] === "{") depth++;
        if (text[j] === "}") depth--;
        j++;
      }
      if (depth > 0) {
        throw new IInjectionSyntaxError("format", `${location} contains unpaired placeholder braces`);
      }
      const inner = text.slice(i + 1, j - 1);
      const [fieldPart, ...restParts] = inner.split(":");
      const [fieldName, ...convParts] = fieldPart.split("!");
      const formatSpec = restParts.join(":");
      const conversion = convParts.join("!");
      if (fieldName !== "" && fieldName !== "0" || formatSpec || conversion) {
        const shown = fieldName === "" ? "{}" : "{" + fieldName + "}";
        throw new IInjectionSyntaxError("format", `${location} contains unsupported placeholder ${shown}; only exact {{}} or {{0}} is allowed`);
      }
      fields.push(fieldName);
      i = j;
      continue;
    }
    if (c === "}") {
      if (text[i + 1] === "}") {
        i += 2;
        continue;
      }
      throw new IInjectionSyntaxError("format", `${location} contains unpaired placeholder braces`);
    }
    i++;
  }
  if (fields.includes("") && fields.length > 1) {
    throw new IInjectionSyntaxError("format", `${location} automatic placeholder {{}} may appear once and cannot mix with {{0}}`);
  }
  return fields;
}

export function validate_i_injection_syntax(g_value: any, i_value: any, method: string): void {
  const [args, kwargs] = parse_g_arguments(g_value, method);
  const hasInput = i_value !== null && i_value !== undefined && Boolean(String(i_value).trim());
  if (!hasInput) {
    const staticValues = [...args, ...Object.values(kwargs)];
    if (staticValues.some((value) => _STATIC_INJECTION_PLACEHOLDER_RE.test(String(value || "")))) {
      throw new IInjectionSyntaxError("scope", "G contains an exact {} or {0} injection placeholder but column I is blank");
    }
    if (_runtimeStaticLiteralBracesSupported()) {
      return;
    }
    args.forEach((value: any, index: number) => {
      _placeholderFields(value, `G positional argument ${index + 1}`);
    });
    for (const [key, value] of Object.entries(kwargs)) {
      _placeholderFields(value, `G keyword argument ${JSON.stringify(key)}`);
    }
    return;
  }
  const positionalFields = args.map((value: any, index: number) => _placeholderFields(value, `G positional argument ${index + 1}`));
  const keywordFields: Record<string, string[]> = {};
  for (const [key, value] of Object.entries(kwargs)) {
    keywordFields[key] = _placeholderFields(value, `G keyword argument ${JSON.stringify(key)}`);
  }
  if (positionalFields.slice(1).some((f: string[]) => f.length) || Object.values(keywordFields).some((f) => f.length)) {
    throw new IInjectionSyntaxError("scope", "G placeholders are allowed only in the first positional argument");
  }
  const first = positionalFields.length ? positionalFields[0] : [];
  if (!args.length) {
    throw new IInjectionSyntaxError("missing", "I injection requires G to provide a first positional argument");
  }
  if (!first.length) {
    throw new IInjectionSyntaxError("missing", "I injection requires the first positional argument to contain {} or {0}");
  }
}

export function parse_found_times_cells(g_value: any, h_value: any, i_value: any): [string, number] {
  const expected = g_value === null || g_value === undefined ? "" : String(g_value);
  if (!expected.trim()) {
    throw new Error("found_times requires a static expected regex in column G");
  }
  if (h_value !== null && h_value !== undefined && String(h_value).trim()) {
    throw new Error("found_times requires column H to be blank");
  }
  const countText = i_value === null || i_value === undefined ? "" : String(i_value).trim();
  let count: number;
  try {
    count = parseInt(countText, 10);
    if (Number.isNaN(count)) throw new Error("nan");
  } catch {
    throw new Error("found_times requires column I to be a positive integer count");
  }
  if (count <= 0 || String(count) !== countText) {
    throw new Error("found_times requires column I to be a positive integer count");
  }
  return [expected, count];
}

export class Row {
  test_object = "";
  method = "";
  data = "";
  save_as: string | null = null;
  input_var: string | null = null;
  provenance: string | null = null;

  is_check_point(): boolean {
    return this.test_object === "check_point";
  }
}

export class Step {
  stmt_type: number;
  description: string;
  rows: Row[] = [];
  constructor(stmt_type: number, description: string) {
    this.stmt_type = stmt_type;
    this.description = description;
  }
}

export class CaseIR {
  autoid: string;
  priority = "P1";
  title = "";
  steps: Step[] = [];
  source_module = "";
  source_text = "";
  expected: string[] = [];
  confidence = 0.0;
  notes: string[] = [];
  is_passthrough = false;

  constructor(autoid: string) {
    this.autoid = autoid;
  }

  check_point_count(): number {
    let count = 0;
    for (const st of this.steps) {
      for (const r of st.rows) {
        if (r.is_check_point()) count++;
      }
    }
    return count;
  }
}

export class FileIR {
  feature: string;
  author = "IST-Core";
  init_rows: Row[] = [];
  cases: CaseIR[] = [];
  module = "";
  rejected: Array<Record<string, any>> = [];
  questions: Array<Record<string, any>> = [];

  constructor(feature: string) {
    this.feature = feature;
  }
}

export function validate_row(row: Row): string[] {
  const errs: string[] = [];
  const e = String(row.test_object || "").trim();
  const f = String(row.method || "").trim();
  let contract: any;
  try {
    contract = load_excel_contract();
  } catch (exc: any) {
    if (exc instanceof ExcelContractError) {
      return [`Excel function contract is unavailable; row cannot be validated: ${exc.message}`];
    }
    throw exc;
  }
  const entry = contract_entry(e, f, contract);
  if (entry === null) {
    const objectNames = new Set((contract.objects || []).map((item: any) => String(item.e)));
    if (!objectNames.has(e)) {
      errs.push(`E=${JSON.stringify(e)} is not a valid test object`);
    } else {
      errs.push(`F=${JSON.stringify(f)} is not declared for E=${JSON.stringify(e)}`);
    }
    return errs;
  }
  if (entry.status !== "enabled") {
    errs.push(`E=${JSON.stringify(e)}, F=${JSON.stringify(f)} is ${entry.status}: ${entry.reason}`);
    return errs;
  }
  if (e === "check_point" && f === "found_times") {
    try {
      parse_found_times_cells(row.data, row.save_as, row.input_var);
    } catch (exc: any) {
      errs.push(String(exc.message || exc));
    }
  }
  try {
    const { validate_g_for_entry } = require("./excel_contract");
    validate_g_for_entry(entry, String(row.data || ""), contract);
  } catch (exc: any) {
    errs.push(`E=${JSON.stringify(e)}, F=${JSON.stringify(f)} has invalid G syntax: ${exc.message || exc}`);
    return errs;
  }
  if (e !== "check_point") {
    try {
      validate_i_injection_syntax(row.data, row.input_var, f);
    } catch (exc: any) {
      errs.push(`E=${JSON.stringify(e)}, F=${JSON.stringify(f)} has invalid I injection syntax: ${exc.message || exc}`);
    }
  }
  return errs;
}

export function validate_case(case_: CaseIR): string[] {
  const errs: string[] = [];
  if (case_.check_point_count() === 0) {
    errs.push(`case ${case_.autoid} has no check_point — guaranteed fail on device (pass requires success>0)`);
  }
  for (const st of case_.steps) {
    for (const r of st.rows) {
      for (const e of validate_row(r)) {
        errs.push(`case ${case_.autoid} step C=${st.stmt_type}: ${e}`);
      }
    }
  }
  return errs;
}
