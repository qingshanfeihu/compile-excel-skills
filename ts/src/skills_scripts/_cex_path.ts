#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { dataHome } from "../platform/index";

const SKILL_DIR = path.resolve(__dirname, "..", "..", "skills", "compile-excel");

function isHome(p: string): boolean {
  return fs.existsSync(path.join(p, "dist", "cex_client", "tools.js"));
}

// 0.3.1+ installs use a versions layout: <root>/versions/<v>/ + <root>/current
// (a ref file). Resolve such a root to its active version directory; flat
// roots (development checkouts, pre-0.3.1 installs) pass through unchanged.
function resolveCandidate(p: string): string | null {
  if (isHome(p)) return path.resolve(p);
  const ref = path.join(p, "current");
  try {
    const version = fs.readFileSync(ref, "utf8").trim();
    if (version) {
      const active = path.join(p, "versions", version);
      if (isHome(active)) return path.resolve(active);
    }
  } catch {}
  return null;
}

export function cex_home(): string | null {
  const candidates: string[] = [];
  if (process.env.CEX_HOME) candidates.push(process.env.CEX_HOME);
  const marker = path.join(SKILL_DIR, ".cex_home");
  if (fs.existsSync(marker)) {
    const text = fs.readFileSync(marker, "utf8").trim();
    if (text) candidates.push(text);
  }
  let dir = path.resolve(__dirname);
  for (;;) {
    candidates.push(dir);
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  candidates.push(dataHome());
  for (const candidate of candidates) {
    const resolved = resolveCandidate(candidate);
    if (resolved !== null) return resolved;
  }
  return null;
}

export function ensure(): string {
  const home = cex_home();
  if (home === null) {
    console.error("找不到 compile-excel 发行根（dist/cex_client/）。重新运行安装器，或把 CEX_HOME 设为 compile-excel-skills 仓的检出目录。");
    process.exit(1);
  }
  return home;
}

if (require.main === module) {
  console.log(ensure());
}
