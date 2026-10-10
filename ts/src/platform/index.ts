import fs from "node:fs";
import path from "node:path";
import os from "node:os";

export const IS_WINDOWS = process.platform === "win32";

export function dataHome(): string {
  if (IS_WINDOWS) {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(base, "compile-excel");
  }
  return path.join(os.homedir(), ".local", "share", "compile-excel");
}

export function cacheHome(): string {
  if (IS_WINDOWS) {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(base, "compile-excel", "cache");
  }
  return path.join(os.homedir(), ".cache", "compile-excel");
}

export function circleHome(): string {
  return path.join(os.homedir(), ".circle");
}

export function unsetSentinelPath(name: string): string {
  if (IS_WINDOWS) {
    return path.join("\\\\.\\cex-nonexistent-sentinel", name);
  }
  return path.join("/dev/null", name);
}

export function restrictFilePrivate(filePath: string): void {
  if (IS_WINDOWS) return;
  try {
    fs.chmodSync(filePath, 0o600);
  } catch {}
}

export function restrictDirPrivate(dirPath: string): void {
  if (IS_WINDOWS) return;
  try {
    fs.chmodSync(dirPath, 0o700);
  } catch {}
}

export function makeExecutable(filePath: string): void {
  if (IS_WINDOWS) return;
  try {
    fs.chmodSync(filePath, 0o755);
  } catch {}
}

export function checkNotGroupWorldReadable(filePath: string): void {
  if (IS_WINDOWS) return;
  const st = fs.statSync(filePath);
  if (st.mode & 0o077) {
    throw new Error(`refusing to read ${filePath}: group/world permissions set`);
  }
}

export function writeFileAtomic(filePath: string, data: string | Buffer, opts: { private?: boolean } = {}): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(dir, `.tmp-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const fd = fs.openSync(tmp, "w");
  try {
    const buf = typeof data === "string" ? Buffer.from(data, "utf8") : data;
    fs.writeSync(fd, buf);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  if (opts.private) restrictFilePrivate(tmp);
  fs.renameSync(tmp, filePath);
}

export function writePrivateJson(filePath: string, value: unknown): void {
  writeFileAtomic(filePath, JSON.stringify(value, null, 2), { private: true });
}

export function readPrivateJson(filePath: string): unknown {
  checkNotGroupWorldReadable(filePath);
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

export interface FileLock {
  release(): void;
}

const LOCK_POLL_MS = 50;

export async function acquireLock(lockPath: string, timeoutMs = 30000): Promise<FileLock> {
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  const deadline = Date.now() + timeoutMs;
  let fd: number | null = null;
  while (fd === null) {
    try {
      fd = fs.openSync(lockPath, "wx");
    } catch (e: any) {
      if (e && (e.code === "EEXIST" || e.code === "EACCES" || e.code === "EPERM")) {
        if (Date.now() > deadline) {
          throw new Error(`timed out acquiring lock ${lockPath}`);
        }
        await new Promise((r) => setTimeout(r, LOCK_POLL_MS));
        continue;
      }
      throw e;
    }
  }
  const fdHeld = fd;
  return {
    release() {
      try {
        fs.closeSync(fdHeld);
      } catch {}
      try {
        fs.unlinkSync(lockPath);
      } catch {}
    },
  };
}

export function acquireLockSync(lockPath: string, timeoutMs = 30000): FileLock {
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    try {
      const fd = fs.openSync(lockPath, "wx");
      return {
        release() {
          try {
            fs.closeSync(fd);
          } catch {}
          try {
            fs.unlinkSync(lockPath);
          } catch {}
        },
      };
    } catch (e: any) {
      if (e && (e.code === "EEXIST" || e.code === "EACCES" || e.code === "EPERM")) {
        if (Date.now() > deadline) {
          throw new Error(`timed out acquiring lock ${lockPath}`);
        }
        const waitUntil = Date.now() + LOCK_POLL_MS;
        while (Date.now() < waitUntil) {}
        continue;
      }
      throw e;
    }
  }
}

export async function withLock<T>(lockPath: string, fn: () => T | Promise<T>, timeoutMs = 30000): Promise<T> {
  const lock = await acquireLock(lockPath, timeoutMs);
  try {
    return await fn();
  } finally {
    lock.release();
  }
}

export function safeComponent(name: string): string {
  if (!/^[\w.-]+$/.test(name) || name === "." || name === "..") {
    throw new Error(`unsafe path component: ${name}`);
  }
  return name;
}

export function safeRelativePath(rel: string): string {
  const norm = path.normalize(rel);
  if (path.isAbsolute(norm) || norm.startsWith("..") || norm.includes(`..${path.sep}`)) {
    throw new Error(`unsafe relative path: ${rel}`);
  }
  return norm;
}
