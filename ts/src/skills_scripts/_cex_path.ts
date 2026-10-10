#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { dataHome } from "../platform/index";

const SKILL_DIR = path.resolve(__dirname, "..", "..", "skills", "compile-excel");

function isHome(p: string): boolean {
  return fs.existsSync(path.join(p, "dist", "cex_client", "tools.js"));
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
  candidates.push(path.join(dataHome(), "current"));
  for (const candidate of candidates) {
    if (isHome(candidate)) return path.resolve(candidate);
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
