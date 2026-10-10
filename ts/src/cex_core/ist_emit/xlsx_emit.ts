import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { Workbook, Worksheet } from "exceljs";

import {
  read_regular_nofollow,
  sha256_bytes,
  validate_xlsx_zip_budget,
} from "./_sealed_io";
import { FileIR, Row } from "./case_ir";
import { get_config } from "./config";
import { mirror_credential_literals } from "./credential_literals";
import {
  ExcelContractError,
  PINNED_CONTRACT_SHA256,
  TEMPLATE_SHA256,
  resolve_execution_sheet,
} from "./excel_contract";

const _TARGET_NAME = "case.xlsx";
const _TMP_PREFIX = ".case.xlsx.tmp.";
const _BACKUP_PREFIX = ".case.xlsx.previous.";
const _REDACTED_TEMPLATE_CREDENTIAL = "<已移除凭据>";

export const TEMPLATE_PATH = path.resolve(__dirname, "..", "..", "..", "..", "templates", "case_template.xlsx");

export interface RuntimeTemplateSelection {
  path: string;
  content: Buffer;
  release_state: string;
  contract_sha256: string | null;
}

export function select_runtime_template(): RuntimeTemplateSelection {
  const content = read_regular_nofollow(TEMPLATE_PATH, {
    error_type: ExcelContractError,
    invalid_message: "runtime template path is invalid",
    directory_message: "runtime template directory is unavailable",
    open_message: "runtime template is unavailable",
    bounds_message: "runtime template is not a bounded regular file",
    changed_message: "runtime template changed while reading",
    max_bytes: 8 * 1024 * 1024,
  });
  validate_xlsx_zip_budget(content, {
    error_type: ExcelContractError,
    message: "runtime template is not a bounded xlsx archive",
  });
  if (sha256_bytes(content) !== TEMPLATE_SHA256) {
    throw new ExcelContractError(
      `runtime template sha256 does not match the pinned identity ` +
        `(expected ${TEMPLATE_SHA256.slice(0, 12)}…)`,
    );
  }
  return {
    path: TEMPLATE_PATH,
    content,
    release_state: "promoted",
    contract_sha256: PINNED_CONTRACT_SHA256,
  };
}

function _inodeId(st: fs.Stats): [number, number] {
  return [Math.trunc(st.dev), Math.trunc(st.ino)];
}

function _assertDirectoryBinding(
  trustedRoot: string,
  component: string,
): void {
  const checkRoot = path.resolve(trustedRoot);
  const checkCase = path.join(checkRoot, component);
  try {
    const rootStat = fs.statSync(checkRoot);
    const caseStat = fs.statSync(checkCase);
    if (!rootStat.isDirectory() || !caseStat.isDirectory()) {
      throw new Error("case output directory binding changed during xlsx emit");
    }
  } catch (exc) {
    throw new Error("case output directory binding changed during xlsx emit", { cause: exc });
  }
}

function _validateExistingTarget(caseDir: string): fs.Stats | null {
  const target = path.join(caseDir, _TARGET_NAME);
  let st: fs.Stats;
  try {
    st = fs.lstatSync(target);
  } catch {
    return null;
  }
  if (st.isSymbolicLink()) {
    throw new Error("case.xlsx target must not be a symbolic link");
  }
  if (!st.isFile()) {
    throw new Error("case.xlsx target must be a regular file");
  }
  if (st.nlink !== 1) {
    throw new Error("case.xlsx hard-link target is rejected");
  }
  return st;
}

function _uniqueName(prefix: string): string {
  return prefix + crypto.randomBytes(16).toString("hex");
}

function _createNewFile(caseDir: string): [string, number] {
  for (let i = 0; i < 32; i++) {
    const name = _uniqueName(_TMP_PREFIX);
    try {
      const fd = fs.openSync(
        path.join(caseDir, name),
        fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL,
        0o600,
      );
      return [name, fd];
    } catch (exc: unknown) {
      if ((exc as NodeJS.ErrnoException).code === "EEXIST") continue;
      throw exc;
    }
  }
  throw new Error("could not allocate a unique xlsx staging inode");
}

