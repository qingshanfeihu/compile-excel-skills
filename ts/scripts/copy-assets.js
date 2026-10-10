const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..", "src");
const DIST = path.join(__dirname, "..", "dist");
const ROOT = path.join(__dirname, "..");

function copyDir(srcDir, dstDir, exts) {
  if (!fs.existsSync(srcDir)) return;
  for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
    const s = path.join(srcDir, entry.name);
    const d = path.join(dstDir, entry.name);
    if (entry.isDirectory()) copyDir(s, d, exts);
    else if (exts.some((e) => entry.name.endsWith(e))) {
      fs.mkdirSync(dstDir, { recursive: true });
      fs.copyFileSync(s, d);
    }
  }
}

const COPIES = [
  [path.join(SRC, "cex_client", "tool_specs.json"), path.join(DIST, "cex_client", "tool_specs.json")],
];

let n = 0;
for (const [src, dst] of COPIES) {
  if (!fs.existsSync(src)) continue;
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  n++;
}
copyDir(path.join(SRC, "cex_core", "defects", "html_extractors"), path.join(DIST, "cex_core", "defects", "html_extractors"), [".yaml", ".yml"]);
copyDir(path.join(SRC, "cex_core", "engine"), path.join(DIST, "cex_core", "engine"), [".yaml", ".yml", ".json", ".xlsx", ".md", ".txt", ".csv"]);
fs.mkdirSync(DIST, { recursive: true });
console.log(`copied ${n} top-level assets`);
