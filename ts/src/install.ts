#!/usr/bin/env node
import { execFileSync, execSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { dataHome, circleHome, makeExecutable } from "./platform/index";

const SOURCE = path.resolve(__dirname, "..");
const HARNESSES = ["claude", "pi", "circle"] as const;
type Harness = (typeof HARNESSES)[number];
const MARKETPLACE = "compile-excel";
const PLUGIN = "compile-excel@compile-excel";
const PLUGIN_MANIFEST = path.join(".claude-plugin", "plugin.json");
const INSTALL_RECORD = ".cex_install.json";
const SHIM_MARKER = "# compile-excel install.py";
const MJS_MARKER = "// " + SHIM_MARKER;
const SKIP_DIRS = new Set([".git", "tests", "__pycache__", ".pytest_cache", ".ruff_cache",
  ".mypy_cache", "node_modules", ".venv", "venv", ".compile-excel", "compile_outputs",
  ".circle", ".agents"]);
const SKIP_FILES = new Set(["_identities.json", "token.json", "lease.json", "login_pending.json",
  "client_config.json", "tasks.json", ".DS_Store", ".cex_home", INSTALL_RECORD]);
const SKIP_SUFFIXES = [".pyc", ".pyo", ".tmp"];
const SKILLS = ["compile-excel", "mindmap-recompose"];
const DEP_MODULES = ["exceljs", "yaml", "zod", "cheerio"];
const REQUIRED = [
  path.join("dist", "cex_client", "tools.js"),
  path.join("dist", "bin", "cex_tool.js"),
  path.join("dist", "bin", "cex_mcp_proxy.js"),
  ...SKILLS.map((n) => path.join("skills", n, "SKILL.md")),
  path.join("adapters", "circle", "extension.mjs"),
  path.join(".claude-plugin", "plugin.json"),
  path.join(".claude-plugin", "marketplace.json"),
  "package.json",
];

class InstallError extends Error {}
class AlreadyInstalled extends InstallError {
  constructor(public path: string, public version: string) {
    super(`compile-excel ${version} is already installed at ${path}; ask the user, then re-run with --upgrade to replace it`);
  }
}

function posix(rel: string): string {
  return rel.split(path.sep).join("/");
}

function excluded(rel: string): boolean {
  const parts = rel.split("/");
  return parts.slice(0, -1).some((p) => SKIP_DIRS.has(p))
    || SKIP_FILES.has(parts[parts.length - 1])
    || SKIP_SUFFIXES.some((s) => parts[parts.length - 1].endsWith(s));
}

function walkFiles(root: string, base = root): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const full = path.join(root, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) out.push(...walkFiles(full, base));
    } else if (entry.isFile()) {
      out.push(posix(path.relative(base, full)));
    }
  }
  return out;
}

export function distributableFiles(root: string): string[] {
  let listed: string[] | null = null;
  if (fs.existsSync(path.join(root, ".git")) && which("git")) {
    try {
      const out = execSync(`git -C "${root}" ls-files -z --cached --others --exclude-standard`,
        { timeout: 120000, maxBuffer: 64 * 1024 * 1024 });
      listed = out.toString("utf8").split("\0").filter(Boolean);
    } catch {
      listed = null;
    }
  }
  if (listed === null) listed = walkFiles(root);
  const out = new Set<string>();
  for (const rel of listed) {
    const p = path.join(root, rel);
    try {
      const st = fs.lstatSync(p);
      if (!excluded(rel) && st.isFile() && !st.isSymbolicLink()) out.add(rel);
    } catch {}
  }
  // dist/ is build output and gitignored, but the installed copy must run:
  // git ls-files never lists it, so add it explicitly.
  const distDir = path.join(root, "dist");
  if (fs.existsSync(distDir)) {
    for (const rel of walkFiles(distDir, root)) out.add(rel);
  }
  return [...out].sort();
}

