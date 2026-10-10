import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execSync } from "node:child_process";
import { ClientError } from "./errors.js";
import { Workspace, fromStatePath, safeComponent, safeRelativePath, stateLock, toStatePath } from "./workspace.js";
import { cachedManifest, locked, swapDirectory, verifiedFile } from "./bundle.js";

const ENGINE_DIR = path.resolve(__dirname, "../cex_core/engine");

export const DATA_ROOT_ENV = "CEX_ENGINE_DATA_ROOT";
export const LAYOUT = 4;
const _MARKER = ".complete.json";
const _INVENTORY = ".inventory.json";
const _ENGINE_PREFIX = "cex_core.engine.";
const _ROOT_MODULE = "cex_core.engine._root";
const _SPEC_ACTIVE_SCHEMA = "ist.spec.active";
const _COMMAND_TREE_ACTIVE_SCHEMA = "ist.command-tree.active";
const _GENERATION_MANIFEST = "cmdtree/generation_manifest.json";
const _ROUTED_PROJECTIONS: Record<string, string> = {
  ssl_lifecycle_contract_json: "scripts/maintenance/assets/ssl_lifecycle_contract.json",
  criterion_author_rules_jsonl: "runtime/criterion_author_rules.jsonl",
};
const _FOOTPRINT_TAR = /^footprints\/nodes_([0-9][0-9.]*)\.tar\.gz$/;
export const TOPOLOGY_REL = "knowledge/data/auto_env/network_topology.json";
export const TOPOLOGY_MD_REL = "knowledge/data/auto_env/network_topology_rag.md";
export const RULE_LEDGER_REL = "runtime/criterion_author_rules.jsonl";

