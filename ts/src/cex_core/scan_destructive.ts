import fs from "node:fs";
import ExcelJS from "exceljs";

import { resolve_execution_sheet } from "./ist_emit/excel_contract";

export const FORMULA_RULE =
  "formula cell: the framework runs the cached value, not the formula";
const _KEYWORD = /^[A-Za-z_]\w*$/;

export class DestructiveRulesUnavailable extends Error {}

type Dict = Record<string, any>;

function isPlainObject(value: unknown): value is Dict {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function reSyntaxError(source: string): string | null {
  let inClass = false;
  let escaped = false;
  const groups: string[] = [];
  const backrefs: string[] = [];
  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (escaped) {
      escaped = false;
      if (/\d/.test(ch) || ch === "k" || ch === "g" || ch === "g<") {
        backrefs.push(ch);
      }
      continue;
    }
    if (ch === "\\") {
      escaped = true;
      continue;
    }
    if (ch === "[") {
      inClass = true;
      continue;
    }
    if (ch === "]" && inClass) {
      inClass = false;
      continue;
    }
    if (inClass) {
      continue;
    }
    if (ch === "(") {
      let kind = "capture";
      if (source[i + 1] === "?") {
        if (source[i + 2] === "P" && source[i + 3] === "<") {
          const end = source.indexOf(">", i + 4);
          kind = end < 0 ? "?" : `named:${source.slice(i + 4, end)}`;
        } else if (source[i + 2] === "P" && source[i + 3] === "=") {
          const end = source.indexOf(")", i + 4);
          backrefs.push(end < 0 ? "?" : source.slice(i + 4, end));
          continue;
        } else if (source[i + 2] === "<" && source[i + 3] !== "=" && source[i + 3] !== "!") {
          const end = source.indexOf(">", i + 3);
          kind = end < 0 ? "?" : `named:${source.slice(i + 3, end)}`;
        } else {
          kind = "group";
        }
      }
      if (kind !== "?") {
        groups.push(kind);
      } else {
        return "unexpected character in regular expression";
      }
      continue;
    }
    if (ch === ")") {
      if (groups.length === 0) {
        return `unbalanced parenthesis at position ${i}`;
      }
      groups.pop();
    }
  }
  if (inClass) {
    return "unterminated character set";
  }
  if (groups.length) {
    const open = groups[groups.length - 1];
    if (open.startsWith("named:")) {
      return `missing ), unterminated name`;
    }
    return "missing ), unterminated subpattern";
  }
  for (const ref of backrefs) {
    if (/^\d+$/.test(ref) || /^\w/.test(ref)) {
      continue;
    }
  }
  return null;
}

function compilePattern(pattern: string): RegExp {
  try {
    return new RegExp(pattern, "i");
  } catch (e) {
    throw new DestructiveRulesUnavailable(
      `destructive pattern does not compile: ${reSyntaxError(pattern) ?? String(e)}`
    );
  }
}

export function load_patterns(grammar: Dict | string): RegExp[] {
  if (typeof grammar === "string") {
    try {
      grammar = JSON.parse(fs.readFileSync(grammar, "utf8"));
    } catch (e: any) {
      throw new DestructiveRulesUnavailable(`domain grammar unreadable: ${String(e?.message ?? e)}`);
    }
  }
  const grammarDict = isPlainObject(grammar) ? grammar : {};
  const destructive = isPlainObject(grammarDict["destructive_commands"]) ? grammarDict["destructive_commands"] : {};
  const raw = destructive["patterns"] ?? [];
  if (!Array.isArray(raw) || raw.length === 0) {
    throw new DestructiveRulesUnavailable("domain grammar carries no destructive_commands.patterns");
  }
  return raw.map((pattern) => compilePattern(String(pattern)));
}

