#!/usr/bin/env node
// 找到 compile-excel 的 TypeScript 发行根（含 dist/cex_client/）并打印。
// 顺序：1. 环境变量 CEX_HOME；2. skill 目录下的 .cex_home（安装器写入）；
// 3. 从本文件往上找（开发检出、插件缓存根）；4. 默认安装位
//    （Windows %LOCALAPPDATA%\compile-excel\current，其余 ~/.local/share/compile-excel/current）。

const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

const SKILL_DIR = path.resolve(__dirname, "..");

function isHome(p) {
  try {
    return fs.statSync(path.join(p, "dist", "cex_client", "tools.js")).isFile();
  } catch {
    return false;
  }
}

function dataHome() {
  if (process.platform === "win32") {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(base, "compile-excel");
  }
  return path.join(os.homedir(), ".local", "share", "compile-excel");
}

function cexHome() {
  const candidates = [];
  if (process.env.CEX_HOME) candidates.push(process.env.CEX_HOME);
  const marker = path.join(SKILL_DIR, ".cex_home");
  try {
    const text = fs.readFileSync(marker, "utf8").trim();
    if (text) candidates.push(text);
  } catch {}
  let dir = path.resolve(__dirname);
  for (;;) {
    candidates.push(dir);
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  candidates.push(path.join(dataHome(), "current"));
  for (const candidate of candidates) {
    if (candidate && isHome(candidate)) return path.resolve(candidate);
  }
  return null;
}

const home = cexHome();
if (home === null) {
  console.error(
    "找不到 compile-excel 发行根（dist/cex_client/）。先在检出目录运行 npm install && npm run build，" +
      "再运行安装器，或把 CEX_HOME 设为该目录。",
  );
  process.exit(1);
}
console.log(home);