function _sha256(filePath: string): string {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function _copy(src: string, dst: string): void {
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
}

function _extractTree(archive: string, target: string): number {
  let count = 0;
  const tar = execSync(`tar -tf "${archive}"`, { encoding: "utf8" });
  for (const name of tar.split("\n").filter(Boolean)) {
    let clean = name;
    while (clean.startsWith("./")) clean = clean.slice(2);
    clean = clean.replace(/\/+$/, "");
    if (!clean || clean === ".") continue;
    const dest = path.join(target, safeRelativePath(clean));
    if (name.endsWith("/")) {
      fs.mkdirSync(dest, { recursive: true });
    } else {
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      execSync(`tar -xf "${archive}" -C "${target}" "${clean}"`);
      count++;
    }
  }
  return count;
}

function _specGeneration(entries: Record<string, string>, root: string): Record<string, unknown> {
  const manifestPath = entries["spec/manifest.json"];
  if (!manifestPath) return { status: "absent" };
  const raw = fs.readFileSync(manifestPath);
  const manifest = JSON.parse(raw.toString("utf8"));
  const generationId = String(manifest.generation_id ?? "");
  safeComponent(generationId, "spec generation id");
  if (!entries["spec/state.tsv"] || !entries["spec/index.json"]) {
    return {
      status: "incomplete",
      generation_id: generationId,
      note: "the bundle has no spec sync ledger (state.tsv); republish it with the current importer to get governing-spec lookup",
    };
  }
  const store = path.join(root, "knowledge", "data", "spec");
  const generation = path.join(store, "generations", generationId);
  _copy(manifestPath, path.join(generation, "manifest.json"));
  _copy(entries["spec/index.json"], path.join(generation, "index.json"));
  _copy(entries["spec/state.tsv"], path.join(generation, "state.tsv"));
  fs.mkdirSync(path.join(generation, "docs"), { recursive: true });
  for (const [rel, p] of Object.entries(entries)) {
    if (rel.startsWith("spec/docs/")) {
      _copy(p, path.join(generation, "docs", rel.slice("spec/docs/".length)));
    }
  }
  const active = {
    schema: _SPEC_ACTIVE_SCHEMA,
    generation_id: generationId,
    manifest_sha256: crypto.createHash("sha256").update(raw).digest("hex"),
  };
  fs.writeFileSync(path.join(store, "active.json"), JSON.stringify(active), "utf8");
  return { status: "ready", generation_id: generationId };
}

function _commandTreeStore(entries: Record<string, string>, root: string): Record<string, unknown> {
  const manifestPath = entries[_GENERATION_MANIFEST];
  if (!manifestPath) return { status: "absent" };
  const raw = fs.readFileSync(manifestPath);
  const manifest = JSON.parse(raw.toString("utf8"));
  const ids: Record<string, string> = {};
  for (const key of ["generation_id", "product", "platform", "version", "device_build"]) {
    ids[key] = safeComponent(manifest[key], `command tree ${key}`);
  }
  const partition = path.join(
    root, "runtime", "command_tree", "products", ids.product, "platforms", ids.platform,
    "builds", `${ids.version}_${ids.device_build}`);
  const generation = path.join(partition, "generations", ids.generation_id);
  const artifacts = manifest.artifacts;
  if (typeof artifacts !== "object" || artifacts === null || !Object.keys(artifacts).length) {
    throw new ClientError("the command tree generation manifest declares no artifacts; republish the bundle");
  }
  const shipped: Record<string, string> = {};
  for (const [name, declared] of Object.entries(artifacts as Record<string, unknown>).sort()) {
    const safeName = safeComponent(name, "command tree artifact");
    const source = entries[`cmdtree/${safeName}`];
    const digest = typeof declared === "object" && declared !== null
      ? String((declared as Record<string, unknown>).sha256 ?? "")
      : "";
    if (!source || _sha256(source) !== digest) {
      throw new ClientError(
        `the synced bundle's command tree file ${safeName} does not match its generation manifest; call cex_sync, or republish the bundle`);
    }
    _copy(source, path.join(generation, safeName));
    shipped[safeName] = digest;
  }
  fs.writeFileSync(path.join(generation, "manifest.json"), raw);
  const active = {
    schema: _COMMAND_TREE_ACTIVE_SCHEMA,
    product: ids.product,
    platform: ids.platform,
    version: ids.version,
    device_build: ids.device_build,
    generation_id: ids.generation_id,
    manifest_sha256: crypto.createHash("sha256").update(raw).digest("hex"),
  };
  fs.writeFileSync(
    path.join(partition, "active.json"),
    JSON.stringify(active, Object.keys(active).sort()),
    "utf8");
  const projection = Object.entries(shipped).find(([name]) => name.startsWith("vendor_stdlib_"))?.[1] ?? "";
  return {
    status: "ready",
    generation_id: ids.generation_id,
    manifest_sha256: active.manifest_sha256,
    projection_sha256: projection,
  };
}

function _footprints(entries: Record<string, string>, root: string): string[] {
  const base = path.join(root, "knowledge", "footprints");
  const versions: string[] = [];
  for (const [rel, p] of Object.entries(entries).sort()) {
    const match = rel.match(_FOOTPRINT_TAR);
    if (!match) continue;
    const version = safeComponent(match[1], "footprint version");
    versions.push(version);
    _extractTree(p, path.join(base, `nodes_${version}`));
    const receipt = entries[`footprints/receipt_nodes_${version}.json`];
    if (receipt) {
      _copy(receipt, path.join(base, `.receipt_nodes_${version}.json`));
    }
  }
  if (versions.length === 1) {
    const version = versions[0];
    _extractTree(entries[`footprints/nodes_${version}.tar.gz`], path.join(base, "nodes"));
    const receipt = entries[`footprints/receipt_nodes_${version}.json`];
    if (receipt) {
      _copy(receipt, path.join(base, ".receipt_nodes.json"));
    }
  }
  return versions;
}

export function rootFor(ws: Workspace, manifest: Record<string, unknown>): string {
  const bundleId = String(manifest.bundle_id ?? "");
  return path.join(ws.stateDir, "engine", safeComponent(bundleId.slice(0, 16) || "bundle", "bundle id"));
}

function _reusable(target: string): Record<string, unknown> | null {
  let done: Record<string, unknown>;
  let raw: Buffer;
  try {
    done = JSON.parse(fs.readFileSync(path.join(target, _MARKER), "utf8"));
    raw = fs.readFileSync(path.join(target, _INVENTORY));
  } catch {
    return null;
  }
  if (typeof done !== "object" || done === null || done.layout !== LAYOUT ||
      crypto.createHash("sha256").update(raw).digest("hex") !== done.inventory_sha256) {
    return null;
  }
  let files: unknown;
  try {
    files = JSON.parse(raw.toString("utf8"));
  } catch {
    return null;
  }
  if (!Array.isArray(files) || files.length !== done.files) return null;
  for (const rel of files) {
    try {
      if (!fs.statSync(path.join(target, String(rel))).isFile()) return null;
    } catch {
      return null;
    }
  }
  return done;
}

export function materialize(ws: Workspace): [string, Record<string, unknown>] {
  const lock = locked(ws, undefined, true);
  try {
    const manifest = cachedManifest(ws);
    if (manifest === null) {
      throw new ClientError("no synced compile data; call cex_sync first");
    }
    const target = rootFor(ws, manifest);
    const done = _reusable(target);
    if (done !== null) return [target, done];
    const engineLock = stateLock(ws, "engine", path.basename(target));
    try {
      const done2 = _reusable(target);
      if (done2 !== null) return [target, done2];
      return _build(ws, manifest, target);
    } finally {
      engineLock.release();
    }
  } finally {
    lock.release();
  }
}

function _build(ws: Workspace, manifest: Record<string, unknown>, target: string): [string, Record<string, unknown>] {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const legacy = target + ".tmp";
  if (fs.existsSync(legacy) && !fs.lstatSync(legacy).isSymbolicLink()) {
    fs.rmSync(legacy, { recursive: true, force: true });
  }
  const staging = fs.mkdtempSync(path.join(path.dirname(target), `.${path.basename(target)}.staging.`));
  try {
    const info = _populate(ws, manifest, staging);
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (entry.isFile() && !entry.isSymbolicLink()) files.push(path.relative(staging, p).split(path.sep).join("/"));
      }
    };
    walk(staging);
    files.sort();
    const inventory = JSON.stringify(files);
    fs.writeFileSync(path.join(staging, _INVENTORY), inventory, "utf8");
    info.files = files.length;
    info.inventory_sha256 = crypto.createHash("sha256").update(inventory, "utf8").digest("hex");
    fs.writeFileSync(path.join(staging, _MARKER), JSON.stringify(info), "utf8");
    swapDirectory(staging, target);
    return [target, info];
  } catch (e) {
    try { fs.rmSync(staging, { recursive: true, force: true }); } catch {}
    throw e;
  }
}