function _split_parameter_parts(text: string): string[] | null {
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
      if (char === quote) {
        quote = null;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      current += char;
      quote = char;
      continue;
    }
    if (char === ",") {
      const part = current.trim();
      if (part) {
        parts.push(part);
      }
      current = "";
      continue;
    }
    current += char;
  }
  if (quote !== null) {
    return null;
  }
  const tail = current.trim();
  if (tail) {
    parts.push(tail);
  }
  return parts;
}

function _unquote_parameter(value: string): string {
  const text = value.trim();
  if (text.length >= 2 && (text[0] === '"' || text[0] === "'") && text[text.length - 1] === text[0]) {
    return text.slice(1, -1).trim();
  }
  return text;
}

function _keyword_value(part: string): string | null {
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
      if (char === quote) {
        quote = null;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (char === "=") {
      if (_KEYWORD.test(part.slice(0, index).trim())) {
        return part.slice(index + 1).trim();
      }
      return null;
    }
  }
  return null;
}

export function command_forms(line: string): string[] {
  const text = String(line ?? "").trim();
  const forms = text ? [text] : [];
  for (const part of _split_parameter_parts(text) ?? []) {
    const value = _keyword_value(part);
    const form = _unquote_parameter(value === null ? part : value);
    if (form && !forms.includes(form)) {
      forms.push(form);
    }
  }
  return forms;
}

export function scan_lines(
  lines: Iterable<[string, string]>,
  patterns: RegExp[]
): Dict[] {
  const findings: Dict[] = [];
  for (const [where, line] of lines) {
    const forms = command_forms(line);
    let hit: [string, RegExp] | null = null;
    for (const form of forms) {
      for (const p of patterns) {
        if (p.test(form)) {
          hit = [form, p];
          break;
        }
      }
      if (hit) {
        break;
      }
    }
    if (hit === null) {
      continue;
    }
    const [form, pattern] = hit;
    const finding: Dict = { where, command: forms[0], rule: pattern.source };
    if (form !== forms[0]) {
      finding["executed"] = form;
    }
    findings.push(finding);
  }
  return findings;
}

type Scalar = string | number | boolean | null;

