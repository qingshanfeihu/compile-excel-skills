import fs from "node:fs";
import path from "node:path";
import os from "node:os";

let fsSync: typeof fs = fs;
let pathMod: typeof path = path;
export function _installDrive(fsImpl: typeof fs, pathImpl: typeof path): void {
  fsSync = fsImpl;
  pathMod = pathImpl;
}

function _norm(p: any): string {
  return pathMod.normalize(String(p));
}

export class P {
  _p: string;
  constructor(p: any) {
    this._p = p instanceof P ? p._p : String(p);
  }
  toString(): string {
    return this._p;
  }
  get str(): string {
    return this._p;
  }
  get name(): string {
    return pathMod.basename(this._p);
  }
  get stem(): string {
    const base = pathMod.basename(this._p);
    const i = base.lastIndexOf(".");
    return i > 0 ? base.slice(0, i) : base;
  }
  get suffix(): string {
    const base = pathMod.basename(this._p);
    const i = base.lastIndexOf(".");
    return i > 0 ? base.slice(i) : "";
  }
  get suffixes(): string[] {
    const base = pathMod.basename(this._p);
    const out: string[] = [];
    const parts = base.split(".");
    for (let i = 1; i < parts.length; i++) out.push("." + parts[i]);
    return out;
  }
  get parent(): P {
    return new P(pathMod.dirname(this._p));
  }
  get parents(): P[] {
    const out: P[] = [];
    let cur = pathMod.dirname(this._p);
    for (;;) {
      out.push(new P(cur));
      const next = pathMod.dirname(cur);
      if (next === cur) break;
      cur = next;
    }
    return out;
  }
  get parts(): string[] {
    const parsed = pathMod.parse(this._p);
    const segs = this._p.slice(parsed.root.length).split(/[\\/]+/).filter((s) => s !== "");
    if (parsed.root) return [parsed.root, ...segs];
    return segs;
  }
  get anchor(): string {
    return pathMod.parse(this._p).root;
  }
  get drive(): string {
    const m = /^[A-Za-z]:/.exec(this._p);
    return m ? m[0] : "";
  }
  get root(): string {
    const parsed = pathMod.parse(this._p);
    return parsed.root.slice(parsed.root.length === 3 && /^[A-Za-z]:/.test(parsed.root) ? 2 : 0);
  }
  joinpath(...parts: any[]): P {
    return new P(pathMod.join(this._p, ...parts.map((x) => String(x instanceof P ? x._p : x))));
  }
  join(...parts: any[]): P {
    return this.joinpath(...parts);
  }
  div(other: any): P {
    return this.joinpath(other);
  }
  is_absolute(): boolean {
    return pathMod.isAbsolute(this._p);
  }
  is_file(): boolean {
    try {
      return fsSync.statSync(this._p).isFile();
    } catch {
      return false;
    }
  }
  is_dir(): boolean {
    try {
      return fsSync.statSync(this._p).isDirectory();
    } catch {
      return false;
    }
  }
  is_symlink(): boolean {
    try {
      return fsSync.lstatSync(this._p).isSymbolicLink();
    } catch {
      return false;
    }
  }
  exists(): boolean {
    return fsSync.existsSync(this._p);
  }
  resolve(): P {
    return new P(pathMod.resolve(this._p));
  }
  absolute(): P {
    return new P(pathMod.resolve(this._p));
  }
  expanduser(): P {
    const home = os.homedir();
    let s = this._p;
    if (s === "~") s = home;
    else if (s.startsWith("~/") || s.startsWith("~\\")) s = home + s.slice(1);
    return new P(s);
  }
  read_text(encoding = "utf8", errors?: string): string {
    const buf = fsSync.readFileSync(this._p);
    if (errors === "replace") {
      return buf.toString("utf8").replace(/\uFFFD/g, "");
    }
    return buf.toString("utf8");
  }
  read_bytes(): Buffer {
    return fsSync.readFileSync(this._p);
  }
  write_text(text: string, encoding = "utf8"): number {
    fsSync.writeFileSync(this._p, String(text), "utf8");
    return Buffer.byteLength(String(text), "utf8");
  }
  write_bytes(data: Buffer | Uint8Array | string): number {
    const buf = typeof data === "string" ? Buffer.from(data, "utf8") : Buffer.from(data);
    fsSync.writeFileSync(this._p, buf);
    return buf.length;
  }
  mkdir(opts: { parents?: boolean; exist_ok?: boolean; mode?: number; recursive?: boolean } = {}): void {
    if (opts.parents) {
      fsSync.mkdirSync(this._p, { recursive: true });
      return;
    }
    try {
      fsSync.mkdirSync(this._p);
    } catch (e: any) {
      if (e && e.code === "EEXIST") {
        if (opts.exist_ok) {
          try {
            if (fsSync.statSync(this._p).isDirectory()) return;
          } catch {}
        }
        throw new FileExistsError(`[Errno 17] File exists: '${this._p}'`);
      }
      if (e && e.code === "ENOENT") throw new FileNotFoundError(`[Errno 2] No such file or directory: '${this._p}'`);
      throw e;
    }
  }
  unlink(opts: { missing_ok?: boolean } = {}): void {
    try {
      fsSync.unlinkSync(this._p);
    } catch (e: any) {
      if (e && e.code === "ENOENT") {
        if (opts.missing_ok) return;
        throw new FileNotFoundError(`[Errno 2] No such file or directory: '${this._p}'`);
      }
      throw e;
    }
  }
  rename(target: any): P {
    const t = String(target instanceof P ? target._p : target);
    fsSync.renameSync(this._p, t);
    return new P(t);
  }
  replace(target: any): P {
    const t = String(target instanceof P ? target._p : target);
    try {
      fsSync.renameSync(this._p, t);
    } catch (e: any) {
      if (e && (e.code === "EEXIST" || e.code === "EPERM")) {
        try {
          fsSync.rmSync(t, { recursive: true, force: true });
        } catch {}
        fsSync.renameSync(this._p, t);
      } else throw e;
    }
    return new P(t);
  }
  rmdir(): void {
    fsSync.rmdirSync(this._p);
  }
  stat(): fs.Stats {
    try {
      return fsSync.statSync(this._p);
    } catch (e: any) {
      if (e && e.code === "ENOENT") throw new FileNotFoundError(`[Errno 2] No such file or directory: '${this._p}'`);
      throw e;
    }
  }
  lstat(): fs.Stats {
    return fsSync.lstatSync(this._p);
  }
  iterdir(): P[] {
    return fsSync.readdirSync(this._p).map((n) => new P(pathMod.join(this._p, n)));
  }
  glob(pattern: string): P[] {
    return _glob(this._p, String(pattern), false);
  }
  rglob(pattern: string): P[] {
    return _glob(this._p, String(pattern), true);
  }
  relative_to(other: any): P {
    const base = String(other instanceof P ? other._p : other);
    const rel = pathMod.relative(base, this._p);
    if (rel === "" ) return new P(".");
    if (rel.startsWith("..") || pathMod.isAbsolute(rel)) {
      throw new PyValueError(`'${this._p}' is not in the subpath of '${base}'`);
    }
    return new P(rel);
  }
  as_posix(): string {
    return this._p.split(pathMod.sep).join("/");
  }
  touch(opts: { exist_ok?: boolean } = {}): void {
    if (!fsSync.existsSync(this._p)) {
      fsSync.writeFileSync(this._p, "");
      return;
    }
    if (opts.exist_ok === false) throw new FileExistsError(`[Errno 17] File exists: '${this._p}'`);
    const now = new Date();
    try {
      fsSync.utimesSync(this._p, now, now);
    } catch {}
  }
  open(..._args: any[]): any {
    throw new Error("P.open not supported in port; use read_text/write_text");
  }
  with_name(name: string): P {
    return new P(pathMod.join(pathMod.dirname(this._p), name));
  }
  with_suffix(suffix: string): P {
    const base = pathMod.basename(this._p);
    const i = base.lastIndexOf(".");
    const stem = i > 0 ? base.slice(0, i) : base;
    return new P(pathMod.join(pathMod.dirname(this._p), stem + suffix));
  }
  match(pattern: string): boolean {
    const re = _globToRegExp(String(pattern));
    return re.test(this.as_posix()) || re.test(pathMod.basename(this._p));
  }
  eq(other: any): boolean {
    return this._p === (other instanceof P ? other._p : String(other));
  }
  static cwd(): P {
    return new P(process.cwd());
  }
  static home(): P {
    return new P(os.homedir());
  }
}