function contentDigest(root: string, files: string[]): string {
  const digest = crypto.createHash("sha256");
  for (const rel of files) {
    let data = fs.readFileSync(path.join(root, rel));
    if (rel === posix(PLUGIN_MANIFEST)) {
      const manifest = JSON.parse(data.toString("utf8"));
      delete manifest.version;
      data = Buffer.from(JSON.stringify(manifest), "utf8");
    }
    digest.update(Buffer.from(rel, "utf8"));
    digest.update(Buffer.from([0]));
    digest.update(crypto.createHash("sha256").update(data).digest());
  }
  return digest.digest("hex");
}

function pluginVersion(root: string, files: string[]): string {
  let base = "0.0.0";
  try {
    base = String(JSON.parse(fs.readFileSync(path.join(root, PLUGIN_MANIFEST), "utf8")).version || "0.0.0").split("+")[0];
  } catch {}
  return `${base}+${contentDigest(root, files).slice(0, 12)}`;
}

function which(name: string): string | null {
  const exts = process.platform === "win32" ? [".cmd", ".exe", ".bat", ""] : [""];
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    for (const ext of exts) {
      const p = path.join(dir, name + ext);
      if (fs.existsSync(p)) return p;
    }
  }
  return null;
}

function copyFile(src: string, dst: string): void {
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
}

function rmrf(p: string): void {
  fs.rmSync(p, { recursive: true, force: true });
}

export class Installer {
  constructor(public prefix: string, public dryRun: boolean) {}