function _makeTargetBackup(caseDir: string): [string, fs.Stats] | null {
  const target = path.join(caseDir, _TARGET_NAME);
  let oldFd: number;
  try {
    oldFd = fs.openSync(target, "r");
  } catch {
    return null;
  }
  try {
    const oldSt = fs.fstatSync(oldFd);
    if (!oldSt.isFile()) {
      throw new Error("case.xlsx target must be a regular file");
    }
    if (oldSt.nlink !== 1) {
      throw new Error("case.xlsx hard-link target is rejected");
    }
    let backup: string | null = null;
    for (let i = 0; i < 32; i++) {
      const candidate = _uniqueName(_BACKUP_PREFIX);
      try {
        fs.linkSync(target, path.join(caseDir, candidate));
        backup = candidate;
        break;
      } catch (exc: unknown) {
        if ((exc as NodeJS.ErrnoException).code === "EEXIST") continue;
        throw exc;
      }
    }
    if (backup === null) {
      throw new Error("could not allocate a unique xlsx rollback link");
    }
    try {
      const backupSt = fs.lstatSync(path.join(caseDir, backup));
      const currentSt = fs.lstatSync(target);
      const expected = _inodeId(oldSt);
      if (
        JSON.stringify(_inodeId(backupSt)) !== JSON.stringify(expected) ||
        JSON.stringify(_inodeId(currentSt)) !== JSON.stringify(expected) ||
        !currentSt.isFile() ||
        backupSt.nlink !== 2 ||
        currentSt.nlink !== 2
      ) {
        throw new Error("case.xlsx target changed while preparing atomic replace");
      }
      return [backup, oldSt];
    } catch (exc) {
      try {
        fs.unlinkSync(path.join(caseDir, backup));
      } catch {}
      throw exc;
    }
  } finally {
    fs.closeSync(oldFd);
  }
}

function _sameTargetInode(caseDir: string, expected: fs.Stats): boolean {
  let current: fs.Stats;
  try {
    current = fs.lstatSync(path.join(caseDir, _TARGET_NAME));
  } catch {
    return false;
  }
  return current.isFile() && JSON.stringify(_inodeId(current)) === JSON.stringify(_inodeId(expected));
}

function _rollbackReplacedTarget(
  caseDir: string,
  backupName: string | null,
  newInode: fs.Stats,
): void {
  const target = path.join(caseDir, _TARGET_NAME);
  if (backupName !== null) {
    fs.renameSync(path.join(caseDir, backupName), target);
    return;
  }
  if (_sameTargetInode(caseDir, newInode)) {
    fs.unlinkSync(target);
  }
}

function _validateDestination(outPath: string, trustedOutputsRoot: string): [string, string] {
  const root = path.resolve(trustedOutputsRoot);
  const target = path.resolve(outPath);
  const rel = path.relative(root, target);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new Error("case.xlsx destination is outside trusted outputs root");
  }
  const parts = rel.split(path.sep).filter(Boolean);
  if (parts.length !== 2 || parts[0] === "" || parts[0] === "." || parts[0] === ".." || parts[1] !== _TARGET_NAME) {
    throw new Error("case.xlsx destination must be outputs/<single-component>/case.xlsx");
  }
  return [root, parts[0]];
}

function _setRow(sheet: Worksheet, r: number, cols: Record<number, unknown>): void {
  for (let c = 1; c <= 9; c++) {
    const cell = sheet.getCell(r, c);
    const value = cols[c];
    cell.value = value === undefined ? null : (value as never);
    if (c === 1 && value !== null && value !== undefined && value !== "") {
      cell.value = String(value);
      cell.numFmt = "@";
    }
  }
}