function _globToRegExp(pattern: string): RegExp {
  let re = "";
  let i = 0;
  const p = pattern.split(pathMod.sep).join("/");
  while (i < p.length) {
    const c = p[i];
    if (c === "*") {
      if (p[i + 1] === "*") {
        if (p[i + 2] === "/") {
          re += "(?:[^/]+/)*";
          i += 3;
        } else {
          re += ".*";
          i += 2;
        }
      } else {
        re += "[^/]*";
        i += 1;
      }
    } else if (c === "?") {
      re += "[^/]";
      i += 1;
    } else if (c === "[") {
      let j = i + 1;
      if (p[j] === "!") j++;
      if (p[j] === "]") j++;
      while (j < p.length && p[j] !== "]") j++;
      const cls = p.slice(i + 1, j).replace(/^!/, "^");
      re += "[" + cls + "]";
      i = j + 1;
    } else {
      re += c.replace(/[.+^${}()|\\]/g, "\\$&");
      i += 1;
    }
  }
  return new RegExp("^" + re + "$");
}

function _glob(root: string, pattern: string, recursive: boolean): P[] {
  const out: P[] = [];
  const rootP = _norm(root);
  const segs = pattern.split(/[\\/]+/);
  const hasMagic = (s: string) => /[*?[]/.test(s);
  const walk = (dir: string, idx: number): void => {
    if (idx >= segs.length) return;
    const seg = segs[idx];
    const last = idx === segs.length - 1;
    if (!hasMagic(seg)) {
      const full = pathMod.join(dir, seg);
      if (last) {
        if (fsSync.existsSync(full)) out.push(new P(full));
      } else {
        try {
          if (fsSync.statSync(full).isDirectory()) walk(full, idx + 1);
        } catch {}
      }
      return;
    }
    if (seg === "**") {
      if (last) {
        const stack = [dir];
        while (stack.length) {
          const d = stack.pop()!;
          let entries: fs.Dirent[];
          try {
            entries = fsSync.readdirSync(d, { withFileTypes: true });
          } catch {
            continue;
          }
          for (const e of entries) {
            const full = pathMod.join(d, e.name);
            if (e.isDirectory()) {
              out.push(new P(full));
              stack.push(full);
            }
          }
        }
        return;
      }
      walk(dir, idx + 1);
      const stack = [dir];
      while (stack.length) {
        const d = stack.pop()!;
        let entries: fs.Dirent[];
        try {
          entries = fsSync.readdirSync(d, { withFileTypes: true });
        } catch {
          continue;
        }
        for (const e of entries) {
          if (e.isDirectory()) {
            const full = pathMod.join(d, e.name);
            walk(full, idx + 1);
            stack.push(full);
          }
        }
      }
      return;
    }
    const re = _globToRegExp(seg);
    let entries: fs.Dirent[];
    try {
      entries = fsSync.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (!re.test(e.name)) continue;
      const full = pathMod.join(dir, e.name);
      if (last) {
        out.push(new P(full));
      } else if (e.isDirectory()) {
        walk(full, idx + 1);
      }
    }
  };
  walk(rootP, 0);
  void recursive;
  return out;
}

export { P as Path };
export function Counter(items: Iterable<any>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const item of items) {
    const key = String(item);
    out[key] = (out[key] ?? 0) + 1;
  }
  return out;
}

