import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { ClientError, ServerUnreachable } from "./errors.js";
import { Workspace, safeComponent, safeRelativePath, stateLock } from "./workspace.js";
import { request, requestJson } from "./auth.js";

export const MANIFEST = "manifest.json";
const _SHA_CHARS = new Set("0123456789abcdef");

export function _sha256File(filePath: string): string {
  const data = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(data).digest("hex");
}

function _target(root: string, rel: string): string {
  const target = path.resolve(root, safeRelativePath(rel));
  if (!target.startsWith(path.resolve(root) + path.sep)) {
    throw new ClientError(`bundle entry escapes the bundle directory: ${JSON.stringify(rel)}`);
  }
  return target;
}

export function _checkManifest(manifest: Record<string, unknown>, build: string): Record<string, unknown>[] {
  if (manifest.schema !== "cex.bundle/v1" || manifest.build !== build) {
    throw new ClientError("server returned a bundle for another build or an unknown schema");
  }
  const entries = manifest.entries;
  if (!Array.isArray(entries)) {
    throw new ClientError("bundle manifest has no entries");
  }
  for (const entry of entries as Record<string, unknown>[]) {
    const sha = String(entry.sha256 ?? "");
    if (sha.length !== 64 || [...sha].some((c) => !_SHA_CHARS.has(c))) {
      throw new ClientError(`bundle entry has an invalid sha256: ${JSON.stringify(entry.path)}`);
    }
    safeRelativePath(entry.path);
  }
  return entries as Record<string, unknown>[];
}

export function locked(ws: Workspace, build?: string, shared = false): { release(): void } {
  return stateLock(ws, "bundle", build ?? ws.deviceBuild, shared);
}

async function _download(ws: Workspace, sha: string, target: string): Promise<void> {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const [status, raw] = await request(ws, "GET", `/v1/blobs/${sha}`, { timeout: 600_000 });
  if (status !== 200) {
    throw new ClientError(`blob ${sha.slice(0, 12)} download failed (HTTP ${status})`);
  }
  const actual = crypto.createHash("sha256").update(raw).digest("hex");
  if (actual !== sha) {
    throw new ClientError(`SHA256 mismatch for ${path.basename(target)}: expected ${sha.slice(0, 12)}, got ${actual.slice(0, 12)}; refused to write`);
  }
  const tmp = path.join(path.dirname(target), `.${path.basename(target)}.${process.pid}.part`);
  fs.writeFileSync(tmp, raw);
  fs.renameSync(tmp, target);
}

function _summary(manifest: Record<string, unknown>): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const entry of (manifest.entries as Record<string, unknown>[]) ?? []) {
    const kind = String(entry.kind);
    counts[kind] = (counts[kind] ?? 0) + 1;
  }
  return counts;
}

export function cachedManifestAt(root: string): Record<string, unknown> | null {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(root, MANIFEST), "utf8"));
    return typeof data === "object" && data !== null ? data as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function cachedManifest(ws: Workspace, build?: string): Record<string, unknown> | null {
  return cachedManifestAt(ws.bundleDir(build));
}

export function verifyCache(ws: Workspace, build?: string): Record<string, unknown> {
  const manifest = cachedManifest(ws, build);
  if (manifest === null) {
    throw new ClientError("no cached bundle");
  }
  const root = ws.bundleDir(build);
  for (const entry of _checkManifest(manifest, String(manifest.build ?? ""))) {
    const p = _target(root, String(entry.path));
    if (!fs.existsSync(p) || _sha256File(p) !== entry.sha256) {
      throw new ClientError(`cached bundle is incomplete or modified: ${entry.path}`);
    }
  }
  return manifest;
}

function _unchanged(root: string, manifest: Record<string, unknown>, entries: Record<string, unknown>[]): boolean {
  const cached = cachedManifestAt(root);
  if (!cached || cached.bundle_id !== manifest.bundle_id) return false;
  const cachedSet = new Set((cached.entries as Record<string, unknown>[]).map((e) => `${e.path}\0${e.sha256}`));
  const newSet = new Set(entries.map((e) => `${e.path}\0${e.sha256}`));
  if (cachedSet.size !== newSet.size || [...cachedSet].some((x) => !newSet.has(x))) return false;
  for (const entry of entries) {
    const p = _target(root, String(entry.path));
    if (!fs.existsSync(p) || _sha256File(p) !== entry.sha256) return false;
  }
  return true;
}