function scalarCellValue(value: unknown): Scalar {
  if (value === null || value === undefined) {
    return null;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (typeof value === "object") {
    const v = value as any;
    if (Array.isArray(v.richText)) {
      return v.richText.map((r: any) => String(r.text ?? "")).join("");
    }
    if (v.text !== undefined) {
      return String(v.text);
    }
    if (v.result !== undefined) {
      return scalarCellValue(v.result);
    }
    if (v.formula !== undefined) {
      return v.formula === "" ? null : String(v.formula);
    }
    if (v.error !== undefined) {
      return String(v.error);
    }
    return String(value);
  }
  return value as Scalar;
}

interface CellInfo {
  type: number;
  formula: string | null;
  value: Scalar;
}

interface RowData {
  number: number;
  cells: Map<number, CellInfo>;
}

interface SheetData {
  name: string;
  rows: RowData[];
}

interface WorkbookData {
  sheets: SheetData[];
  byName: Map<string, SheetData>;
}

async function _load(xlsx: string): Promise<WorkbookData> {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(xlsx);
  const sheets: SheetData[] = [];
  const byName = new Map<string, SheetData>();
  wb.eachSheet((worksheet) => {
    const rows: RowData[] = [];
    worksheet.eachRow({ includeEmpty: true }, (row, rowNumber) => {
      const cells = new Map<number, CellInfo>();
      for (let c = 1; c <= row.cellCount; c++) {
        const cell = row.getCell(c);
        let formula: string | null = null;
        const raw = cell.value as any;
        if (raw && typeof raw === "object" && raw.formula !== undefined) {
          formula = String(raw.formula);
        }
        cells.set(c, { type: cell.type, formula, value: scalarCellValue(cell.value) });
      }
      rows.push({ number: rowNumber, cells });
    });
    const sheet: SheetData = { name: worksheet.name, rows };
    sheets.push(sheet);
    byName.set(sheet.name, sheet);
  });
  return { sheets, byName };
}

function rowScalars(row: RowData, maxCol: number): Scalar[] {
  const out: Scalar[] = [];
  for (let c = 1; c <= maxCol; c++) {
    out.push(row.cells.get(c)?.value ?? null);
  }
  return out;
}

function colLetter(col: number): string {
  let s = "";
  let n = col;
  while (n > 0) {
    const rem = (n - 1) % 26;
    s = String.fromCharCode(65 + rem) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function _execution_sheet(wb: WorkbookData): SheetData {
  const adapted: any = {
    worksheets: wb.sheets.map((s) => ({
      name: s.name,
      get rowCount() {
        const sheet = wb.byName.get(s.name);
        return sheet ? Math.max(0, ...sheet.rows.map((r) => r.number)) : 0;
      },
      getRow: (rowNo: number) => ({
        get values() {
          const sheet = wb.byName.get(s.name);
          const row = sheet?.rows.find((r) => r.number === rowNo);
          const maxCol = row ? Math.max(0, ...row.cells.keys()) : 0;
          const values: any[] = [undefined];
          for (let c = 1; c <= maxCol; c++) {
            values.push(row?.cells.get(c)?.value ?? null);
          }
          return values;
        },
      }),
    })),
  };
  const [ws] = resolve_execution_sheet(adapted, { allow_legacy: true });
  const sheet = wb.byName.get(ws.name);
  if (!sheet) {
    throw new DestructiveRulesUnavailable(`execution sheet ${ws.name} not found`);
  }
  return sheet;
}

function _command_lines(ws: SheetData): Array<[string, string]> {
  const out: Array<[string, string]> = [];
  for (const row of ws.rows) {
    const device = row.cells.has(5) ? String(row.cells.get(5)!.value ?? "").trim() : "";
    const raw = row.cells.get(7)?.value;
    const command = raw === null || raw === undefined ? "" : String(raw);
    if (!device.startsWith("APV") || !command.trim()) {
      continue;
    }
    for (const line of command.split(/\r\n|\n|\r/)) {
      if (line.trim()) {
        out.push([`${ws.name}!G${row.number}`, line]);
      }
    }
  }
  return out;
}

function _formula_cells(cached: SheetData, formulas: SheetData): Dict[] {
  const findings: Dict[] = [];
  for (const row of formulas.rows) {
    for (const [col, cell] of row.cells) {
      if (cell.type !== ExcelJS.ValueType.Formula) {
        continue;
      }
      const coordinate = `${colLetter(col)}${row.number}`;
      const value = cached.rows.find((r) => r.number === row.number)?.cells.get(col)?.value ?? null;
      findings.push({
        where: `${cached.name}!${coordinate}`,
        command: value === null ? "" : String(value),
        rule: FORMULA_RULE,
        formula: cell.formula ?? "",
      });
    }
  }
  return findings;
}

export async function workbook_command_lines(xlsx: string): Promise<Array<[string, string]>> {
  const wb = await _load(xlsx);
  return _command_lines(_execution_sheet(wb));
}

export async function workbook_formula_cells(xlsx: string): Promise<Dict[]> {
  const cached = await _load(xlsx);
  const formulas = await _load(xlsx);
  const ws = _execution_sheet(cached);
  return _formula_cells(ws, formulas.byName.get(ws.name)!);
}

export async function scan_workbook(xlsx: string, grammar: Dict | string): Promise<Dict[]> {
  const patterns = load_patterns(grammar);
  const cached = await _load(xlsx);
  const formulas = await _load(xlsx);
  const ws = _execution_sheet(cached);
  return _formula_cells(ws, formulas.byName.get(ws.name)!).concat(scan_lines(_command_lines(ws), patterns));
}

export const loadPatterns = load_patterns;
export const commandForms = command_forms;
export const scanLines = scan_lines;
export const workbookCommandLines = workbook_command_lines;
export const workbookFormulaCells = workbook_formula_cells;
export const scanWorkbook = scan_workbook;

