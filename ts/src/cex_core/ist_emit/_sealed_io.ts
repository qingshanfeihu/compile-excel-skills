import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { restrictFilePrivate } from "../../platform/index";

export type FileIdentity = [number, number, number, number, number];

export function _identity(info: fs.Stats): FileIdentity {
  return [
    Math.trunc(info.dev),
    Math.trunc(info.ino),
    Math.trunc(info.size),
    Math.trunc(info.mtimeMs * 1e6),
    Math.trunc(info.ctimeMs * 1e6),
  ];
}

function _sortKeys(value: unknown): unknown {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      out[key] = _sortKeys((value as Record<string, unknown>)[key]);
    }
    return out;
  }
  if (Array.isArray(value)) {
    return value.map(_sortKeys);
  }
  return value;
}

export function canonical_json(
  value: unknown,
  opts: { ensure_ascii: boolean; omit?: string | string[] | null } = { ensure_ascii: true },
): Buffer {
  let body: unknown = value;
  if (body !== null && typeof body === "object" && !Array.isArray(body) && !Buffer.isBuffer(body)) {
    body = { ...(body as Record<string, unknown>) };
    const omitted = typeof opts.omit === "string" ? [opts.omit] : (opts.omit ?? []);
    for (const field of omitted) {
      delete (body as Record<string, unknown>)[field];
    }
  }
  const json = JSON.stringify(_sortKeys(body));
  return Buffer.from(json, "utf-8");
}

export function sha256_bytes(value: Buffer): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

export const CONTRACT_CARD_MAX_BYTES = 4 * 1024 * 1024;

const _BUDGET_UNBOUNDED = 1 << 30;

export function scan_json_budget(
  payload: Buffer | string,
  opts: { abort_tokens?: number | null; abort_depth?: number | null } = {},
): [number, number] {
  const raw = typeof payload === "string" ? Buffer.from(payload, "utf-8") : payload;
  const stopTokens = opts.abort_tokens ?? _BUDGET_UNBOUNDED;
  const stopDepth = opts.abort_depth ?? _BUDGET_UNBOUNDED;
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
      } else if (byte === 0x5c) {
        escaped = true;
      } else if (byte === 0x22) {
        inString = false;
      }
      continue;
    }
    if (byte === 0x22) {
      inString = true;
      continue;
    }
    if (byte === 0x7b || byte === 0x5b) {
      depth += 1;
      tokens += 1;
      if (depth > maxDepth) maxDepth = depth;
    } else if (byte === 0x7d || byte === 0x5d) {
      depth = Math.max(0, depth - 1);
      continue;
    } else if (byte === 0x2c) {
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

export function validate_json_budget<T extends Error>(
  payload: Buffer | string,
  opts: {
    error_type: new (msg: string) => T;
    message: string;
    max_depth?: number;
    max_tokens?: number;
  },
): void {
  const maxDepth = opts.max_depth ?? 128;
  const maxTokens = opts.max_tokens ?? 500_000;
  const [tokens, depth] = scan_json_budget(payload, {
    abort_tokens: maxTokens,
    abort_depth: maxDepth,
  });
  if (depth > maxDepth || tokens > maxTokens) {
    throw new opts.error_type(opts.message);
  }
}

export function file_identity(info: fs.Stats): FileIdentity {
  return _identity(info);
}

export function validate_xlsx_zip_budget<T extends Error>(
  payload: Buffer,
  opts: {
    error_type: new (msg: string) => T;
    message: string;
    max_members?: number;
    max_member_bytes?: number;
    max_total_bytes?: number;
    max_compression_ratio?: number;
    max_central_directory_bytes?: number;
  },
): void {
  const maxMembers = opts.max_members ?? 4096;
  const maxMemberBytes = opts.max_member_bytes ?? 128 * 1024 * 1024;
  const maxTotalBytes = opts.max_total_bytes ?? 512 * 1024 * 1024;
  const maxCompressionRatio = opts.max_compression_ratio ?? 500;
  const maxCentralDirectoryBytes = opts.max_central_directory_bytes ?? 32 * 1024 * 1024;
  try {
    const tailStart = Math.max(0, payload.length - (65535 + 22));
    const eocdOffset = payload.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
    if (eocdOffset < tailStart || eocdOffset + 22 > payload.length) {
      throw new opts.error_type(opts.message);
    }
    const diskNumber = payload.readUInt16LE(eocdOffset + 4);
    const centralDisk = payload.readUInt16LE(eocdOffset + 6);
    const entriesOnDisk = payload.readUInt16LE(eocdOffset + 8);
    let totalEntries = payload.readUInt16LE(eocdOffset + 10);
    let centralSize = payload.readUInt32LE(eocdOffset + 12);
    const commentSize = payload.readUInt16LE(eocdOffset + 20);
    if (eocdOffset + 22 + commentSize !== payload.length) {
      throw new opts.error_type(opts.message);
    }
    if (diskNumber !== 0 || centralDisk !== 0 || entriesOnDisk !== totalEntries) {
      throw new opts.error_type(opts.message);
    }
    if (totalEntries === 0xffff || centralSize === 0xffffffff) {
      const locatorOffset = eocdOffset - 20;
      if (locatorOffset < 0 || !payload.subarray(locatorOffset, locatorOffset + 4).equals(Buffer.from([0x50, 0x4b, 0x06, 0x07]))) {
        throw new opts.error_type(opts.message);
      }
      const zip64Disk = payload.readUInt32LE(locatorOffset + 4);
      const zip64Offset = Number(payload.readBigUInt64LE(locatorOffset + 8));
      const diskCount = payload.readUInt32LE(locatorOffset + 16);
      if (zip64Disk !== 0 || diskCount !== 1 || zip64Offset + 56 > payload.length) {
        throw new opts.error_type(opts.message);
      }
      if (!payload.subarray(zip64Offset, zip64Offset + 4).equals(Buffer.from([0x50, 0x4b, 0x06, 0x06]))) {
        throw new opts.error_type(opts.message);
      }
      const zip64RecordSize = Number(payload.readBigUInt64LE(zip64Offset + 4));
      const zip64DiskNumber = payload.readUInt16LE(zip64Offset + 16);
      const zip64CentralDisk = payload.readUInt16LE(zip64Offset + 18);
      const zip64EntriesOnDisk = Number(payload.readBigUInt64LE(zip64Offset + 24));
      totalEntries = Number(payload.readBigUInt64LE(zip64Offset + 32));
      centralSize = Number(payload.readBigUInt64LE(zip64Offset + 40));
      if (
        zip64RecordSize < 44 ||
        zip64DiskNumber !== 0 ||
        zip64CentralDisk !== 0 ||
        zip64EntriesOnDisk !== totalEntries
      ) {
        throw new opts.error_type(opts.message);
      }
    }
    if (totalEntries > maxMembers || centralSize > maxCentralDirectoryBytes) {
      throw new opts.error_type(opts.message);
    }
  } catch (exc) {
    if (exc instanceof RangeError || exc instanceof TypeError) {
      throw new opts.error_type(opts.message);
    }
    throw exc;
  }
  void maxMemberBytes;
  void maxTotalBytes;
  void maxCompressionRatio;
}

export function lexical_absolute(p: string): string {
  return path.resolve(p);
}

export function lexical_path_inside_root<T extends Error>(
  p: string,
  trustedRoot: string,
  opts: { error_type: new (msg: string) => T; traversal_message: string; outside_message: string },
): string {
  if (p.split(/[\\/]+/).includes("..")) {
    throw new opts.error_type(opts.traversal_message);
  }
  const root = lexical_absolute(trustedRoot);
  const target = path.isAbsolute(p) ? lexical_absolute(p) : lexical_absolute(path.join(root, p));
  const rel = path.relative(root, target);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new opts.error_type(opts.outside_message);
  }
  return target;
}

