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
// flock releases when the holder dies; an O_EXCL lockfile does not, so a
// crash between acquire and release would wedge every later caller forever.
// The lockfile carries the holder's pid and start time: a lock whose pid is
// gone (or improbably old) is taken over.
const LOCK_STALE_MS = 10 * 60 * 1000;

function processAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e: any) {
    return e && e.code === "EPERM";
  }
}

function lockIsStale(lockPath: string): boolean {
  let pid = 0;
  let startMs = 0;
  try {
    const info = JSON.parse(fs.readFileSync(lockPath, "utf8")) as { pid?: number; started_ms?: number };
    pid = Number(info.pid) || 0;
    startMs = Number(info.started_ms) || 0;
  } catch {
    // unreadable payload: a fresh file is a holder between create and write
    try {
      return Date.now() - fs.statSync(lockPath).mtimeMs > 5000;
    } catch {
      return true;
    }
  }
  if (pid > 0 && pid !== process.pid && processAlive(pid)) {
    if (startMs > 0 && Date.now() - startMs > LOCK_STALE_MS) {
      // held for implausibly long: treat as stale even with a live pid
      // (pid reuse after a crash can otherwise keep a dead lock alive)
      return true;
    }
    return false;
  }
  return pid !== process.pid;
}

function writeLockPayload(fd: number): void {
  fs.writeSync(fd, JSON.stringify({ pid: process.pid, started_ms: Date.now() }));
}

function sleepSync(ms: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function tryTakeLock(lockPath: string): number | null {
  try {
    const fd = fs.openSync(lockPath, "wx");
    writeLockPayload(fd);
    return fd;
  } catch (e: any) {
    if (e && (e.code === "EEXIST" || e.code === "EACCES" || e.code === "EPERM")) {
      if (lockIsStale(lockPath)) {
        try {
          fs.unlinkSync(lockPath);
        } catch {}
      }
      return null;
    }
    throw e;
  }
}

function releaseLockFd(fd: number, lockPath: string): void {
  try {
    fs.closeSync(fd);
  } catch {}
  try {
    fs.unlinkSync(lockPath);
  } catch {}
}

export async function acquireLock(lockPath: string, timeoutMs = 30000): Promise<FileLock> {
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const fd = tryTakeLock(lockPath);
    if (fd !== null) {
      return { release: () => releaseLockFd(fd, lockPath) };
    }
    if (Date.now() > deadline) {
      throw new Error(`timed out acquiring lock ${lockPath}`);
    }
    await new Promise((r) => setTimeout(r, LOCK_POLL_MS));
  }
}

export function acquireLockSync(lockPath: string, timeoutMs = 30000): FileLock {
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const fd = tryTakeLock(lockPath);
    if (fd !== null) {
      return { release: () => releaseLockFd(fd, lockPath) };
    }
    if (Date.now() > deadline) {
      throw new Error(`timed out acquiring lock ${lockPath}`);
    }
    sleepSync(LOCK_POLL_MS);
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
