import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const DEFAULT_DENY_DIR = path.join(os.homedir(), ".config", "compile-excel");
const ENV_OVERRIDE = "COMPILE_EXCEL_CREDENTIALS_DENY";

let _CACHE: { key: [number, number]; values: ReadonlySet<string> } | null = null;

export function deny_file_path(): string {
  const override = (process.env[ENV_OVERRIDE] ?? "").trim();
  if (override) {
    return override;
  }
  return path.join(DEFAULT_DENY_DIR, "credentials.deny");
}

export function clear_credential_literal_cache(): void {
  _CACHE = null;
}

function _read_deny_file(filePath: string): ReadonlySet<string> {
  let info: fs.Stats;
  try {
    info = fs.lstatSync(filePath);
  } catch {
    return new Set();
  }
  if (!info.isFile()) {
    return new Set();
  }
  let text: string;
  try {
    const fd = fs.openSync(filePath, "r");
    try {
      const buf = Buffer.alloc(1024 * 1024);
      const n = fs.readSync(fd, buf, 0, buf.length, 0);
      text = buf.subarray(0, n).toString("utf-8");
    } finally {
      fs.closeSync(fd);
    }
  } catch {
    return new Set();
  }
  const values = new Set<string>();
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith("#")) {
      values.add(trimmed);
    }
  }
  return values;
}

export function mirror_credential_literals(): ReadonlySet<string> {
  const filePath = deny_file_path();
  let key: [number, number];
  try {
    const info = fs.lstatSync(filePath, { bigint: true });
    key = [Number(info.mtimeNs / 1000000n), Number(info.size)];
  } catch {
    _CACHE = null;
    return new Set();
  }
  if (_CACHE !== null && _CACHE.key[0] === key[0] && _CACHE.key[1] === key[1]) {
    return _CACHE.values;
  }
  const values = _read_deny_file(filePath);
  _CACHE = { key, values };
  return values;
}