export function atomic_write_bytes_nofollow<T extends Error>(
  p: string,
  payload: Buffer,
  opts: {
    error_type: new (msg: string) => T;
    invalid_message: string;
    unavailable_message: string;
    create_parents?: boolean;
    mode?: number;
  },
): string {
  const createParents = opts.create_parents ?? true;
  const mode = opts.mode ?? 0o600;
  const absolute = lexical_absolute(p);
  if (!path.isAbsolute(absolute) || ["", ".", ".."].includes(path.basename(absolute))) {
    throw new opts.error_type(opts.invalid_message);
  }
  const dir = path.dirname(absolute);
  if (createParents) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const name = path.basename(absolute);

  let oldInfo: fs.Stats | null = null;
  try {
    oldInfo = fs.lstatSync(absolute);
  } catch {
    oldInfo = null;
  }
  if (oldInfo !== null && (!oldInfo.isFile() || oldInfo.nlink !== 1)) {
    throw new opts.error_type(opts.unavailable_message);
  }

  const token = `${process.pid}.${crypto.randomBytes(12).toString("hex")}`;
  let tmpName = `.${name}.${token}.tmp`;
  let backupName = oldInfo !== null ? `.${name}.${token}.rollback` : "";
  const tmpPath = path.join(dir, tmpName);
  const backupPath = backupName ? path.join(dir, backupName) : "";
  let replaced = false;
  let newInfo: fs.Stats | null = null;
  try {
    if (oldInfo !== null) {
      fs.linkSync(absolute, backupPath);
    }
    const fd = fs.openSync(tmpPath, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL, mode);
    try {
      restrictFilePrivate(tmpPath);
      let offset = 0;
      while (offset < payload.length) {
        const written = fs.writeSync(fd, payload, offset, payload.length - offset);
        if (written <= 0) throw new Error("short atomic write");
        offset += written;
      }
      fs.fsyncSync(fd);
      newInfo = fs.fstatSync(fd);
      if (!newInfo.isFile() || newInfo.nlink !== 1) {
        throw new Error("atomic staging inode identity is invalid");
      }
    } finally {
      fs.closeSync(fd);
    }
    try {
      fs.renameSync(tmpPath, absolute);
      tmpName = "";
      replaced = true;
      const dirFd = fs.openSync(dir, "r");
      try {
        fs.fsyncSync(dirFd);
      } catch {
      } finally {
        fs.closeSync(dirFd);
      }
      const observed = fs.readFileSync(absolute);
      if (!observed.equals(payload) || newInfo === null) {
        throw new Error("atomic publish read-back mismatch");
      }
    } catch (publishExc) {
      try {
        if (backupName) {
          fs.renameSync(backupPath, absolute);
          backupName = "";
          const restored = fs.lstatSync(absolute);
          if (!restored.isFile()) {
            throw new Error("atomic rollback verification failed");
          }
        } else if (replaced) {
          fs.unlinkSync(absolute);
        }
      } catch (rollbackExc) {
        throw new opts.error_type(`${opts.unavailable_message}; verified rollback failed`);
      }
      throw publishExc;
    }
    if (backupName) {
      try {
        fs.unlinkSync(backupPath);
        backupName = "";
      } catch (cleanupExc) {
        fs.renameSync(backupPath, absolute);
        backupName = "";
        throw new opts.error_type(opts.unavailable_message);
      }
    }
  } catch (exc) {
    for (const residue of [tmpName, backupName]) {
      if (!residue) continue;
      try {
        fs.unlinkSync(path.join(dir, residue));
      } catch {}
    }
    if (exc instanceof opts.error_type) throw exc;
    throw new opts.error_type(opts.unavailable_message);
  }
  return sha256_bytes(payload);
}

