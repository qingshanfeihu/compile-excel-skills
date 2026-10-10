import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export type ErrorType<E extends Error = Error> = new (message?: string) => E;
export type FileIdentity = [number, number, number, number, number];

function _identity(info: fs.Stats): FileIdentity {
  return [Number(info.dev), Number(info.ino), Number(info.size), Number(info.mtimeMs), Number(info.ctimeMs)];
}

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function canonicalJsonString(value: any): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return Object.is(value, -0) ? "-0.0" : String(value);
    return String(value);
  }
  if (typeof value === "string") return _jsonStr(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalJsonString).join(",") + "]";
  const keys = Object.keys(value).sort();
  return "{" + keys.map((k) => _jsonStr(k) + ":" + canonicalJsonString(value[k])).join(",") + "}";
}

function _jsonStr(s: string): string {
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
    else out += ch;
  }
  return out + '"';
}

export function canonical_json(value: any, opts: { ensure_ascii?: boolean; omit?: string | Iterable<string> | null } = {}): Buffer {
  let body: any = _isMapping(value) ? { ...value } : value;
  if (_isMapping(body)) {
    const omitted = typeof opts.omit === "string" ? [opts.omit] : Array.from(opts.omit ?? []);
    for (const field of omitted) {
      delete body[field];
    }
  }
  let text = canonicalJsonString(body);
  if (opts.ensure_ascii !== false) {
    text = text.replace(/[^\x00-\x7f]/g, (ch) => {
      const code = ch.codePointAt(0)!;
      if (code <= 0xffff) {
        return "\\u" + code.toString(16).padStart(4, "0");
      }
      const hi = 0xd800 + ((code - 0x10000) >> 10);
      const lo = 0xdc00 + ((code - 0x10000) & 0x3ff);
      return "\\u" + hi.toString(16) + "\\u" + lo.toString(16);
    });
  }
  return Buffer.from(text, "utf8");
}

export function sha256_bytes(value: Buffer): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

export const CONTRACT_CARD_MAX_BYTES = 4 * 1024 * 1024;
const _BUDGET_UNBOUNDED = 1 << 30;

export function scan_json_budget(payload: Buffer | string, opts: { abort_tokens?: number | null; abort_depth?: number | null } = {}): [number, number] {
  const raw = typeof payload === "string" ? Buffer.from(payload, "utf8") : payload;
  const stopTokens = opts.abort_tokens == null ? _BUDGET_UNBOUNDED : opts.abort_tokens;
  const stopDepth = opts.abort_depth == null ? _BUDGET_UNBOUNDED : opts.abort_depth;
  const aborting = opts.abort_tokens != null || opts.abort_depth != null;
  let depth = 0;
  let maxDepth = 0;
  let tokens = 0;
  let inString = false;
  let escaped = false;
  for (const byte of raw) {
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (byte === 92) {
        escaped = true;
      } else if (byte === 34) {
        inString = false;
      }
      continue;
    }
    if (byte === 34) {
      inString = true;
      continue;
    }
    if (byte === 123 || byte === 91) {
      depth += 1;
      tokens += 1;
      if (depth > maxDepth) maxDepth = depth;
    } else if (byte === 125 || byte === 93) {
      depth = Math.max(0, depth - 1);
      continue;
    } else if (byte === 44) {
      tokens += 1;
    } else {
      continue;
    }
    if (aborting && (maxDepth > stopDepth || tokens > stopTokens)) {
      return [tokens, maxDepth];
    }
  }
  return [tokens, maxDepth];
}

export function validate_json_budget<E extends Error>(
  payload: Buffer | string,
  opts: { errorType: ErrorType<E>; message: string; maxDepth?: number; maxTokens?: number }
): void {
  const [tokens, depth] = scan_json_budget(payload, { abort_tokens: opts.maxTokens ?? 500000, abort_depth: opts.maxDepth ?? 128 });
  if (depth > (opts.maxDepth ?? 128) || tokens > (opts.maxTokens ?? 500000)) {
    throw new opts.errorType(opts.message);
  }
}

export function file_identity(info: fs.Stats): FileIdentity {
  return _identity(info);
}

