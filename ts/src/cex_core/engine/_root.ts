import fs from "node:fs";
import path from "node:path";
import { unsetSentinelPath } from "../../platform/index";

export const DATA_ROOT_ENV = "CEX_ENGINE_DATA_ROOT";
export const IDENTITIES_ENV = "CEX_ENGINE_IDENTITIES";
// /dev/null 不是目录（POSIX）：它底下的路径读不到、也建不出来，哪个用户都一样
const _UNSET = unsetSentinelPath("CEX_ENGINE_DATA_ROOT-is-unset");
const _BOUND_WHILE_UNSET = new Set<string>();

export function data_root(): string {
  const raw = (process.env[DATA_ROOT_ENV] || "").trim();
  return raw ? path.resolve(raw.replace(/^~(?=$|[\\/])/, process.env.USERPROFILE || process.env.HOME || "~")) : _UNSET;
}

export function data_root_configured(): boolean {
  return data_root() !== _UNSET;
}

export function modules_bound_while_unset(): string[] {
  return Array.from(_BOUND_WHILE_UNSET).sort();
}

let _callerName = "?";

export function _cex_set_caller(name: string): void {
  _callerName = name;
}

export function _cex_data_path(rel = ""): string {
  const root = data_root();
  if (root === _UNSET) {
    _BOUND_WHILE_UNSET.add(String(_callerName || "?"));
  }
  return rel ? path.join(root, rel) : root;
}

export class IdentityListUnavailable extends Error {}

class _Unavailable {
  private _key: string;
  private _reason: string;
  constructor(key: string, reason = "") {
    this._key = key;
    this._reason = reason;
  }
  private _fail(): never {
    const why = this._reason ? ` (${this._reason})` : "";
    throw new IdentityListUnavailable(
      `${this._key} is kept out of the shipped engine and its identity table is ` +
        `unavailable${why}; set ${IDENTITIES_ENV} to the _identities.json that ` +
        "tools/extract_engine.py writes from the InfoTest source"
    );
  }
  contains(): never { return this._fail(); }
  iter(): never { return this._fail(); }
  size(): never { return this._fail(); }
  has(_v?: any): never { return this._fail(); }
  get length(): never { return this._fail(); }
  [Symbol.iterator](): never { return this._fail(); }
}

export type IdentitySet = ReadonlySet<string> | _Unavailable;

export function _identity_table(): string {
  const raw = (process.env[IDENTITIES_ENV] || "").trim();
  if (raw) {
    return raw.replace(/^~(?=$|[\\/])/, process.env.USERPROFILE || process.env.HOME || "~");
  }
  return path.resolve(__dirname, "..", "..", "..", "cex_core", "engine", "_identities.json");
}

export function _cex_identity_set(key: string): IdentitySet {
  const p = _identity_table();
  let table: any;
  try {
    table = JSON.parse(fs.readFileSync(p, "utf8"));
  } catch (exc: any) {
    if (exc && exc.code === "ENOENT") {
      return new _Unavailable(key, `${p} does not exist`);
    }
    return new _Unavailable(key, `${p} is unreadable: ${exc?.constructor?.name || "Error"}`);
  }
  const values = table && typeof table === "object" && !Array.isArray(table) ? table[key] : undefined;
  if (!Array.isArray(values) || !values.every((v) => typeof v === "string")) {
    return new _Unavailable(key, `${p} has no list of strings under this key`);
  }
  return new Set(values);
}
