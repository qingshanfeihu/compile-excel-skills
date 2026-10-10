import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const _CAP = 32768;
const _READ_CHUNK = 1024 * 1024;
const _CTIME_IS_CHANGE_TIME = process.platform !== "win32";

type StatSignature = [number, number, number, number, number, number];
const _CACHE = new Map<string, string>();

function _statSignature(info: fs.Stats): StatSignature {
  return [
    Number(info.dev),
    Number(info.ino),
    Number(info.size),
    Number(info.mtimeMs),
    Number(info.ctimeMs),
    Number(info.mode),
  ];
}

function _sigKey(resolved: string, sig: StatSignature): string {
  return resolved + "\0" + sig.join("\0");
}

export type FileIdentity = [string, number, number, string];

function _statIdentity(resolved: string): FileIdentity {
  const before = fs.statSync(resolved);
  if (!before.isFile()) {
    throw new Error("unsafe_file_identity");
  }
  const signature = _statSignature(before);
  const key = _sigKey(resolved, signature);
  const cacheable = _CTIME_IS_CHANGE_TIME && Number(before.ino) !== 0;
  if (cacheable) {
    const hit = _CACHE.get(key);
    if (hit !== undefined) {
      _CACHE.delete(key);
      _CACHE.set(key, hit);
      return [resolved, Number(before.size), Number(before.mtimeMs), hit];
    }
  }
  const digest = crypto.createHash("sha256");
  const fd = fs.openSync(resolved, "r");
  try {
    const buf = Buffer.alloc(_READ_CHUNK);
    let n: number;
    while ((n = fs.readSync(fd, buf, 0, _READ_CHUNK, null)) > 0) {
      digest.update(buf.subarray(0, n));
    }
  } finally {
    fs.closeSync(fd);
  }
  const after = fs.statSync(resolved);
  if (JSON.stringify(_statSignature(after)) !== JSON.stringify(signature) || !after.isFile()) {
    throw new Error("file_changed_while_reading");
  }
  const value = digest.digest("hex");
  if (cacheable) {
    _CACHE.set(key, value);
    while (_CACHE.size > _CAP) {
      const first = _CACHE.keys().next().value;
      if (first === undefined) break;
      _CACHE.delete(first);
    }
  }
  return [resolved, Number(before.size), Number(before.mtimeMs), value];
}

export function file_identity(p: string): FileIdentity {
  return _statIdentity(path.resolve(p));
}

export function walk_identity(root: string): FileIdentity[] {
  try {
    const st = fs.lstatSync(root);
    if (!st.isDirectory() || st.isSymbolicLink()) {
      return [];
    }
  } catch {
    return [];
  }
  const resolvedRoot = path.resolve(root);
  const entries: FileIdentity[] = [];
  const walk = (dir: string): void => {
    for (const name of fs.readdirSync(dir).sort()) {
      const full = path.join(dir, name);
      const rel = path.relative(resolvedRoot, full).split(path.sep).join("/");
      const lst = fs.lstatSync(full);
      if (lst.isSymbolicLink()) {
        entries.push([rel, 0, 0, `symlink:${fs.readlinkSync(full)}`]);
        continue;
      }
      if (lst.isDirectory()) {
        walk(full);
        continue;
      }
      const [, size, mtime, digest] = _statIdentity(full);
      entries.push([rel, size, mtime, digest]);
    }
  };
  walk(resolvedRoot);
  entries.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return entries;
}

export function clear_file_identity_cache(): void {
  _CACHE.clear();
}