export function validate_xlsx_zip_budget<E extends Error>(
  payload: Buffer,
  opts: {
    errorType: ErrorType<E>;
    message: string;
    max_members?: number;
    max_member_bytes?: number;
    max_total_bytes?: number;
    max_compression_ratio?: number;
    max_central_directory_bytes?: number;
  }
): void {
  const maxMembers = opts.max_members ?? 4096;
  const maxMemberBytes = opts.max_member_bytes ?? 128 * 1024 * 1024;
  const maxTotalBytes = opts.max_total_bytes ?? 512 * 1024 * 1024;
  const maxCompressionRatio = opts.max_compression_ratio ?? 500;
  const maxCentralDirectoryBytes = opts.max_central_directory_bytes ?? 32 * 1024 * 1024;
  const fail = (): never => {
    throw new opts.errorType(opts.message);
  };
  try {
    const tailStart = Math.max(0, payload.length - (65535 + 22));
    const eocdOffset = payload.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]), payload.length);
    let eocd = -1;
    for (let i = payload.length - 22; i >= tailStart; i--) {
      if (payload[i] === 0x50 && payload[i + 1] === 0x4b && payload[i + 2] === 0x05 && payload[i + 3] === 0x06) {
        eocd = i;
        break;
      }
    }
    void eocdOffset;
    if (eocd < 0 || eocd + 22 > payload.length) fail();
    const diskNumber = payload.readUInt16LE(eocd + 4);
    const centralDisk = payload.readUInt16LE(eocd + 6);
    const entriesOnDisk = payload.readUInt16LE(eocd + 8);
    let totalEntries = payload.readUInt16LE(eocd + 10);
    let centralSize = payload.readUInt32LE(eocd + 12);
    let centralOffset = payload.readUInt32LE(eocd + 16);
    const commentSize = payload.readUInt16LE(eocd + 20);
    if (eocd + 22 + commentSize !== payload.length) fail();
    if (diskNumber !== 0 || centralDisk !== 0 || entriesOnDisk !== totalEntries) fail();
    if (totalEntries === 65535 || centralSize === 4294967295 || centralOffset === 4294967295) {
      const locatorOffset = eocd - 20;
      if (locatorOffset < 0 || payload.readUInt32LE(locatorOffset) !== 0x07064b50) fail();
      const zip64Disk = payload.readUInt32LE(locatorOffset + 4);
      const zip64Offset = Number(payload.readBigUInt64LE(locatorOffset + 8));
      const diskCount = payload.readUInt32LE(locatorOffset + 16);
      if (zip64Disk !== 0 || diskCount !== 1 || zip64Offset + 56 > payload.length) fail();
      if (payload.readUInt32LE(zip64Offset) !== 0x06064b50) fail();
      const zip64RecordSize = Number(payload.readBigUInt64LE(zip64Offset + 4));
      const zip64DiskNumber = payload.readUInt32LE(zip64Offset + 16);
      const zip64CentralDisk = payload.readUInt32LE(zip64Offset + 20);
      const zip64EntriesOnDisk = Number(payload.readBigUInt64LE(zip64Offset + 24));
      totalEntries = Number(payload.readBigUInt64LE(zip64Offset + 32));
      centralSize = Number(payload.readBigUInt64LE(zip64Offset + 40));
      centralOffset = Number(payload.readBigUInt64LE(zip64Offset + 48));
      if (zip64RecordSize < 44 || zip64DiskNumber !== 0 || zip64CentralDisk !== 0 || zip64EntriesOnDisk !== totalEntries) fail();
    }
    if (totalEntries > maxMembers || centralSize > maxCentralDirectoryBytes) fail();
    let offset = centralOffset;
    let total = 0;
    let count = 0;
    for (let i = 0; i < totalEntries; i++) {
      if (offset + 46 > payload.length || payload.readUInt32LE(offset) !== 0x02014b50) fail();
      const flagBits = payload.readUInt16LE(offset + 8);
      const compressedRaw = payload.readUInt32LE(offset + 20);
      const sizeRaw = payload.readUInt32LE(offset + 24);
      const nameLen = payload.readUInt16LE(offset + 28);
      const extraLen = payload.readUInt16LE(offset + 30);
      const commentLen = payload.readUInt16LE(offset + 32);
      const nameBuf = payload.subarray(offset + 46, offset + 46 + nameLen);
      const extra = payload.subarray(offset + 46 + nameLen, offset + 46 + nameLen + extraLen);
      let size = sizeRaw;
      let compressed = compressedRaw;
      if (sizeRaw === 0xffffffff || compressedRaw === 0xffffffff) {
        for (let p = 0; p + 4 <= extra.length; ) {
          const tag = extra.readUInt16LE(p);
          const len = extra.readUInt16LE(p + 2);
          if (p + 4 + len > extra.length) break;
          if (tag === 0x0001) {
            let q = p + 4;
            if (sizeRaw === 0xffffffff && q + 8 <= p + 4 + len) {
              size = Number(extra.readBigUInt64LE(q));
              q += 8;
            }
            if (compressedRaw === 0xffffffff && q + 8 <= p + 4 + len) {
              compressed = Number(extra.readBigUInt64LE(q));
              q += 8;
            }
          }
          p += 4 + len;
        }
      }
      const name = nameBuf.toString("utf8");
      const parts = name.split(/[\\/]+/);
      if (!name || name.startsWith("/") || name.startsWith("\\") || parts.includes("..") || name.includes("") || flagBits & 1) {
        fail();
      }
      total += size;
      if (size > maxMemberBytes || total > maxTotalBytes) fail();
      if (size && (compressed <= 0 || size > compressed * maxCompressionRatio)) fail();
      count += 1;
      offset += 46 + nameLen + extraLen + commentLen;
    }
    if (count > maxMembers) fail();
  } catch (exc) {
    if (exc instanceof opts.errorType) throw exc;
    fail();
  }
}