function _sanitizeInheritedTemplateCredentials(workbook: Workbook): void {
  const literals = Array.from(mirror_credential_literals())
    .filter((v) => v)
    .sort((a, b) => b.length - a.length);
  for (const sheet of workbook.worksheets) {
    sheet.eachRow({ includeEmpty: false }, (row) => {
      row.eachCell({ includeEmpty: false }, (cell) => {
        const value = cell.value;
        if (typeof value !== "string") return;
        let cleaned = value;
        for (const literal of literals) {
          const re = new RegExp(literal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
          cleaned = cleaned.replace(re, _REDACTED_TEMPLATE_CREDENTIAL);
        }
        if (cleaned !== value) {
          cell.value = cleaned;
        }
      });
    });
  }
}

function _rowCols(
  row: Row,
  opts: { stmt_type?: number | null; description?: string | null; autoid?: string | null; priority?: string | null } = {},
): Record<number, unknown> {
  const cols: Record<number, unknown> = {};
  if (opts.autoid !== null && opts.autoid !== undefined) cols[1] = opts.autoid;
  if (opts.priority !== null && opts.priority !== undefined) cols[2] = opts.priority;
  if (opts.stmt_type !== null && opts.stmt_type !== undefined) cols[3] = opts.stmt_type;
  if (opts.description !== null && opts.description !== undefined) cols[4] = opts.description;
  cols[5] = row.test_object;
  cols[6] = row.method;
  cols[7] = row.data;
  if (row.save_as) cols[8] = row.save_as;
  if (row.input_var) cols[9] = row.input_var;
  return cols;
}

async function _buildWorkbook(
  fileIr: FileIR,
  selection?: RuntimeTemplateSelection,
): Promise<Workbook> {
  const sel = selection ?? select_runtime_template();
  const wb = new Workbook();
  await wb.xlsx.load(sel.content as unknown as ArrayBuffer);
  _sanitizeInheritedTemplateCredentials(wb);
  const [sheet, layout] = resolve_execution_sheet(wb, { allow_legacy: false });
  const colA = sheet.getColumn(1);
  const currentWidth = Number(colA.width ?? 0);
  colA.width = Math.max(currentWidth, 22.0);

  const dataStart = layout.data_start;

  for (let r = dataStart; r <= sheet.rowCount; r++) {
    _setRow(sheet, r, {});
  }

  let r = dataStart;
  _setRow(sheet, r, { 3: 0, 4: `Author         : ${fileIr.author ?? "IST-Core"}\n${fileIr.feature}` });
  r += 1;

  for (const row of fileIr.init_rows ?? []) {
    _setRow(sheet, r, _rowCols(row, { stmt_type: 1, description: "初始化配置" }));
    r += 1;
  }

  for (const case_ of fileIr.cases ?? []) {
    let firstCaseRow = true;
    for (const st of case_.steps ?? []) {
      let firstRowOfStep = true;
      for (const row of st.rows ?? []) {
        let cols: Record<number, unknown>;
        if (firstRowOfStep) {
          cols = _rowCols(row, {
            stmt_type: st.stmt_type,
            description: st.description,
            autoid: firstCaseRow ? (case_.autoid ?? "") : null,
            priority: firstCaseRow ? (case_.priority ?? "P1") : null,
          });
          firstCaseRow = false;
          firstRowOfStep = false;
        } else {
          cols = _rowCols(row, { stmt_type: null, description: null });
        }
        _setRow(sheet, r, cols);
        r += 1;
      }
    }
    r += 1;
  }
  return wb;
}

export async function emit_xlsx(
  fileIr: FileIR,
  outPath: string,
  opts: { trusted_outputs_root: string },
): Promise<Record<string, unknown>> {
  const [trustedRoot, component] = _validateDestination(outPath, opts.trusted_outputs_root);
  const selection = select_runtime_template();
  fs.mkdirSync(path.join(trustedRoot, component), { recursive: true });
  const caseDir = path.join(trustedRoot, component);
  let tempFd = -1;
  let tempName: string | null = null;
  let backupName: string | null = null;
  let newInode: fs.Stats | null = null;
  let finalStats: Record<string, unknown> | null = null;
  try {
    _assertDirectoryBinding(trustedRoot, component);
    _validateExistingTarget(caseDir);

    const wb = await _buildWorkbook(fileIr, selection);
    [tempName, tempFd] = _createNewFile(caseDir);
    const tempPath = path.join(caseDir, tempName);
    fs.closeSync(tempFd);
    tempFd = -1;
    await wb.xlsx.writeFile(tempPath);
    newInode = fs.statSync(tempPath);
    if (!newInode.isFile() || newInode.nlink !== 1) {
      throw new Error("xlsx staging inode lost its regular-file identity");
    }

    _assertDirectoryBinding(trustedRoot, component);
    _validateExistingTarget(caseDir);
    const backup = _makeTargetBackup(caseDir);
    if (backup !== null) {
      const [bName, oldInode] = backup;
      backupName = bName;
      if (!_sameTargetInode(caseDir, oldInode)) {
        throw new Error("case.xlsx target changed before atomic replace");
      }
    }

    _assertDirectoryBinding(trustedRoot, component);
    let didReplace = false;
    try {
      fs.renameSync(tempPath, path.join(caseDir, _TARGET_NAME));
      didReplace = true;
      tempName = null;

      _assertDirectoryBinding(trustedRoot, component);
      if (newInode === null || !_sameTargetInode(caseDir, newInode)) {
        throw new Error("atomic xlsx target identity check failed");
      }
      const current = fs.lstatSync(path.join(caseDir, _TARGET_NAME));
      if (current.nlink !== 1) {
        throw new Error("atomic xlsx target unexpectedly has multiple links");
      }

      const readFd = fs.openSync(path.join(caseDir, _TARGET_NAME), "r");
      try {
        const readStat = fs.fstatSync(readFd);
        if (JSON.stringify(_inodeId(readStat)) !== JSON.stringify(_inodeId(newInode))) {
          throw new Error("case.xlsx changed before round-trip readback");
        }
        const stats = await _readback(path.join(caseDir, _TARGET_NAME), outPath);
        stats["template_release_state"] = selection.release_state;
        stats["runtime_template_sha256"] = TEMPLATE_SHA256;
        if (selection.contract_sha256 !== null) {
          stats["excel_contract_sha256"] = selection.contract_sha256;
        }
        finalStats = stats;
      } finally {
        fs.closeSync(readFd);
      }

      _assertDirectoryBinding(trustedRoot, component);
      if (!_sameTargetInode(caseDir, newInode)) {
        throw new Error("case.xlsx changed before atomic emit commit");
      }
    } catch (exc) {
      if (didReplace) {
        _rollbackReplacedTarget(caseDir, backupName, newInode!);
        backupName = null;
      }
      throw exc;
    }

    if (backupName !== null) {
      fs.unlinkSync(path.join(caseDir, backupName));
      backupName = null;
    }
    if (finalStats === null) {
      throw new Error("atomic xlsx emit produced no readback stats");
    }
    return finalStats;
  } finally {
    if (tempFd >= 0) {
      fs.closeSync(tempFd);
    }
    for (const residue of [tempName, backupName]) {
      if (residue !== null) {
        try {
          fs.unlinkSync(path.join(caseDir, residue));
        } catch {}
      }
    }
  }
}

async function _readback(source: string, displayPath?: string): Promise<Record<string, unknown>> {
  const wb = new Workbook();
  await wb.xlsx.readFile(source);
  const [sheet] = resolve_execution_sheet(wb, { allow_legacy: false });
  const grid: unknown[][] = [];
  sheet.eachRow({ includeEmpty: true }, (row) => {
    const values = (row.values as unknown[]).slice(1);
    grid.push(values);
  });
  const anchor = get_config().xlsx.header_anchor;
  const autoids: string[] = [];
  let caseBegin = false;
  let nCheck = 0;
  for (const row of grid) {
    const a = row.length > 0 ? row[0] : null;
    const c = row.length > 2 ? row[2] : null;
    const e = row.length > 4 ? row[4] : null;
    if (a !== null && a !== undefined && String(a).trim() === anchor) {
      caseBegin = true;
      continue;
    }
    if (!caseBegin) continue;
    if (a !== null && a !== undefined && !["1", "0", "None"].includes(String(c))) {
      autoids.push(String(a));
    }
    if (e === "check_point") {
      nCheck += 1;
    }
  }
  return {
    path: displayPath ?? source,
    rows: grid.length,
    case_count: autoids.length,
    autoids,
    check_point_count: nCheck,
  };
}
