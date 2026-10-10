import type { Workbook, Worksheet } from "exceljs";
import { XlsxLayout } from "./config";
import { accepts_schema } from "./schema_identity";

export const SCHEMA = "ist.excel.function-contract";
export const RUNTIME_SCHEMA = "ist.excel.runtime";

export const EXECUTION_HEADERS = [
  "自动化ID",
  "优先级",
  "语句类型",
  "描述",
  "测试对象",
  "方法",
  "数据",
  "临时保存期望结果",
  "输入变量",
] as const;
export const EXECUTION_SHEET_MARKER = "IST_EXECUTION_SHEET";
export const CONTRACT_MARKER = "IST_EXCEL_CONTRACT";

export const TEMPLATE_SHA256 = "46aa14dfffbe767ec486dc6b186d582458d666de8a8f6aec2294f920077a45f9";
export const PINNED_CONTRACT_SHA256 = "ca32544f34bbd8662e14320e1cec7ca7892df63a3852a24f496ae2e2eb1fdf6c";

export class ExcelContractError extends Error {}

function _repr(value: unknown): string {
  if (typeof value === "string") {
    return `'${value.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
  }
  return String(value);
}

function _normalizedHeader(row: unknown[]): string[] {
  return row.map((value) => (value === null || value === undefined ? "" : String(value).trim()));
}

export function _definedNameDestinations(workbook: Workbook): Array<[string, string]> | null {
  const names = (workbook as unknown as {
    definedNames?: {
      get?(name: string): unknown;
      matrixMap?: Record<string, unknown>;
      model?: Array<{ name: string; ranges?: string[] }>;
    };
  }).definedNames;
  if (names === null || names === undefined) {
    return null;
  }
  const out: Array<[string, string]> = [];
  if (typeof names.get === "function") {
    let marker: unknown;
    try {
      marker = names.get(EXECUTION_SHEET_MARKER);
    } catch {
      marker = null;
    }
    if (marker === null || marker === undefined) {
      return null;
    }
    try {
      const destinations = (marker as { destinations?: Iterable<[string, string]> }).destinations;
      return Array.from(destinations ?? []);
    } catch (exc) {
      throw new ExcelContractError("execution-sheet marker is malformed", { cause: exc });
    }
  }
  const entry = names.matrixMap?.[EXECUTION_SHEET_MARKER] ??
    (names.model || []).find((item) => item && item.name === EXECUTION_SHEET_MARKER);
  if (entry === null || entry === undefined) {
    return null;
  }
  try {
    if (Array.isArray((entry as { ranges?: string[] }).ranges)) {
      for (const range of (entry as { ranges: string[] }).ranges) {
        const idx = String(range).lastIndexOf("!");
        const sheet = idx >= 0 ? String(range).slice(0, idx) : "";
        const ref = idx >= 0 ? String(range).slice(idx + 1) : String(range);
        out.push([sheet, ref]);
      }
      return out;
    }
    const sheets = (entry as { sheets?: Record<string, unknown> }).sheets || {};
    for (const [sheetName, matrix] of Object.entries(sheets)) {
      if (!Array.isArray(matrix)) continue;
      let minRow = Infinity, maxRow = -Infinity, minCol = Infinity, maxCol = -Infinity;
      for (let r = 0; r < matrix.length; r++) {
        const row = matrix[r];
        if (!Array.isArray(row)) continue;
        for (let c = 0; c < row.length; c++) {
          const cell = row[c];
          if (cell && typeof cell === "object") {
            const cellRow = Number((cell as { row?: number }).row);
            const cellCol = Number((cell as { col?: number }).col);
            if (Number.isFinite(cellRow) && Number.isFinite(cellCol)) {
              minRow = Math.min(minRow, cellRow);
              maxRow = Math.max(maxRow, cellRow);
              minCol = Math.min(minCol, cellCol);
              maxCol = Math.max(maxCol, cellCol);
            }
          }
        }
      }
      if (minRow !== Infinity) {
        const colLetter = (col: number) => {
          let s = "";
          let n = col;
          while (n > 0) { const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = Math.floor((n - 1) / 26); }
          return s;
        };
        out.push([sheetName, '$' + colLetter(minCol) + '$' + minRow + ':$' + colLetter(maxCol) + '$' + maxRow]);
      }
    }
    return out.length ? out : null;
  } catch (exc) {
    throw new ExcelContractError("execution-sheet marker is malformed", { cause: exc });
  }
}

function _unquoteSheetName(name: string): string {
  if (name.length >= 2 && name[0] === "'" && name[name.length - 1] === "'") {
    return name.slice(1, -1).replace(/''/g, "'");
  }
  return name;
}

export function resolve_execution_sheet(
  workbook: Workbook,
  opts: { allow_legacy?: boolean } = {},
): [Worksheet, XlsxLayout] {
  const allowLegacy = opts.allow_legacy ?? false;
  const matches: Array<[Worksheet, number]> = [];
  for (const worksheet of workbook.worksheets ?? []) {
    for (let rowNo = 1; rowNo <= worksheet.rowCount; rowNo++) {
      const values = worksheet.getRow(rowNo).values as unknown[];
      const row = values.slice(1, EXECUTION_HEADERS.length + 1);
      while (row.length < EXECUTION_HEADERS.length) row.push(null);
      const normalized = _normalizedHeader(row);
      if (JSON.stringify(normalized) === JSON.stringify([...EXECUTION_HEADERS])) {
        matches.push([worksheet, rowNo]);
      }
    }
  }
  if (matches.length !== 1) {
    throw new ExcelContractError(
      `expected exactly one complete A-I execution header, found ${matches.length}`,
    );
  }

  const [worksheet, headerRow] = matches[0];
  const destinations = _definedNameDestinations(workbook);
  const markers: Array<[Worksheet, number, unknown[]]> = [];
  for (const candidate of workbook.worksheets ?? []) {
    for (let rowNo = 1; rowNo <= candidate.rowCount; rowNo++) {
      const values = candidate.getRow(rowNo).values as unknown[];
      const row = [values[1] ?? null, values[2] ?? null, values[3] ?? null];
      if (row.length && String(row[0] ?? "").trim() === CONTRACT_MARKER) {
        markers.push([candidate, rowNo, row]);
      }
    }
  }

  if (destinations === null && markers.length === 0) {
    if (!allowLegacy) {
      throw new ExcelContractError(
        `current workbook is missing ${_repr(EXECUTION_SHEET_MARKER)} and ` +
          `${_repr(CONTRACT_MARKER)} markers`,
      );
    }
  } else {
    if (destinations === null) {
      throw new ExcelContractError(
        `current workbook is missing ${_repr(EXECUTION_SHEET_MARKER)} marker`,
      );
    }
    const expectedRef = `$A$${headerRow}:$I$${headerRow}`;
    const normalized = destinations.map(
      ([sheet, ref]) => [_unquoteSheetName(sheet), ref.toUpperCase()] as [string, string],
    );
    if (JSON.stringify(normalized) !== JSON.stringify([[worksheet.name, expectedRef]])) {
      throw new ExcelContractError(
        `${_repr(EXECUTION_SHEET_MARKER)} does not target the unique A-I header`,
      );
    }
    if (markers.length !== 1) {
      throw new ExcelContractError(
        `expected exactly one ${_repr(CONTRACT_MARKER)} identity marker, ` +
          `found ${markers.length}`,
      );
    }
    const [markerSheet, markerRow, markerValues] = markers[0];
    if (markerSheet !== worksheet || markerRow >= headerRow) {
      throw new ExcelContractError(
        `${_repr(CONTRACT_MARKER)} must precede the unique A-I header`,
      );
    }
    const markerVersion = String(markerValues[1] ?? "").trim();
    const markerSha = String(markerValues[2] ?? "").trim();
    if (!accepts_schema(markerVersion, RUNTIME_SCHEMA)) {
      throw new ExcelContractError(
        `workbook runtime identity does not match the pinned contract ` +
          `(workbook ${_repr(markerVersion)} vs pinned ${_repr(RUNTIME_SCHEMA)})`,
      );
    }
    if (markerSha !== PINNED_CONTRACT_SHA256 && !allowLegacy) {
      throw new ExcelContractError(
        `workbook contract identity does not match the pinned contract ` +
          `(workbook sha ${markerSha.slice(0, 12)}… vs pinned ` +
          `${PINNED_CONTRACT_SHA256.slice(0, 12)}…)`,
      );
    }
  }

  return [
    worksheet,
    new XlsxLayout({
      header_row: headerRow,
      data_start: headerRow + 1,
      header_anchor: EXECUTION_HEADERS[0],
      n_cols: EXECUTION_HEADERS.length,
    }),
  ];
}