export function lexical_absolute(p: string): string {
  return path.resolve(p);
}

export function lexical_path_inside_root<E extends Error>(
  p: string,
  trusted_root: string,
  opts: { errorType: ErrorType<E>; traversal_message: string; outside_message: string }
): string {
  const raw = String(p);
  if (raw.split(/[\\/]+/).includes("..")) {
    throw new opts.errorType(opts.traversal_message);
  }
  const root = lexical_absolute(trusted_root);
  const target = lexical_absolute(path.isAbsolute(raw) ? raw : path.join(root, raw));
  const rel = path.relative(root, target);
  if (rel === "" ) {
    return target;
  }
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new opts.errorType(opts.outside_message);
  }
  return target;
}

function _splitAbsolute(absolute: string): string[] {
  const parsed = path.parse(absolute);
  const rest = absolute.slice(parsed.root.length);
  return rest.split(/[\\/]+/).filter((c) => c.length > 0);
}

function _lstatComponent(dir: string, component: string): fs.Stats {
  return fs.lstatSync(path.join(dir, component));
}

export function open_directory_nofollow<E extends Error>(
  p: string,
  opts: {
    errorType: ErrorType<E>;
    invalid_message: string;
    unavailable_message: string;
    preserve_missing?: boolean;
    create_missing?: boolean;
    create_mode?: number;
  }
): string {
  const absolute = lexical_absolute(p);
  if (!path.isAbsolute(absolute) || _splitAbsolute(absolute).length < 1) {
    throw new opts.errorType(opts.invalid_message);
  }
  const parsed = path.parse(absolute);
  let current = parsed.root;
  try {
    fs.lstatSync(current);
  } catch {
    throw new opts.errorType(opts.unavailable_message);
  }
  for (const component of _splitAbsolute(absolute)) {
    const full = path.join(current, component);
    let st: fs.Stats;
    try {
      st = _lstatComponent(current, component);
    } catch (exc: any) {
      if (exc && exc.code === "ENOENT") {
        if (!opts.create_missing) {
          if (opts.preserve_missing) throw exc;
          throw new opts.errorType(opts.unavailable_message);
        }
        try {
          fs.mkdirSync(full, { mode: opts.create_mode ?? 0o755 });
        } catch (mk: any) {
          if (!mk || mk.code !== "EEXIST") throw new opts.errorType(opts.unavailable_message);
        }
        st = _lstatComponent(current, component);
      } else {
        throw new opts.errorType(opts.unavailable_message);
      }
    }
    if (st.isSymbolicLink() || !st.isDirectory()) {
      throw new opts.errorType(opts.unavailable_message);
    }
    current = full;
  }
  return current;
}

function _inodeKey(info: fs.Stats | FileIdentity): [number, number] {
  if (Array.isArray(info)) {
    return [Number(info[0]), Number(info[1])];
  }
  return [Number((info as fs.Stats).dev), Number((info as fs.Stats).ino)];
}