export function pinnedRoot(ws: Workspace, recorded: unknown): [string, Record<string, unknown>] {
  const root = fromStatePath(ws, recorded);
  if (path.dirname(root) !== path.join(ws.stateDir, "engine") || !path.basename(root)) {
    throw new ClientError(
      `the batch state names ${JSON.stringify(recorded)}, which is not a compile data root of this workspace; prepare the batch again`);
  }
  const done = _reusable(root);
  if (done !== null) return [root, done];
  const manifest = cachedManifest(ws);
  if (manifest !== null && rootFor(ws, manifest) === root) {
    return materialize(ws);
  }
  const current = String(manifest?.bundle_id ?? "").slice(0, 16) || "none";
  throw new ClientError(
    `this batch was prepared on compile data ${path.basename(root)}, which is no longer complete in this workspace (the synced bundle is now ${current}). Prepare the batch again on the current data: cex_recompose_prepare (same mindmap and out_name; recorded cases stay recorded), cex_recompose_seal, then cex_author_prepare`);
}

function _populate(ws: Workspace, manifest: Record<string, unknown>, staging: string): Record<string, unknown> {
  const bundleId = String(manifest.bundle_id ?? "");
  const entries: Record<string, string> = {};
  for (const entry of (manifest.entries as Record<string, unknown>[]) ?? []) {
    entries[safeRelativePath(entry.path)] = verifiedFile(ws, entry);
  }
  const compileRef = path.join(staging, "knowledge", "data", "compile_ref");
  const manualRoot = path.join(staging, "knowledge", "data", "manual");
  const commandTree: Record<string, unknown> = { projections: [], xml: [] };
  const routed: string[] = [];
  for (const [rel, p] of Object.entries(entries)) {
    if (rel.startsWith("projections/")) {
      const tail = rel.slice("projections/".length);
      const routedKey = tail.replace(/[./]/g, "_");
      if (_ROUTED_PROJECTIONS[routedKey]) {
        _copy(p, path.join(staging, _ROUTED_PROJECTIONS[routedKey]));
        routed.push(tail);
      } else {
        _copy(p, path.join(compileRef, tail));
      }
    } else if (rel.startsWith("cmdtree/") && rel !== "cmdtree/source.json" && rel !== _GENERATION_MANIFEST) {
      const name = safeComponent(rel.slice("cmdtree/".length), "command tree file");
      _copy(p, path.join(compileRef, name));
      (commandTree.xml as string[]).push(name);
      if (name.endsWith(".xml")) (commandTree.xml as string[]).push(name);
      else (commandTree.projections as string[]).push(name);
    } else if (rel.startsWith("manual/")) {
      const tail = rel.slice("manual/".length);
      if (tail.endsWith("/sync_state.json")) {
        _copy(p, path.join(manualRoot, ".sync_state.json"));
      } else {
        _copy(p, path.join(manualRoot, tail));
      }
    }
  }
  commandTree.store = _commandTreeStore(entries, staging);
  let build = String(manifest.build ?? "");
  let source: Record<string, unknown> = {};
  if (entries["cmdtree/source.json"]) {
    source = JSON.parse(fs.readFileSync(entries["cmdtree/source.json"], "utf8"));
    build = String(source.full_version ?? build);
    if (typeof source.sanitization === "object" && source.sanitization !== null) {
      commandTree.sanitization = source.sanitization;
    }
  }
  if (build) {
    const capabilities = path.join(staging, "knowledge", "data", "auto_env", "env_capabilities.json");
    fs.mkdirSync(path.dirname(capabilities), { recursive: true });
    fs.writeFileSync(capabilities, JSON.stringify({ build }), "utf8");
  }
  const mirror = path.join(staging, "knowledge", "framework", "mirror");
  let frameworkFiles = 0;
  if (entries["framework/framework_tree.tar.gz"]) {
    frameworkFiles = _extractTree(entries["framework/framework_tree.tar.gz"], mirror);
    if (entries["framework/sync_meta.json"]) {
      _copy(entries["framework/sync_meta.json"], path.join(mirror, ".sync_meta.json"));
    }
  }
  return {
    layout: LAYOUT,
    bundle_id: bundleId,
    build: manifest.build,
    device_os_build: build || null,
    command_tree: commandTree,
    capability: {
      generation_id: String(source.generation_id ?? ""),
      projection_sha256: String(source.projection_sha256 ?? ""),
    },
    routed: routed.sort(),
    footprints: _footprints(entries, staging),
    spec: _specGeneration(entries, staging),
    framework_files: frameworkFiles,
  };
}