export async function sync(ws: Workspace, channel?: string): Promise<Record<string, unknown>> {
  const build = ws.deviceBuild;
  const ch = channel ?? ws.channel;
  const root = ws.bundleDir(build);
  let manifest: Record<string, unknown>;
  try {
    manifest = await requestJson(ws, "GET", `/v1/builds/${safeComponent(build, "device_build")}/bundle?channel=${ch}`);
  } catch (e) {
    if (e instanceof ServerUnreachable) {
      const lock = locked(ws, build, true);
      try {
        const cached = verifyCache(ws, build);
        return {
          ok: true,
          source: "cache",
          build,
          bundle_id: cached.bundle_id,
          entries: _summary(cached),
          note: `server unreachable; using the cached bundle ${String(cached.bundle_id).slice(0, 12)} created ${cached.created_at}`,
        };
      } finally {
        lock.release();
      }
    }
    throw e;
  }
  const entries = _checkManifest(manifest, build);
  const lock = locked(ws, build);
  try {
    if (_unchanged(root, manifest, entries)) {
      return {
        ok: true,
        source: "server",
        build,
        channel: ch,
        bundle_id: manifest.bundle_id,
        downloaded: 0,
        unchanged: entries.length,
        removed: 0,
        entries: _summary(manifest),
      };
    }
    const previous = cachedManifestAt(root) ?? {};
    fs.mkdirSync(path.dirname(root), { recursive: true });
    const staging = fs.mkdtempSync(path.join(path.dirname(root), `.${path.basename(root)}.sync.`));
    let downloaded = 0;
    let unchanged = 0;
    try {
      for (const entry of entries) {
        const target = _target(staging, String(entry.path));
        const current = fs.existsSync(root) ? _target(root, String(entry.path)) : null;
        if (current !== null && fs.existsSync(current) && _sha256File(current) === entry.sha256) {
          fs.mkdirSync(path.dirname(target), { recursive: true });
          fs.copyFileSync(current, target);
          unchanged++;
        } else {
          await _download(ws, String(entry.sha256), target);
          downloaded++;
        }
        if (_sha256File(target) !== entry.sha256) {
          throw new ClientError(`staged bundle file ${entry.path} does not match its manifest; nothing was changed`);
        }
      }
      fs.writeFileSync(path.join(staging, MANIFEST), JSON.stringify(manifest, null, 1), "utf8");
      swapDirectory(staging, root);
    } catch (e) {
      try {
        fs.rmSync(staging, { recursive: true, force: true });
      } catch {}
      throw e;
    }
    const keep = new Set(entries.map((e) => String(e.path)));
    const removed = ((previous.entries as Record<string, unknown>[]) ?? []).filter(
      (e) => !keep.has(String(e.path)),
    ).length;
    return {
      ok: true,
      source: "server",
      build,
      channel: ch,
      bundle_id: manifest.bundle_id,
      downloaded,
      unchanged,
      removed,
      entries: _summary(manifest),
    };
  } finally {
    lock.release();
  }
}

export function swapDirectory(staging: string, root: string): void {
  let old: string | null = null;
  if (fs.existsSync(root)) {
    old = fs.mkdtempSync(path.join(path.dirname(root), `.${path.basename(root)}.old.`));
    fs.rmdirSync(old);
    fs.renameSync(root, old);
  }
  try {
    fs.renameSync(staging, root);
  } catch (e) {
    if (old !== null && !fs.existsSync(root)) {
      fs.renameSync(old, root);
    }
    throw e;
  }
  if (old !== null) {
    try {
      fs.rmSync(old, { recursive: true, force: true });
    } catch {}
  }
}

export function verifiedFile(ws: Workspace, entry: Record<string, unknown>, build?: string): string {
  const p = _target(ws.bundleDir(build), String(entry.path ?? ""));
  if (!fs.existsSync(p) || _sha256File(p) !== String(entry.sha256 ?? "")) {
    throw new ClientError(
      `the synced bundle file ${entry.path} is missing or does not match its manifest (an interrupted or tampered sync); call cex_sync`);
  }
  return p;
}

export function entryPath(ws: Workspace, kind: string, namePrefix = ""): string | null {
  const lock = locked(ws, undefined, true);
  try {
    const manifest = cachedManifest(ws);
    if (manifest === null) return null;
    for (const entry of (manifest.entries as Record<string, unknown>[]) ?? []) {
      const rel = String(entry.path ?? "");
      if (entry.kind === kind && rel.split("/").pop()!.startsWith(namePrefix)) {
        return verifiedFile(ws, entry);
      }
    }
    return null;
  } finally {
    lock.release();
  }
}

export const entry_path = entryPath;