function _validateLeaf<E extends Error>(name: string, errorType: ErrorType<E>, message: string): string {
  const leaf = String(name || "");
  if (!leaf || leaf === "." || leaf === ".." || path.basename(leaf) !== leaf || leaf.includes("/") || leaf.includes("\\")) {
    throw new errorType(message);
  }
  return leaf;
}

export function read_regular_at_nofollow<E extends Error>(
  directoryPath: string,
  name: string,
  opts: {
    errorType: ErrorType<E>;
    open_message: string;
    bounds_message: string;
    changed_message: string;
    max_bytes?: number | null;
    min_bytes?: number;
    chunk_bytes?: number;
    preserve_missing?: boolean;
    return_identity?: boolean;
    require_current_uid?: boolean;
  }
): Buffer | [Buffer, FileIdentity] {
  const leaf = _validateLeaf(name, opts.errorType, opts.open_message);
  const full = path.join(directoryPath, leaf);
  let lst: fs.Stats;
  try {
    lst = fs.lstatSync(full);
  } catch (exc: any) {
    if (exc && exc.code === "ENOENT") {
      if (opts.preserve_missing) throw exc;
      throw new opts.errorType(opts.open_message);
    }
    throw new opts.errorType(opts.open_message);
  }
  if (lst.isSymbolicLink()) {
    throw new opts.errorType(opts.open_message);
  }
  let fd: number;
  try {
    fd = fs.openSync(full, "r");
  } catch (exc: any) {
    if (exc && exc.code === "ENOENT") {
      if (opts.preserve_missing) throw exc;
      throw new opts.errorType(opts.open_message);
    }
    throw new opts.errorType(opts.open_message);
  }
  try {
    const before = fs.fstatSync(fd);
    const maxBytes = opts.max_bytes ?? null;
    const minBytes = opts.min_bytes ?? 0;
    if (
      !before.isFile() ||
      Number(before.nlink) !== 1 ||
      (opts.require_current_uid && process.platform !== "win32" && typeof process.getuid === "function" && Number((before as any).uid) !== process.getuid()) ||
      Number(before.size) < minBytes ||
      (maxBytes !== null && Number(before.size) > maxBytes)
    ) {
      throw new opts.errorType(opts.bounds_message);
    }
    const limit = maxBytes !== null ? maxBytes + 1 : Number(before.size) + 1;
    const chunkBytes = opts.chunk_bytes ?? 1024 * 1024;
    const chunks: Buffer[] = [];
    let remaining = limit;
    while (remaining > 0) {
      const buf = Buffer.alloc(Math.min(chunkBytes, remaining));
      const n = fs.readSync(fd, buf, 0, buf.length, null);
      if (n <= 0) break;
      chunks.push(buf.subarray(0, n));
      remaining -= n;
    }
    const payload = Buffer.concat(chunks);
    const after = fs.fstatSync(fd);
    const stable = JSON.stringify(_identity(before)) === JSON.stringify(_identity(after));
    if (!stable || payload.length !== Number(before.size) || (maxBytes !== null && payload.length > maxBytes)) {
      throw new opts.errorType(opts.changed_message);
    }
    return opts.return_identity ? [payload, _identity(after)] : payload;
  } finally {
    fs.closeSync(fd);
  }
}