export class PyError extends Error {}
export class PyValueError extends PyError {}
export class PyTypeError extends PyError {}
export class PyKeyError extends PyError {
  key: any;
  constructor(key?: any) {
    super(typeof key === "string" ? `'${key}'` : String(key ?? ""));
    this.key = key;
  }
}
export class PyIndexError extends PyError {}
export class PyAttributeError extends PyError {}
export class PyRuntimeError extends PyError {}
export class PyStopIteration extends PyError {}
export class PyNotImplementedError extends PyError {}
export class PyRecursionError extends PyError {}
export class PyOverflowError extends PyError {}
export class PyAssertionError extends PyError {}
export class PyPermissionError extends PyError {}

export class PyOSError extends PyError {
  errno?: number;
  code?: string;
  constructor(message?: string, errno?: number) {
    super(message);
    if (errno !== undefined) this.errno = errno;
  }
}
export class FileNotFoundError extends PyOSError {
  constructor(message?: string) {
    super(message ?? "[Errno 2] No such file or directory");
    this.errno = 2;
    this.code = "ENOENT";
  }
}
export class FileExistsError extends PyOSError {
  constructor(message?: string) {
    super(message ?? "[Errno 17] File exists");
    this.errno = 17;
    this.code = "EEXIST";
  }
}
export class NotADirectoryError extends PyOSError {
  constructor(message?: string) {
    super(message ?? "[Errno 20] Not a directory");
    this.errno = 20;
    this.code = "ENOTDIR";
  }
}
export class IsADirectoryError extends PyOSError {
  constructor(message?: string) {
    super(message ?? "[Errno 21] Is a directory");
    this.errno = 21;
    this.code = "EISDIR";
  }
}
export class PyJSONDecodeError extends PyValueError {}
export class PyUnicodeDecodeError extends PyValueError {}
export class PyUnicodeEncodeError extends PyValueError {}
export class PyModuleNotFoundError extends PyError {}
export class PyImportError extends PyError {}
export class PyTimeoutError extends PyOSError {}

export function pyStr(v: any): string {
  if (v === null || v === undefined) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (v instanceof P) return v._p;
  if (typeof v === "number") return _numStr(v);
  if (typeof v === "string") return v;
  if (v instanceof Set) {
    if (v.size === 0) return "set()";
    return "{" + Array.from(v).map(pyRepr).join(", ") + "}";
  }
  if (v instanceof Map) {
    return "{" + Array.from(v.entries()).map(([k, x]) => `${pyRepr(k)}: ${pyRepr(x)}`).join(", ") + "}";
  }
  if (Array.isArray(v)) return "[" + v.map(pyRepr).join(", ") + "]";
  if (v && v.__tuple__ === true && Array.isArray(v.items)) return "(" + v.items.map(pyRepr).join(", ") + (v.items.length === 1 ? "," : "") + ")";
  if (typeof v === "object") {
    if (typeof v.__str__ === "function") return v.__str__();
    if (typeof v.__repr__ === "function") return v.__repr__();
    return "{" + Object.keys(v).map((k) => `${pyRepr(k)}: ${pyRepr(v[k])}`).join(", ") + "}";
  }
  return String(v);
}