function _infotestSpelling(text: string): string {
  return text
    .replace(/\bcex_core\.engine\.scripts\b/g, "scripts")
    .replace(/\bcex_core\.engine\b(?!\._root\b)/g, "main");
}

export function codeMirror(root: string): number {
  const manifest = JSON.parse(fs.readFileSync(path.join(ENGINE_DIR, "MANIFEST.json"), "utf8"));
  let written = 0;
  for (const entry of (manifest.modules as Record<string, unknown>[]) ?? []) {
    const source = String(entry.source ?? "");
    if (!source.startsWith("main/case_compiler/") || source.endsWith("/__init__.py")) continue;
    const rel = String(entry.engine_module).split(".").slice(2);
    const text = _infotestSpelling(fs.readFileSync(path.join(ENGINE_DIR, ...rel) + ".py", "utf8"));
    const target = path.join(root, safeRelativePath(source));
    if (fs.existsSync(target) && fs.readFileSync(target, "utf8") === text) continue;
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const tmp = path.join(path.dirname(target), `.${path.basename(target)}.tmp`);
    fs.writeFileSync(tmp, text, "utf8");
    fs.renameSync(tmp, target);
    written++;
  }
  return written;
}

export function localRulesPath(ws: Workspace): string {
  return path.join(ws.stateDir, "criterion", "criterion_author_rules.jsonl");
}