  run(argv: string[], actions: string[], opts: { timeout?: number; check?: boolean; readonly?: boolean; cwd?: string } = {}): string | null {
    const { timeout = 300000, check = true, readonly = false, cwd } = opts;
    actions.push("$ " + (cwd ? `cd ${cwd} && ` : "") + argv.join(" "));
    if (this.dryRun && !readonly) return null;
    try {
      return execFileSync(argv[0], argv.slice(1), { timeout, cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    } catch (e: any) {
      if (check) {
        const detail = String(e.stderr || e.stdout || e.message || "").trim().slice(-600);
        throw new InstallError(`${argv[0]} ${argv.slice(1, 3).join(" ")} failed: ${detail}`);
      }
      return null;
    }
  }

  runStatus(argv: string[], actions: string[], readonly = false): { code: number; stdout: string } | null {
    actions.push("$ " + argv.join(" "));
    if (this.dryRun && !readonly) return null;
    try {
      const stdout = execFileSync(argv[0], argv.slice(1), { timeout: 300000, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
      return { code: 0, stdout };
    } catch (e: any) {
      return { code: typeof e.status === "number" ? e.status : 1, stdout: String(e.stdout || "") };
    }
  }

  version(root: string): string {
    try {
      return String(JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8")).version);
    } catch {
      return "unknown";
    }
  }

  placeDistribution(upgrade: boolean): any {
    const missing = REQUIRED.filter((rel) => !fs.existsSync(path.join(SOURCE, rel)));
    if (missing.length) {
      throw new InstallError(`source checkout is incomplete (run npm run build first), missing: ${missing.join(", ")}`);
    }
    const files = distributableFiles(SOURCE);
    const stamped = pluginVersion(SOURCE, files);
    const report: any = { path: this.prefix, version: this.version(SOURCE), plugin_version: stamped, files: files.length, actions: [] };
    if (path.resolve(this.prefix) === SOURCE) {
      report.actions.push("running from the installed copy; nothing to copy");
      report.plugin_version = this.installedPluginVersion() || stamped;
      return report;
    }
    if (fs.existsSync(this.prefix)) {
      if (!upgrade) throw new AlreadyInstalled(this.prefix, this.version(this.prefix));
      if (!fs.existsSync(path.join(this.prefix, INSTALL_RECORD))) {
        throw new InstallError(`${this.prefix} exists but was not written by this installer; choose another --prefix or move it away yourself`);
      }
    }
    const staged = this.prefix + ".new";
    const old = this.prefix + ".old";
    report.actions.push(`copy ${files.length} distributable files ${SOURCE} -> ${this.prefix}`);
    report.actions.push(`stamp ${posix(PLUGIN_MANIFEST)} version ${stamped}`);
    if (this.dryRun) return report;
    rmrf(staged);
    rmrf(old);
    fs.mkdirSync(path.dirname(this.prefix), { recursive: true });
    fs.mkdirSync(staged);
    for (const rel of files) copyFile(path.join(SOURCE, rel), path.join(staged, rel));
    const manifestPath = path.join(staged, PLUGIN_MANIFEST);
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    manifest.version = stamped;
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");
    fs.writeFileSync(path.join(staged, INSTALL_RECORD), JSON.stringify({
      version: report.version, plugin_version: stamped,
      installed_at: Math.floor(Date.now() / 1000), source: SOURCE,
    }, null, 1) + "\n", "utf8");
    makeExecutable(path.join(staged, "dist", "bin", "cex_tool.js"));
    makeExecutable(path.join(staged, "dist", "bin", "cex_mcp_proxy.js"));
    if (fs.existsSync(this.prefix)) fs.renameSync(this.prefix, old);
    // an upgrade must not drop the dependencies the previous install installed
    const installedDeps = path.join(old, "node_modules");
    if (fs.existsSync(installedDeps)) {
      fs.renameSync(installedDeps, path.join(staged, "node_modules"));
    }
    fs.renameSync(staged, this.prefix);
    rmrf(old);
    return report;
  }

  installedPluginVersion(): string {
    try {
      return String(JSON.parse(fs.readFileSync(path.join(this.prefix, PLUGIN_MANIFEST), "utf8")).version || "");
    } catch {
      return "";
    }
  }

  checkDeps(install: boolean): any {
    const report: any = { ok: true, node: process.execPath, actions: [] };
    const probeRoot = this.dryRun ? SOURCE : this.prefix;
    const missing = DEP_MODULES.filter((m) => {
      try {
        require.resolve(m, { paths: [probeRoot] });
        return false;
      } catch {
        return true;
      }
    });
    report.missing = missing;
    if (missing.length && install) {
      this.run(["npm", "install", "--omit=dev", "--no-audit", "--no-fund"], report.actions, { timeout: 900000, cwd: probeRoot });
      report.missing = [];
    } else if (missing.length) {
      report.next = `ask the user, then: npm install in ${probeRoot} (or re-run install with --install-deps)`;
    }
    return report;
  }

  claudePluginList(actions: string[]): any[] {
    const listed = this.runStatus(["claude", "plugin", "list", "--json"], actions, true);
    if (!listed || listed.code !== 0) return [];
    try {
      const plugins = JSON.parse(listed.stdout || "[]");
      return Array.isArray(plugins) ? plugins.filter((p) => p && typeof p === "object") : [];
    } catch {
      return [];
    }
  }

  claude(): any {
    const actions: string[] = [];
    if (!which("claude")) throw new InstallError("claude CLI not found on PATH");
    const listing = this.runStatus(["claude", "plugin", "marketplace", "list", "--json"], actions, true);
    let existing: any[] = [];
    if (listing && listing.code === 0) {
      try {
        existing = JSON.parse(listing.stdout || "[]");
      } catch {
        existing = [];
      }
    }
    const current = existing.find((m: any) => m && m.name === MARKETPLACE);
    if (!current) {
      this.run(["claude", "plugin", "marketplace", "add", this.prefix], actions);
    } else if (path.resolve(String(current.path || "")) !== path.resolve(this.prefix)) {
      throw new InstallError(`a marketplace named ${MARKETPLACE} already points to ${current.path}; remove it with \`claude plugin marketplace remove ${MARKETPLACE}\` if it is an old copy`);
    } else {
      this.run(["claude", "plugin", "marketplace", "update", MARKETPLACE], actions);
    }
    const installed = this.claudePluginList(actions).some((p: any) => p.id === PLUGIN);
    this.run(["claude", "plugin", installed ? "update" : "install", PLUGIN], actions);
    const wanted = this.dryRun ? pluginVersion(SOURCE, distributableFiles(SOURCE)) : this.installedPluginVersion();
    if (this.dryRun) return { ok: true, actions, plugin_version: wanted };
    return this.verifyClaudeCache(actions, wanted);
  }

  verifyClaudeCache(actions: string[], wanted: string): any {
    const entry = this.claudePluginList(actions).find((p: any) => p.id === PLUGIN);
    const report: any = { ok: false, actions, plugin_version: wanted };
    if (!entry) {
      report.error = `${PLUGIN} is not in \`claude plugin list\` after installing it`;
      return report;
    }
    const cache = String(entry.installPath || "");
    report.cache = cache;
    if (String(entry.version || "") !== wanted) {
      report.error = `Claude Code still lists ${PLUGIN} at version ${JSON.stringify(entry.version)}, not ${JSON.stringify(wanted)}; its cached copy was not replaced`;
      return report;
    }
    const differing = distributableFiles(this.prefix).filter((rel) => {
      const cached = path.join(cache, rel);
      const installed = path.join(this.prefix, rel);
      try {
        return !fs.existsSync(cached) || !fs.readFileSync(cached).equals(fs.readFileSync(installed));
      } catch {
        return true;
      }
    });
    if (differing.length) {
      report.error = `Claude Code's cached copy at ${cache} differs from the distribution in ${differing.length} file(s), e.g. ${differing.slice(0, 3)}`;
      return report;
    }
    report.ok = true;
    report.note = "Claude Code runs its cached copy of the plugin, now this version; sessions started before the upgrade keep the old one until they are restarted";
    return report;
  }

  pi(): any {
    const actions: string[] = [];
    const pi = process.env.CEX_PI || which("pi");
    if (!pi) throw new InstallError("pi CLI not found on PATH (set CEX_PI to its path)");
    this.run([pi, "install", this.prefix], actions);
    return { ok: true, actions };
  }

  circle(): any {
    const actions: string[] = [];
    const home = process.env.CIRCLE_HOME || circleHome();
    const skills = SKILLS.map((name) => path.join(home, "skills", name));
    const extDir = path.join(home, "extensions", "compile-excel");
    for (const target of [...skills, extDir]) {
      if (fs.existsSync(target) && !Installer.ours(target)) {
        throw new InstallError(`${target} exists and was not written by this installer; move it away first`);
      }
    }
    for (const skill of skills) actions.push(`copy skill -> ${skill}`);
    actions.push(`write extension entry -> ${path.join(extDir, "extension.mjs")}`);
    if (this.dryRun) return { ok: true, actions };
    for (const skill of skills) {
      rmrf(skill);
      const source = path.join(this.prefix, "skills", path.basename(skill));
      for (const rel of distributableFiles(source)) {
        copyFile(path.join(source, rel), path.join(skill, rel));
      }
      fs.writeFileSync(path.join(skill, ".cex_home"), this.prefix + "\n", "utf8");
    }
    fs.mkdirSync(extDir, { recursive: true });
    const implMjs = path.join(this.prefix, "adapters", "circle", "extension.mjs");
    fs.writeFileSync(path.join(extDir, "extension.mjs"),
      `${MJS_MARKER}: entry forwards to the installed distribution root.\n`
      + `const impl = ${JSON.stringify("file://" + implMjs.split(path.sep).join("/"))};\n`
      + "export async function register(api) {\n"
      + "  const module = await import(impl + '?load=' + Date.now());\n"
      + "  return module.register(api);\n"
      + "}\n", "utf8");
    return { ok: true, actions, note: "circle 1.0 and later load extension.mjs" };
  }

  static ours(p: string): boolean {
    if (fs.existsSync(path.join(p, ".cex_home"))) return true;
    const entry = path.join(p, "extension.py");
    if (fs.existsSync(entry) && fs.readFileSync(entry, "utf8").startsWith(SHIM_MARKER)) return true;
    const module_ = path.join(p, "extension.mjs");
    return fs.existsSync(module_) && fs.readFileSync(module_, "utf8").startsWith(MJS_MARKER);
  }

  verify(): any {
    if (this.dryRun) return { ok: true, skipped: "dry run" };
    const report: any = { ok: false };
    const toolsResult = this.runStatus([process.execPath, path.join(this.prefix, "dist", "bin", "cex_tool.js"), "list"], []);
    if (toolsResult && toolsResult.code === 0) {
      try {
        report.tools = JSON.parse(toolsResult.stdout).length;
        report.ok = true;
      } catch {
        report.error = toolsResult.stdout.slice(-400);
      }
    } else {
      report.error = "cex_tool list failed";
    }
    return report;
  }
}

function parseArgs(argv: string[]): { harnesses: Harness[]; prefix: string; upgrade: boolean; installDeps: boolean; dryRun: boolean } {
  const harnessArgs: string[] = [];
  let prefix = path.join(dataHome(), "current");
  let upgrade = false;
  let installDeps = false;
  let dryRun = false;
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--harness") {
      const value = argv[++i];
      if (!value || ![...HARNESSES, "all"].includes(value as any)) {
        throw new InstallError(`--harness must be one of ${[...HARNESSES, "all"].join("|")}`);
      }
      harnessArgs.push(value);
    } else if (arg === "--prefix") {
      prefix = argv[++i] || prefix;
    } else if (arg === "--upgrade") {
      upgrade = true;
    } else if (arg === "--install-deps") {
      installDeps = true;
    } else if (arg === "--dry-run") {
      dryRun = true;
    } else {
      throw new InstallError(`unknown argument: ${arg}`);
    }
  }
  if (!harnessArgs.length) throw new InstallError("usage: install --harness claude|pi|circle|all [--upgrade] [--install-deps] [--prefix DIR] [--dry-run]");
  const harnesses: Harness[] = harnessArgs.includes("all")
    ? [...HARNESSES]
    : [...new Set(harnessArgs)] as Harness[];
  return { harnesses, prefix: path.resolve(prefix), upgrade, installDeps, dryRun };
}

function main(argv: string[]): number {
  let parsed;
  try {
    parsed = parseArgs(argv);
  } catch (e: any) {
    console.log(JSON.stringify({ ok: false, error: e.message }, null, 1));
    return 2;
  }
  const installer = new Installer(parsed.prefix, parsed.dryRun);
  const report: any = { ok: false, dry_run: parsed.dryRun };
  try {
    report.distribution = installer.placeDistribution(parsed.upgrade);
  } catch (e: any) {
    if (e instanceof AlreadyInstalled) {
      report.error = e.message;
      report.installed_version = e.version;
      report.path = e.path;
      console.log(JSON.stringify(report, null, 1));
      return 3;
    }
    report.error = String(e.message || e);
    console.log(JSON.stringify(report, null, 1));
    return 1;
  }
  try {
    report.dependencies = installer.checkDeps(parsed.installDeps);
  } catch (e: any) {
    report.dependencies = { ok: false, error: String(e.message || e) };
  }
  report.harnesses = {};
  for (const name of parsed.harnesses) {
    try {
      report.harnesses[name] = (installer as any)[name]();
    } catch (e: any) {
      report.harnesses[name] = { ok: false, error: String(e.message || e) };
    }
  }
  report.verify = installer.verify();
  report.ok = report.verify.ok
    && report.dependencies.ok !== false
    && Object.values(report.harnesses as any[]).every((h: any) => h.ok);
  report.next = "Start a new session in the harness. On first use in a project folder the skill asks for the server URL and device build, then signs in through the browser (cex_init, cex_login_start).";
  console.log(JSON.stringify(report, null, 1));
  return report.ok ? 0 : 1;
}

if (require.main === module) {
  process.exit(main(process.argv.slice(2)));
}