export function pyRepr(v: any): string {
  if (typeof v === "string") {
    if (!/'/.test(v)) return "'" + v.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t") + "'";
    if (!/"/.test(v)) return '"' + v.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t") + '"';
    return "'" + v.replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t") + "'";
  }
  if (v === null || v === undefined) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (typeof v === "number") return _numStr(v);
  return pyStr(v);
}

function _numStr(n: number): string {
  if (Number.isInteger(n)) {
    if (Object.is(n, -0)) return "-0";
    return String(n);
  }
  return String(n);
}

export function pyLen(v: any): number {
  if (v === null || v === undefined) return 0;
  if (typeof v === "string") return v.length;
  if (Array.isArray(v)) return v.length;
  if (v instanceof Set || v instanceof Map) return v.size;
  if (typeof v === "object") return Object.keys(v).length;
  return String(v).length;
}

export function pyBool(v: any): boolean {
  if (v === null || v === undefined) return false;
  if (v === false) return false;
  if (typeof v === "number") return v !== 0;
  if (typeof v === "string") return v.length > 0;
  if (Array.isArray(v)) return v.length > 0;
  if (v instanceof Set || v instanceof Map) return v.size > 0;
  if (typeof v === "object") return Object.keys(v).length > 0;
  return Boolean(v);
}

export function pyInt(v: any, base = 10): number {
  if (typeof v === "number") return Math.trunc(v);
  if (typeof v === "boolean") return v ? 1 : 0;
  const s = String(v).trim();
  if (base === 16) return parseInt(s.replace(/^0x/i, ""), 16);
  const n = parseInt(s, base);
  if (Number.isNaN(n)) throw new PyValueError(`invalid literal for int() with base ${base}: ${pyRepr(v)}`);
  return n;
}

export function pyFloat(v: any): number {
  if (typeof v === "number") return v;
  const n = parseFloat(String(v).trim());
  if (Number.isNaN(n)) throw new PyValueError(`could not convert string to float: ${pyRepr(v)}`);
  return n;
}

export function pySorted<T>(items: Iterable<T>, keyFn?: (x: T) => any, reverse = false): T[] {
  const arr = Array.from(items);
  const kf = keyFn || ((x: any) => x);
  const cmp = (a: T, b: T): number => {
    const ka = kf(a);
    const kb = kf(b);
    return pyCompare(ka, kb);
  };
  arr.sort(cmp);
  if (reverse) arr.reverse();
  return arr;
}

export function pyCompare(a: any, b: any): number {
  if (a && a.__tuple__ && b && b.__tuple__) {
    const n = Math.min(a.items.length, b.items.length);
    for (let i = 0; i < n; i++) {
      const c = pyCompare(a.items[i], b.items[i]);
      if (c !== 0) return c;
    }
    return a.items.length - b.items.length;
  }
  if (typeof a === "number" && typeof b === "number") return a - b;
  const sa = typeof a === "string" ? a : pyStr(a);
  const sb = typeof b === "string" ? b : pyStr(b);
  return sa < sb ? -1 : sa > sb ? 1 : 0;
}

export function pyMin<T>(items: Iterable<T>, keyFn?: (x: T) => any): T {
  let best: T | undefined;
  let bestKey: any;
  for (const x of items) {
    const k = keyFn ? keyFn(x) : x;
    if (best === undefined || pyCompare(k, bestKey) < 0) {
      best = x;
      bestKey = k;
    }
  }
  if (best === undefined) throw new PyValueError("min() arg is an empty sequence");
  return best;
}

export function pyMax<T>(items: Iterable<T>, keyFn?: (x: T) => any): T {
  let best: T | undefined;
  let bestKey: any;
  for (const x of items) {
    const k = keyFn ? keyFn(x) : x;
    if (best === undefined || pyCompare(k, bestKey) > 0) {
      best = x;
      bestKey = k;
    }
  }
  if (best === undefined) throw new PyValueError("max() arg is an empty sequence");
  return best;
}

export function pySum(items: Iterable<any>): number {
  let total = 0;
  for (const x of items) total += x;
  return total;
}

export function pyEnumerate<T>(items: Iterable<T>, start = 0): Array<[number, T]> {
  const out: Array<[number, T]> = [];
  let i = start;
  for (const x of items) out.push([i++, x]);
  return out;
}

export function pyZip(...lists: Array<Iterable<any>>): any[][] {
  const arrays = lists.map((l) => Array.from(l));
  const n = Math.min(...arrays.map((a) => a.length));
  const out: any[][] = [];
  for (let i = 0; i < n; i++) out.push(arrays.map((a) => a[i]));
  return out;
}

export function pyRange(a: number, b?: number, step = 1): number[] {
  const start = b === undefined ? 0 : a;
  const stop = b === undefined ? a : b;
  const out: number[] = [];
  if (step > 0) for (let i = start; i < stop; i += step) out.push(i);
  else for (let i = start; i > stop; i += step) out.push(i);
  return out;
}

export function pyIsInstance(v: any, ...types: any[]): boolean {
  for (const t of types) {
    if (t === String || t === "str") {
      if (typeof v === "string") return true;
    } else if (t === Number || t === "int" || t === "float") {
      if (typeof v === "number") return true;
      if (t === "int" && typeof v === "boolean") return true;
    } else if (t === "int") {
      if (typeof v === "number" && Number.isInteger(v)) return true;
    } else if (t === Boolean || t === "bool") {
      if (typeof v === "boolean") return true;
    } else if (t === Array || t === "list") {
      if (Array.isArray(v)) return true;
    } else if (t === "dict") {
      if (typeof v === "object" && v !== null && !Array.isArray(v) && !(v instanceof Set) && !(v instanceof Map)) return true;
    } else if (t === Set || t === "set" || t === "frozenset") {
      if (v instanceof Set) return true;
    } else if (t === "bytes" || t === "bytearray") {
      if (Buffer.isBuffer(v) || v instanceof Uint8Array) return true;
    } else if (typeof t === "function") {
      if (v instanceof t) return true;
    }
  }
  return false;
}

export function pyJsonDumps(value: any, opts: { ensure_ascii?: boolean; sort_keys?: boolean; separators?: [string, string]; indent?: number | null } = {}): string {
  const ensureAscii = opts.ensure_ascii !== false;
  const sortKeys = opts.sort_keys === true;
  let sep = opts.separators;
  let sepItem = ", ";
  let sepKey = ": ";
  if (opts.indent != null) {
    sepItem = ",";
    sepKey = ": ";
  }
  if (sep) {
    sepItem = sep[0];
    sepKey = sep[1];
  }
  const ser = (v: any, level: number): string => {
    if (v === null || v === undefined) return "null";
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "number") return _jsonNumberStr(v);
    if (typeof v === "string") return _jsonStrStr(v, ensureAscii);
    if (Buffer.isBuffer(v)) throw new PyTypeError("Object of type bytes is not JSON serializable");
    if (Array.isArray(v)) {
      if (v.length === 0) return "[]";
      const pad = opts.indent != null ? "\n" + " ".repeat(opts.indent * (level + 1)) : "";
      const padEnd = opts.indent != null ? "\n" + " ".repeat(opts.indent * level) : "";
      const itemSep = opts.indent != null ? "," : sepItem;
      return "[" + pad + v.map((x) => ser(x, level + 1)).join(itemSep + (opts.indent != null ? "" : "")) + padEnd + "]";
    }
    if (v instanceof Set) throw new PyTypeError("Object of type set is not JSON serializable");
    if (typeof v === "object") {
      let keys = Object.keys(v);
      if (sortKeys) keys = keys.sort();
      if (keys.length === 0) return "{}";
      const pad = opts.indent != null ? "\n" + " ".repeat(opts.indent * (level + 1)) : "";
      const padEnd = opts.indent != null ? "\n" + " ".repeat(opts.indent * level) : "";
      const itemSep = opts.indent != null ? "," : sepItem;
      return "{" + pad + keys.map((k) => _jsonStrStr(k, ensureAscii) + sepKey + ser(v[k], level + 1)).join(itemSep) + padEnd + "}";
    }
    throw new PyTypeError(`Object of type ${typeof v} is not JSON serializable`);
  };
  return ser(value, 0);
}

function _jsonNumberStr(n: number): string {
  if (Number.isInteger(n)) return Object.is(n, -0) ? "-0.0" : String(n);
  if (!Number.isFinite(n)) {
    if (Number.isNaN(n)) return "NaN";
    return n > 0 ? "Infinity" : "-Infinity";
  }
  return String(n);
}

function _jsonStrStr(s: string, ensureAscii: boolean): string {
  let out = '"';
  for (const ch of s) {
    const code = ch.codePointAt(0)!;
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\f") out += "\\f";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (code < 0x20) out += "\\u" + code.toString(16).padStart(4, "0");
    else if (ensureAscii && code > 0x7f) {
      if (code <= 0xffff) {
        out += "\\u" + code.toString(16).padStart(4, "0");
      } else {
        const hi = 0xd800 + ((code - 0x10000) >> 10);
        const lo = 0xdc00 + ((code - 0x10000) & 0x3ff);
        out += "\\u" + hi.toString(16) + "\\u" + lo.toString(16);
      }
    } else out += ch;
  }
  return out + '"';
}