export function read_regular_nofollow<T extends Error>(
  p: string,
  opts: {
    error_type: new (msg: string) => T;
    invalid_message: string;
    directory_message: string;
    open_message: string;
    bounds_message: string;
    changed_message: string;
    max_bytes?: number | null;
    min_bytes?: number;
    trusted_root?: string | null;
  },
): Buffer {
  if (p.split(/[\\/]+/).includes("..")) {
    throw new opts.error_type(opts.invalid_message);
  }
  const absolute =
    opts.trusted_root == null
      ? lexical_absolute(p)
      : lexical_path_inside_root(p, opts.trusted_root, {
          error_type: opts.error_type,
          traversal_message: opts.invalid_message,
          outside_message: opts.invalid_message,
        });
  if (!path.isAbsolute(absolute) || ["", ".", ".."].includes(path.basename(absolute))) {
    throw new opts.error_type(opts.invalid_message);
  }
  let fd: number;
  try {
    fd = fs.openSync(absolute, "r");
  } catch {
    throw new opts.error_type(opts.open_message);
  }
  try {
    const before = fs.fstatSync(fd);
    const minBytes = opts.min_bytes ?? 0;
    if (
      !before.isFile() ||
      before.size < minBytes ||
      (opts.max_bytes != null && before.size > opts.max_bytes)
    ) {
      throw new opts.error_type(opts.bounds_message);
    }
    const payload = fs.readFileSync(fd);
    const after = fs.fstatSync(fd);
    const stable = JSON.stringify(_identity(before)) === JSON.stringify(_identity(after));
    if (!stable || payload.length !== before.size || (opts.max_bytes != null && payload.length > opts.max_bytes)) {
      throw new opts.error_type(opts.changed_message);
    }
    return payload;
  } finally {
    fs.closeSync(fd);
  }
}

export function stat_regular_nofollow<T extends Error>(
  p: string,
  opts: {
    error_type: new (msg: string) => T;
    invalid_message: string;
    directory_message: string;
    open_message: string;
    bounds_message: string;
    max_bytes?: number | null;
    min_bytes?: number;
  },
): FileIdentity {
  const absolute = lexical_absolute(p);
  if (!path.isAbsolute(absolute) || ["", ".", ".."].includes(path.basename(absolute))) {
    throw new opts.error_type(opts.invalid_message);
  }
  let fd: number;
  try {
    fd = fs.openSync(absolute, "r");
  } catch {
    throw new opts.error_type(opts.open_message);
  }
  try {
    const info = fs.fstatSync(fd);
    const minBytes = opts.min_bytes ?? 0;
    if (
      !info.isFile() ||
      info.nlink !== 1 ||
      info.size < minBytes ||
      (opts.max_bytes != null && info.size > opts.max_bytes)
    ) {
      throw new opts.error_type(opts.bounds_message);
    }
    return _identity(info);
  } finally {
    fs.closeSync(fd);
  }
}
