import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import { acquireLock, acquireLockSync } from "../platform/index";

function tmpLockPath(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cex-lock-"));
  return path.join(dir, "test.lock");
}

test("lock excludes concurrent holders and releases", async () => {
  const lockPath = tmpLockPath();
  const first = await acquireLock(lockPath, 500);
  await assert.rejects(() => acquireLock(lockPath, 200), /timed out/);
  first.release();
  const second = await acquireLock(lockPath, 500);
  second.release();
});

test("sync lock excludes concurrent holders and releases", () => {
  const lockPath = tmpLockPath();
  const first = acquireLockSync(lockPath, 500);
  assert.throws(() => acquireLockSync(lockPath, 200), /timed out/);
  first.release();
  const second = acquireLockSync(lockPath, 500);
  second.release();
});

test("a stale lock (dead pid) is taken over instead of wedging", async () => {
  const lockPath = tmpLockPath();
  // a pid that is definitely not running: spawn-reaped or a huge unlikely pid
  const deadPid = 999999;
  fs.writeFileSync(lockPath, JSON.stringify({ pid: deadPid, started_ms: Date.now() }), "utf8");
  const lock = await acquireLock(lockPath, 500);
  lock.release();
});

test("a live foreign pid is respected until the stale age passes", async () => {
  const lockPath = tmpLockPath();
  fs.writeFileSync(lockPath, JSON.stringify({ pid: process.pid === 1 ? 2 : 1, started_ms: Date.now() }), "utf8");
  // pid 1 exists (init/launchd) but is not us: the lock must be respected while fresh
  await assert.rejects(() => acquireLock(lockPath, 200), /timed out/);
  // ...and taken over once older than the staleness window
  const stale = Date.now() - 11 * 60 * 1000;
  fs.writeFileSync(lockPath, JSON.stringify({ pid: process.pid === 1 ? 2 : 1, started_ms: stale }), "utf8");
  const lock = await acquireLock(lockPath, 500);
  lock.release();
});

test("same-pid relock does not steal its own held lock", async () => {
  const lockPath = tmpLockPath();
  const first = await acquireLock(lockPath, 500);
  await assert.rejects(() => acquireLock(lockPath, 200), /timed out/);
  first.release();
});