export function pyJsonLoads(text: string | Buffer): any {
  const s = typeof text === "string" ? text : text.toString("utf8");
  try {
    return JSON.parse(s);
  } catch (e: any) {
    throw new PyJSONDecodeError(String(e && e.message ? e.message : e));
  }
}

export class RE {
  _re: RegExp;
  _source: string;
  constructor(pattern: string, flags = "") {
    this._source = pattern;
    const src = _translateRegex(pattern);
    this._re = new RegExp(src, flags.includes("g") ? flags : flags + (flags.includes("g") ? "" : ""));
  }
  static compile(pattern: string, flags = ""): RE {
    return new RE(pattern, flags);
  }
  search(text: string, pos = 0): Match | null {
    const re = new RegExp(this._re.source, _stripG(this._re.flags));
    const hay = pos ? text.slice(pos) : text;
    const m = re.exec(hay);
    if (!m) return null;
    return new Match(m, pos, text);
  }
  match(text: string, pos = 0): Match | null {
    const re = new RegExp("^(?:" + this._re.source + ")", _stripG(this._re.flags));
    const m = re.exec(pos ? text.slice(pos) : text);
    if (!m) return null;
    return new Match(m, pos, text);
  }
  fullmatch(text: string): Match | null {
    const re = new RegExp("^(?:" + this._re.source + ")$", _stripG(this._re.flags));
    const m = re.exec(text);
    if (!m) return null;
    return new Match(m, 0, text);
  }
  findall(text: string): any[] {
    const re = new RegExp(this._re.source, _ensureG(this._re.flags));
    const out: any[] = [];
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      if (m.length > 2) {
        out.push({ __tuple__: true, items: m.slice(1) });
      } else if (m.length === 2) {
        out.push(m[1]);
      } else {
        out.push(m[0]);
      }
      if (m[0] === "") re.lastIndex++;
    }
    return out;
  }
  finditer(text: string): Match[] {
    const re = new RegExp(this._re.source, _ensureG(this._re.flags));
    const out: Match[] = [];
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      out.push(new Match(m, 0, text));
      if (m[0] === "") re.lastIndex++;
    }
    return out;
  }
  sub(replacement: any, text: string, count = 0): string {
    let flags = _ensureG(this._re.flags);
    const re = new RegExp(this._re.source, flags);
    const rep = typeof replacement === "function"
      ? (...args: any[]) => {
          const m = args.slice(0, args.length - 2);
          const match = new Match(args as any, 0, args[args.length - 1]);
          return replacement(match);
        }
      : _translateReplacement(String(replacement));
    if (count > 0) {
      let n = 0;
      return text.replace(re, (...args) => {
        n++;
        if (n > count) return args[0];
        if (typeof replacement === "function") return replacement(new Match(args as any, 0, args[args.length - 1]));
        return _translateReplacement(String(replacement)).replace(/\$(\d)/g, (_m: string, g: string) => args[Number(g)] ?? "");
      });
    }
    if (typeof replacement === "function") {
      return text.replace(re, (...args) => replacement(new Match(args as any, 0, args[args.length - 1])));
    }
    return text.replace(re, _translateReplacement(String(replacement)));
  }
  subn(replacement: any, text: string, count = 0): [string, number] {
    let n = 0;
    const result = this.sub((...args: any[]) => {
      n++;
      if (typeof replacement === "function") return replacement(args[0]);
      return replacement;
    }, text, count);
    return [result, n];
  }
  split(text: string, maxsplit = 0): string[] {
    const re = new RegExp(this._re.source, _stripG(this._re.flags));
    if (maxsplit > 0) {
      const out: string[] = [];
      let rest = text;
      let n = 0;
      let m: RegExpExecArray | null;
      const gre = new RegExp(this._re.source, _ensureG(this._re.flags));
      let lastIndex = 0;
      let lastEnd = 0;
      const parts: string[] = [];
      while ((m = gre.exec(text)) !== null && n < maxsplit) {
        parts.push(text.slice(lastEnd, m.index));
        for (let g = 1; g < m.length; g++) parts.push(m[g]);
        lastEnd = m.index + m[0].length;
        if (m[0] === "") gre.lastIndex++;
        n++;
      }
      parts.push(text.slice(lastEnd));
      void lastIndex;
      void rest;
      return parts;
    }
    return text.split(re);
  }
  get pattern(): string {
    return this._source;
  }
  test(text: string): boolean {
    return this.search(text) !== null;
  }
}

function _stripG(flags: string): string {
  return flags.replace("g", "");
}
function _ensureG(flags: string): string {
  return flags.includes("g") ? flags : flags + "g";
}

export class Match {
  _m: any;
  _pos: number;
  _text: string;
  constructor(m: any, pos: number, text: string) {
    if (Array.isArray(m)) {
      this._m = { 0: m[0], length: m.length, index: (m as any).index, groups: undefined } as any;
      for (let i = 0; i < m.length; i++) this._m[i] = m[i];
      this._m.index = typeof (m as any).index === "number" ? (m as any).index : 0;
      this._m.groups = (m as any).groups;
    } else {
      this._m = m;
    }
    this._pos = pos;
    this._text = text;
  }
  group(n: any = 0): any {
    if (typeof n === "string") {
      const g = this._m.groups;
      return g ? g[n] : undefined;
    }
    return this._m[n];
  }
  groups(): any[] {
    return Array.prototype.slice.call(this._m, 1).map((x: any) => (x === undefined ? null : x));
  }
  groupdict(): Record<string, any> {
    const g = this._m.groups || {};
    const out: Record<string, any> = {};
    for (const k of Object.keys(g)) out[k] = g[k] === undefined ? null : g[k];
    return out;
  }
  start(n = 0): number {
    if (n === 0) return this._pos + (this._m.index || 0);
    const needle = this._m[n];
    if (needle === undefined || needle === null) return -1;
    return this._pos + this._text.slice(this._m.index).indexOf(needle);
  }
  end(n = 0): number {
    if (n === 0) return this._pos + (this._m.index || 0) + String(this._m[0]).length;
    const needle = this._m[n];
    if (needle === undefined || needle === null) return -1;
    return this.start(n) + String(needle).length;
  }
  span(n = 0): [number, number] {
    return [this.start(n), this.end(n)];
  }
}