export function mergeLocalRules(ws: Workspace, root: string): number {
  const local = localRulesPath(ws);
  if (!fs.existsSync(local)) return 0;
  const ledger = path.join(root, RULE_LEDGER_REL);
  const present = new Set<string>();
  if (fs.existsSync(ledger)) {
    for (const line of fs.readFileSync(ledger, "utf8").split("\n")) {
      try {
        present.add(String(JSON.parse(line).rule_sha256 ?? ""));
      } catch {}
    }
  }
  const missing: string[] = [];
  for (const line of fs.readFileSync(local, "utf8").split("\n")) {
    try {
      const record = JSON.parse(line);
      const sha = String(record.rule_sha256 ?? "");
      if (typeof record === "object" && record !== null && !present.has(sha)) {
        missing.push(JSON.stringify(record, Object.keys(record).sort()));
        present.add(sha);
      }
    } catch {}
  }
  if (missing.length) {
    fs.mkdirSync(path.dirname(ledger), { recursive: true });
    fs.appendFileSync(ledger, missing.map((l) => l + "\n").join(""), "utf8");
  }
  return missing.length;
}

export function topologyPath(ws: Workspace): string {
  return path.join(ws.stateDir, "bed", "network_topology.json");
}

export function placeTopology(ws: Workspace, root: string): Record<string, unknown> | null {
  const source = topologyPath(ws);
  const target = path.join(root, TOPOLOGY_REL);
  if (!fs.existsSync(source)) {
    if (fs.existsSync(target)) fs.unlinkSync(target);
    return null;
  }
  const raw = fs.readFileSync(source);
  if (!fs.existsSync(target) || !fs.readFileSync(target).equals(raw)) {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const tmp = path.join(path.dirname(target), `.${path.basename(target)}.tmp`);
    fs.writeFileSync(tmp, raw);
    fs.renameSync(tmp, target);
  }
  const rag = path.join(path.dirname(source), "network_topology_rag.md");
  if (fs.existsSync(rag)) {
    _copy(rag, path.join(root, TOPOLOGY_MD_REL));
  }
  return { path: target, sha256: crypto.createHash("sha256").update(raw).digest("hex") };
}

export function activate(root: string): string {
  const resolved = path.resolve(root);
  const current = process.env[DATA_ROOT_ENV] ?? "";
  for (const key of Object.keys(process.env)) {
    if (key.startsWith("IST_")) {
      delete process.env[key];
    }
  }
  process.env[DATA_ROOT_ENV] = resolved;
  return resolved;
}

export function prepare(ws: Workspace, pinned?: unknown): [string, Record<string, unknown>] {
  const [root, info] = pinned ? pinnedRoot(ws, pinned) : materialize(ws);
  const lock = stateLock(ws, "engine", path.basename(root));
  try {
    codeMirror(root);
    mergeLocalRules(ws, root);
    const topology = placeTopology(ws, root);
    return [activate(root), { ...info, topology, data_root: toStatePath(ws, root) }];
  } finally {
    lock.release();
  }
}