export function atomic_write_bytes_at_nofollow<E extends Error>(
  directoryPath: string,
  name: string,
  payload: Buffer,
  opts: { errorType: ErrorType<E>; unavailable_message: string; mode?: number }
): string {
  const errorType = opts.errorType;
  const unavailable = opts.unavailable_message;
  const mode = opts.mode ?? 0o600;
  const leaf = String(name || "");
  if (!leaf || leaf === "." || leaf === ".." || path.basename(leaf) !== leaf) {
    throw new errorType(unavailable);
  }
  let oldInfo: fs.Stats | null;
  try {
    oldInfo = fs.lstatSync(path.join(directoryPath, leaf));
  } catch {
    oldInfo = null;
  }
  if (
    oldInfo !== null &&
    (!oldInfo.isFile() ||
      Number(oldInfo.nlink) !== 1 ||
      oldInfo.isSymbolicLink() ||
      (process.platform !== "win32" && typeof process.getuid === "function" && Number((oldInfo as any).uid) !== process.getuid()))
  ) {
    throw new errorType(unavailable);
  }
  const token = `${process.pid}.${crypto.randomBytes(12).toString("hex")}`;
  let tmpName = `.${leaf}.${token}.tmp`;
  let backupName = oldInfo !== null ? `.${leaf}.${token}.rollback` : "";
  let newInfo: fs.Stats | null = null;
  let replaced = false;
  const tmpPath = () => path.join(directoryPath, tmpName);
  const backupPath = () => path.join(directoryPath, backupName);
  const targetPath = () => path.join(directoryPath, leaf);
  try {
    try {
      if (oldInfo !== null) {
        fs.linkSync(targetPath(), backupPath());
        const current = fs.lstatSync(targetPath());
        const backup = fs.lstatSync(backupPath());
        const ik = (a: [number, number], b: [number, number]) => a[0] === b[0] && a[1] === b[1];
        if (
          !ik(_inodeKey(current), _inodeKey(oldInfo)) ||
          !ik(_inodeKey(backup), _inodeKey(oldInfo)) ||
          Number(current.nlink) !== 2 ||
          Number(backup.nlink) !== 2
        ) {
          throw new Error("atomic rollback inode binding failed");
        }
      }
      const fd = fs.openSync(tmpPath(), "wx", mode);
      try {
        try {
          fs.chmodSync(tmpPath(), mode);
        } catch {}
        let view: Buffer = payload;
        while (view.length) {
          const written = fs.writeSync(fd, view, 0, view.length, null);
          if (written <= 0) {
            throw new Error("short atomic write");
          }
          view = view.subarray(written);
        }
        fs.fsyncSync(fd);
        newInfo = fs.fstatSync(fd);
        if (!newInfo.isFile() || Number(newInfo.nlink) !== 1) {
          throw new Error("atomic staging inode identity is invalid");
        }
      } finally {
        fs.closeSync(fd);
      }
      try {
        fs.renameSync(tmpPath(), targetPath());
        tmpName = "";
        replaced = true;
        const observed = read_regular_at_nofollow(directoryPath, leaf, {
          errorType,
          open_message: unavailable,
          bounds_message: unavailable,
          changed_message: unavailable,
          max_bytes: payload.length,
          min_bytes: payload.length,
          return_identity: true,
        }) as [Buffer, FileIdentity];
        const [observedPayload, observedIdentity] = observed;
        const ik2 = (a: [number, number], b: [number, number]) => a[0] === b[0] && a[1] === b[1];
        if (!observedPayload.equals(payload) || newInfo === null || !ik2(_inodeKey(observedIdentity as any), _inodeKey(newInfo))) {
          throw new Error("atomic publish read-back mismatch");
        }
      } catch (publishExc) {
        try {
          if (backupName) {
            fs.renameSync(backupPath(), targetPath());
            backupName = "";
            const restored = fs.lstatSync(targetPath());
            const ik = (a: [number, number], b: [number, number]) => a[0] === b[0] && a[1] === b[1];
            if (oldInfo === null || !ik(_inodeKey(restored), _inodeKey(oldInfo)) || !restored.isFile() || Number(restored.nlink) !== 1) {
              throw new Error("atomic rollback verification failed");
            }
          } else if (replaced) {
            const current = fs.lstatSync(targetPath());
            const ik = (a: [number, number], b: [number, number]) => a[0] === b[0] && a[1] === b[1];
            if (newInfo === null || !ik(_inodeKey(current), _inodeKey(newInfo))) {
              throw new Error("atomic rollback target identity changed");
            }
            fs.unlinkSync(targetPath());
            try {
              fs.lstatSync(targetPath());
              throw new Error("atomic rollback removal failed");
            } catch (e: any) {
              if (!e || e.code !== "ENOENT") throw e;
            }
          }
        } catch (rollbackExc) {
          throw new errorType(`${unavailable}; verified rollback failed`);
        }
        throw publishExc;
      }
      if (backupName) {
        try {
          fs.unlinkSync(backupPath());
          backupName = "";
        } catch (cleanupExc) {
          fs.renameSync(backupPath(), targetPath());
          backupName = "";
          throw new errorType(unavailable);
        }
      }
    } catch (exc) {
      if (exc instanceof errorType) throw exc;
      if (!(exc instanceof Error)) throw exc;
      throw new errorType(unavailable);
    }
  } finally {
    for (const residue of [tmpName, backupName]) {
      if (!residue) continue;
      try {
        fs.unlinkSync(path.join(directoryPath, residue));
      } catch {}
    }
  }
  return sha256_bytes(payload);
}