function _translateRegex(pattern: string): string {
  let out = "";
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i];
    if (c === "\\" && i + 1 < pattern.length) {
      const n = pattern[i + 1];
      if (n === "A") {
        out += "^";
        i++;
        continue;
      }
      if (n === "Z") {
        out += "$";
        i++;
        continue;
      }
      out += c + n;
      i++;
      continue;
    }
    if (c === "(" && pattern.slice(i, i + 3) === "(?P<") {
      const end = pattern.indexOf(">", i);
      if (end > 0) {
        out += "(?<" + pattern.slice(i + 4, end) + ">";
        i = end;
        continue;
      }
    }
    if (c === "(" && pattern.slice(i, i + 3) === "(?P=") {
      const end = pattern.indexOf(")", i);
      if (end > 0) {
        out += "\\k<" + pattern.slice(i + 3, end) + ">";
        i = end;
        continue;
      }
    }
    out += c;
  }
  return out;
}

function _translateReplacement(rep: string): string {
  return rep.replace(/\\(\d+)/g, (_m, g) => `$${g}`).replace(/\\g<(\w+)>/g, (_m, name) => `$<${name}>`);
}

export function reSearch(pattern: string | RE, text: string, flags = ""): Match | null {
  const re = typeof pattern === "string" ? new RE(pattern, flags) : pattern;
  return re.search(text);
}
export function reMatch(pattern: string | RE, text: string, flags = ""): Match | null {
  const re = typeof pattern === "string" ? new RE(pattern, flags) : pattern;
  return re.match(text);
}
export function reFullmatch(pattern: string | RE, text: string, flags = ""): Match | null {
  const re = typeof pattern === "string" ? new RE(pattern, flags) : pattern;
  return re.fullmatch(text);
}
export function reFindall(pattern: string | RE, text: string, flags = ""): any[] {
  const re = typeof pattern === "string" ? new RE(pattern, flags) : pattern;
  return re.findall(text);
}
export function reFinditer(pattern: string | RE, text: string, flags = ""): Match[] {
  const re = typeof pattern === "string" ? new RE(pattern, flags) : pattern;
  return re.finditer(text);
}
export function reSub(pattern: string | RE, replacement: any, text: string, count = 0, flags = ""): string {
  const re = typeof pattern === "string" ? new RE(pattern, flags) : pattern;
  return re.sub(replacement, text, count);
}
export function reSplit(pattern: string | RE, text: string, maxsplit = 0, flags = ""): string[] {
  const re = typeof pattern === "string" ? new RE(pattern, flags) : pattern;
  return re.split(text, maxsplit);
}

export const reFlags = {
  IGNORECASE: "i",
  I: "i",
  MULTILINE: "m",
  M: "m",
  DOTALL: "s",
  S: "s",
  VERBOSE: "x",
  X: "x",
  ASCII: "a",
};

export function strSplit(s: string, sep?: string | null, maxsplit = -1): string[] {
  if (sep === null || sep === undefined) {
    const trimmed = s.replace(/^\s+/, "");
    if (trimmed === "") return [];
    const parts = trimmed.split(/\s+/);
    if (maxsplit >= 0 && parts.length > maxsplit + 1) {
      const head = parts.slice(0, maxsplit);
      const rest = parts.slice(maxsplit).join(" ");
      return [...head, rest];
    }
    return parts;
  }
  if (maxsplit < 0) return s.split(sep);
  const out: string[] = [];
  let rest = s;
  let n = 0;
  while (n < maxsplit) {
    const i = rest.indexOf(sep);
    if (i < 0) break;
    out.push(rest.slice(0, i));
    rest = rest.slice(i + sep.length);
    n++;
  }
  out.push(rest);
  return out;
}

export function strRsplit(s: string, sep?: string | null, maxsplit = -1): string[] {
  if (sep === null || sep === undefined) {
    if (maxsplit < 0) return strSplit(s, null, -1);
    const parts = strSplit(s, null, -1);
    if (parts.length <= maxsplit + 1) return parts;
    return [parts.slice(0, parts.length - maxsplit).join(" "), ...parts.slice(parts.length - maxsplit)];
  }
  if (maxsplit < 0) return s.split(sep);
  const idxs: number[] = [];
  let i = s.indexOf(sep);
  while (i >= 0) {
    idxs.push(i);
    i = s.indexOf(sep, i + sep.length);
  }
  const cut = idxs.slice(Math.max(0, idxs.length - maxsplit));
  const out: string[] = [];
  let last = 0;
  for (const idx of cut) {
    out.push(s.slice(last, idx));
    last = idx + sep.length;
  }
  out.push(s.slice(last));
  return out;
}

export function strJoin(sep: string, items: Iterable<any>): string {
  return Array.from(items).map((x) => String(x instanceof P ? x._p : x)).join(sep);
}

export function strStrip(s: string, chars?: string): string {
  if (chars === undefined) return s.trim();
  return _stripChars(s, chars, true, true);
}
export function strLstrip(s: string, chars?: string): string {
  if (chars === undefined) return s.replace(/^\s+/, "");
  return _stripChars(s, chars, true, false);
}
export function strRstrip(s: string, chars?: string): string {
  if (chars === undefined) return s.replace(/\s+$/, "");
  return _stripChars(s, chars, false, true);
}
function _stripChars(s: string, chars: string, left: boolean, right: boolean): string {
  const set = new Set(chars.split(""));
  let a = 0;
  let b = s.length;
  if (left) while (a < b && set.has(s[a])) a++;
  if (right) while (b > a && set.has(s[b - 1])) b--;
  return s.slice(a, b);
}

export function strPartition(s: string, sep: string): [string, string, string] {
  const i = s.indexOf(sep);
  if (i < 0) return [s, "", ""];
  return [s.slice(0, i), sep, s.slice(i + sep.length)];
}
export function strRpartition(s: string, sep: string): [string, string, string] {
  const i = s.lastIndexOf(sep);
  if (i < 0) return ["", "", s];
  return [s.slice(0, i), sep, s.slice(i + sep.length)];
}

export function strRemoveprefix(s: string, prefix: string): string {
  return s.startsWith(prefix) ? s.slice(prefix.length) : s;
}
export function strRemovesuffix(s: string, suffix: string): string {
  return suffix !== "" && s.endsWith(suffix) ? s.slice(0, s.length - suffix.length) : s;
}

export function strZfill(s: string, width: number): string {
  if (s.length >= width) return s;
  const pad = "0".repeat(width - s.length);
  if (s.startsWith("+") || s.startsWith("-")) return s[0] + pad + s.slice(1);
  return pad + s;
}

export function strCenter(s: string, width: number, fill = " "): string {
  if (s.length >= width) return s;
  const total = width - s.length;
  const left = Math.floor(total / 2) + (total % 2 && width % 2 ? 1 : 0);
  return fill.repeat(left) + s + fill.repeat(total - left);
}

export function pyDivmod(a: number, b: number): [number, number] {
  const q = Math.floor(a / b);
  return [q, a - q * b];
}

export function pyFloorDiv(a: number, b: number): number {
  return Math.floor(a / b);
}

export function pyMod(a: number, b: number): number {
  return ((a % b) + b) % b;
}

export function pyPow(a: number, b: number): number {
  return Math.pow(a, b);
}

export function pyHash(value: any): string {
  const crypto = require("node:crypto");
  return crypto.createHash("sha256").update(Buffer.from(String(value))).digest("hex");
}

export function osGetenv(name: string, def?: any): any {
  const v = process.env[name];
  return v === undefined ? (def === undefined ? null : def) : v;
}

export function pyList(v: any): any[] {
  if (Array.isArray(v)) return [...v];
  if (v instanceof Set) return Array.from(v);
  if (v instanceof Map) return Array.from(v.keys());
  if (typeof v === "string") return v.split("");
  if (v && typeof v[Symbol.iterator] === "function") return Array.from(v);
  if (typeof v === "object" && v !== null) return Object.keys(v);
  return [];
}

export function pyDict(v?: any): Record<string, any> {
  if (v === undefined || v === null) return {};
  if (v instanceof Map) return Object.fromEntries(v);
  if (Array.isArray(v)) {
    const out: Record<string, any> = {};
    for (const pair of v) out[pair[0]] = pair[1];
    return out;
  }
  return { ...v };
}

export function pySet(v?: Iterable<any>): Set<any> {
  return new Set(v ?? []);
}

export function pyTuple(...items: any[]): any {
  return { __tuple__: true, items };
}

export function dictGet(d: any, key: any, def: any = null): any {
  if (d instanceof Map) return d.has(key) ? d.get(key) : def;
  if (typeof d === "object" && d !== null) {
    return Object.prototype.hasOwnProperty.call(d, key) ? d[key] : def;
  }
  return def;
}

export function dictPop(d: any, key: any, def?: any): any {
  if (d instanceof Map) {
    if (d.has(key)) {
      const v = d.get(key);
      d.delete(key);
      return v;
    }
    if (arguments.length >= 3) return def;
    throw new PyKeyError(key);
  }
  if (typeof d === "object" && d !== null && Object.prototype.hasOwnProperty.call(d, key)) {
    const v = d[key];
    delete d[key];
    return v;
  }
  if (arguments.length >= 3) return def;
  throw new PyKeyError(key);
}

export function dictSetdefault(d: any, key: any, def: any = null): any {
  if (d instanceof Map) {
    if (!d.has(key)) d.set(key, def);
    return d.get(key);
  }
  if (!Object.prototype.hasOwnProperty.call(d, key)) d[key] = def;
  return d[key];
}

export function inOp(item: any, container: any): boolean {
  if (container instanceof Set) return container.has(item);
  if (container instanceof Map) return container.has(item);
  if (typeof container === "string") return container.includes(String(item));
  if (Array.isArray(container)) return container.includes(item);
  if (typeof container === "object" && container !== null) return Object.prototype.hasOwnProperty.call(container, item);
  return false;
}

export function pyChr(n: number): string {
  return String.fromCodePoint(n);
}
export function pyOrd(c: string): number {
  return c.codePointAt(0)!;
}
export function pyHex(n: number): string {
  return (n < 0 ? "-0x" : "0x") + Math.abs(n).toString(16);
}
export function pyOct(n: number): string {
  return (n < 0 ? "-0o" : "0o") + Math.abs(n).toString(8);
}
export function pyBin(n: number): string {
  return (n < 0 ? "-0b" : "0b") + Math.abs(n).toString(2);
}
export function pyAbs(n: number): number {
  return Math.abs(n);
}
export function pyRound(n: number, ndigits?: number): number {
  if (ndigits === undefined) {
    const floor = Math.floor(n);
    const diff = n - floor;
    if (diff > 0.5) return floor + 1;
    if (diff < 0.5) return floor;
    return floor % 2 === 0 ? floor : floor + 1;
  }
  const f = Math.pow(10, ndigits);
  return pyRound(n * f) / f;
}

export function pyAny(items: Iterable<any>): boolean {
  for (const x of items) if (pyBool(x)) return true;
  return false;
}
export function pyAll(items: Iterable<any>): boolean {
  for (const x of items) if (!pyBool(x)) return false;
  return true;
}

export function pyNext<T>(it: Iterator<T>, def?: any): T {
  const r = it.next();
  if (r.done) {
    if (arguments.length >= 2) return def;
    throw new PyStopIteration();
  }
  return r.value;
}

export function* iterOf<T>(v: Iterable<T>): Generator<T> {
  yield* v;
}