export function atomic_write_bytes_nofollow<E extends Error>(
  p: string,
  payload: Buffer,
  opts: {
    errorType: ErrorType<E>;
    invalid_message: string;
    unavailable_message: string;
    create_parents?: boolean;
    mode?: number;
  }
): string {
  const absolute = lexical_absolute(p);
  const base = path.basename(absolute);
  if (!path.isAbsolute(absolute) || base === "" || base === "." || base === "..") {
    throw new opts.errorType(opts.invalid_message);
  }
  const parentPath = open_directory_nofollow(path.dirname(absolute), {
    errorType: opts.errorType,
    invalid_message: opts.invalid_message,
    unavailable_message: opts.unavailable_message,
    create_missing: opts.create_parents ?? true,
  });
  return atomic_write_bytes_at_nofollow(parentPath, base, payload, {
    errorType: opts.errorType,
    unavailable_message: opts.unavailable_message,
    mode: opts.mode ?? 0o600,
  });
}

export function read_regular_nofollow<E extends Error>(
  p: string,
  opts: {
    errorType: ErrorType<E>;
    invalid_message: string;
    directory_message: string;
    open_message: string;
    bounds_message: string;
    changed_message: string;
    max_bytes?: number | null;
    min_bytes?: number;
    preserve_missing?: boolean;
    return_identity?: boolean;
    trusted_root?: string | null;
    require_current_uid?: boolean;
  }
): Buffer | [Buffer, FileIdentity] {
  const raw = String(p);
  if (raw.split(/[\\/]+/).includes("..")) {
    throw new opts.errorType(opts.invalid_message);
  }
  const absolute =
    opts.trusted_root == null
      ? lexical_absolute(raw)
      : lexical_path_inside_root(raw, opts.trusted_root, {
          errorType: opts.errorType,
          traversal_message: opts.invalid_message,
          outside_message: opts.invalid_message,
        });
  const base = path.basename(absolute);
  if (!path.isAbsolute(absolute) || base === "" || base === "." || base === "..") {
    throw new opts.errorType(opts.invalid_message);
  }
  const parentPath = open_directory_nofollow(path.dirname(absolute), {
    errorType: opts.errorType,
    invalid_message: opts.invalid_message,
    unavailable_message: opts.directory_message,
    preserve_missing: opts.preserve_missing ?? false,
  });
  return read_regular_at_nofollow(parentPath, base, {
    errorType: opts.errorType,
    open_message: opts.open_message,
    bounds_message: opts.bounds_message,
    changed_message: opts.changed_message,
    max_bytes: opts.max_bytes ?? null,
    min_bytes: opts.min_bytes ?? 0,
    preserve_missing: opts.preserve_missing ?? false,
    return_identity: opts.return_identity ?? false,
    require_current_uid: opts.require_current_uid ?? false,
  });
}

export function stat_regular_nofollow<E extends Error>(
  p: string,
  opts: {
    errorType: ErrorType<E>;
    invalid_message: string;
    directory_message: string;
    open_message: string;
    bounds_message: string;
    max_bytes?: number | null;
    min_bytes?: number;
  }
): FileIdentity {
  const absolute = lexical_absolute(p);
  const base = path.basename(absolute);
  if (!path.isAbsolute(absolute) || base === "" || base === "." || base === "..") {
    throw new opts.errorType(opts.invalid_message);
  }
  const parentPath = open_directory_nofollow(path.dirname(absolute), {
    errorType: opts.errorType,
    invalid_message: opts.invalid_message,
    unavailable_message: opts.directory_message,
  });
  const full = path.join(parentPath, base);
  let lst: fs.Stats;
  try {
    lst = fs.lstatSync(full);
  } catch (exc) {
    throw new opts.errorType(opts.open_message);
  }
  if (lst.isSymbolicLink()) {
    throw new opts.errorType(opts.open_message);
  }
  const maxBytes = opts.max_bytes ?? null;
  const minBytes = opts.min_bytes ?? 0;
  if (!lst.isFile() || Number(lst.nlink) !== 1 || Number(lst.size) < minBytes || (maxBytes !== null && Number(lst.size) > maxBytes)) {
    throw new opts.errorType(opts.bounds_message);
  }
  return _identity(lst);
}