export function pySlice<T>(arr: T[], start?: number | null, stop?: number | null, step?: number): T[] {
  const s = step ?? 1;
  const n = arr.length;
  const norm = (i: number | null | undefined, dflt: number): number => {
    if (i === null || i === undefined) return dflt;
    let v = i;
    if (v < 0) v = Math.max(0, v + n);
    else v = Math.min(n, v);
    return v;
  };
  if (s > 0) {
    const a = norm(start, 0);
    const b = norm(stop, n);
    const out: T[] = [];
    for (let i = a; i < b; i += s) out.push(arr[i]);
    return out;
  }
  const a = start === null || start === undefined ? n - 1 : start < 0 ? Math.max(-1, start + n) : Math.min(n - 1, start);
  const b = stop === null || stop === undefined ? -1 : stop < 0 ? Math.max(-1, stop + n) : stop;
  const out: T[] = [];
  for (let i = a; i > b; i += s) out.push(arr[i]);
  return out;
}

export function strSlice(s: string, start?: number | null, stop?: number | null, step?: number): string {
  return pySlice(s.split(""), start, stop, step).join("");
}

export function pyBytesFromHex(hex: string): Buffer {
  return Buffer.from(hex, "hex");
}

export function bytesHex(buf: Buffer | Uint8Array): string {
  return Buffer.from(buf).toString("hex");
}

export function pyFormat(template: string, ...args: any[]): string {
  let idx = 0;
  return template.replace(/\{([^{}]*)\}/g, (_m, spec: string) => {
    const [field, ...rest] = spec.split(":");
    const fmt = rest.join(":");
    let value: any;
    if (field === "") {
      value = args[idx++];
    } else if (/^\d+$/.test(field)) {
      value = args[Number(field)];
    } else {
      const parts = field.split(".");
      value = args[0];
      for (const part of parts) {
        if (value && typeof value === "object") value = value[part];
      }
    }
    return _formatValue(value, fmt);
  });
}

function _formatValue(value: any, fmt: string): string {
  if (!fmt) return pyStr(value);
  const m = /^([<>=^])?([+\- ])?(\d+)?(?:\.(\d+))?([bcdeEfFgGnosxX%])?$/.exec(fmt);
  if (!m) return pyStr(value);
  const [, align, sign, widthS, precS, type] = m;
  let text: string;
  const t = type || "";
  if (t === "f" || t === "F") {
    text = Number(value).toFixed(precS !== undefined ? Number(precS) : 6);
  } else if (t === "d" || t === "n" || t === "") {
    text = String(value);
  } else if (t === "x") {
    text = Number(value).toString(16);
  } else if (t === "X") {
    text = Number(value).toString(16).toUpperCase();
  } else if (t === "s") {
    text = pyStr(value);
  } else if (t === "%") {
    text = (Number(value) * 100).toFixed(precS !== undefined ? Number(precS) : 6) + "%";
  } else if (t === "e" || t === "E") {
    text = Number(value).toExponential(precS !== undefined ? Number(precS) : 6);
    if (t === "E") text = text.toUpperCase();
  } else {
    text = String(value);
  }
  if (sign === "+" && !text.startsWith("-") && !Number.isNaN(Number(text))) text = "+" + text;
  if (widthS) {
    const width = Number(widthS);
    if (text.length < width) {
      const pad = width - text.length;
      if (align === "<") text = text + " ".repeat(pad);
      else if (align === "^") {
        const l = Math.floor(pad / 2);
        text = " ".repeat(l) + text + " ".repeat(pad - l);
      } else text = " ".repeat(pad) + text;
    }
  }
  return text;
}

export function deepcopy<T>(v: T): T {
  if (v === null || typeof v !== "object") return v;
  if (Buffer.isBuffer(v)) return Buffer.from(v) as any;
  if (v instanceof P) return new P(v._p) as any;
  if (v instanceof Set) return new Set(Array.from(v).map((x) => deepcopy(x))) as any;
  if (v instanceof Map) return new Map(Array.from(v.entries()).map(([k, x]) => [deepcopy(k), deepcopy(x)])) as any;
  if (Array.isArray(v)) return v.map((x) => deepcopy(x)) as any;
  const out: any = {};
  for (const k of Object.keys(v as any)) out[k] = deepcopy((v as any)[k]);
  return out;
}

export function pyShutilCopytree(src: string, dst: string): void {
  fsSync.cpSync(src, dst, { recursive: true });
}
export function pyShutilRmtree(p: string, ignoreErrors = false): void {
  try {
    fsSync.rmSync(p, { recursive: true, force: true });
  } catch (e) {
    if (!ignoreErrors) throw e;
  }
}
export function pyShutilCopy(src: string, dst: string): string {
  fsSync.copyFileSync(src, dst);
  return dst;
}
export function pyShutilMove(src: string, dst: string): string {
  fsSync.renameSync(src, dst);
  return dst;
}

export function listDir(p: string): string[] {
  return fsSync.readdirSync(p);
}

export function makedirs(p: string, existOk = false): void {
  if (existOk) {
    fsSync.mkdirSync(p, { recursive: true });
    return;
  }
  fsSync.mkdirSync(p);
}

export function pyWalk(root: string): Array<[string, string[], string[]]> {
  const out: Array<[string, string[], string[]]> = [];
  const walk = (dir: string): void => {
    let entries: fs.Dirent[];
    try {
      entries = fsSync.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    const dirs: string[] = [];
    const filesArr: string[] = [];
    for (const e of entries) {
      if (e.isDirectory()) dirs.push(e.name);
      else filesArr.push(e.name);
    }
    out.push([dir, dirs, filesArr]);
    for (const d of dirs) walk(pathMod.join(dir, d));
  };
  walk(root);
  return out;
}

export function isoNow(): string {
  return new Date().toISOString();
}

export function timeTime(): number {
  return Date.now() / 1000;
}
export function timeTimeNs(): bigint {
  return process.hrtime.bigint();
}
export function timeMonotonic(): number {
  return Number(process.hrtime.bigint()) / 1e9;
}
export function timeSleep(seconds: number): void {
  const end = Date.now() + seconds * 1000;
  while (Date.now() < end) {}
}

export function dtIsoformat(d: Date): string {
  return d.toISOString().replace("Z", "+00:00");
}

export function pyExit(code = 0): never {
  process.exit(code);
}

export function sysStderrWrite(text: string): void {
  process.stderr.write(text);
}
export function sysStdoutWrite(text: string): void {
  process.stdout.write(text);
}
