import fs from "node:fs";
import path from "node:path";
import { node_template } from "./schema";

const logger = {
  warning: (...args: any[]) => console.warn(...args),
};

export const NODES_DIR = "nodes";

function _height_to_level(height: number): string {
  if (height === 0) {
    return "leaf";
  }
  if (height === 1) {
    return "trunk";
  }
  return "branch";
}

function _parent_id(feature_id: string): string | null {
  if (!feature_id.includes(".")) {
    return null;
  }
  return feature_id.substring(0, feature_id.lastIndexOf("."));
}

export function reconcile(footprint_dir: string, nodes_subdir: string = "nodes"): Record<string, any> {
  const nodes_dir = path.join(String(footprint_dir), nodes_subdir);
  if (!fs.existsSync(nodes_dir)) {
    return { total: 0, created: 0, by_level: {} };
  }
  const nodes: Record<string, Record<string, any>> = {};
  for (const entry of fs.readdirSync(nodes_dir)) {
    if (!entry.endsWith(".json")) {
      continue;
    }
    const f = path.join(nodes_dir, entry);
    let d: Record<string, any>;
    try {
      d = JSON.parse(fs.readFileSync(f, "utf8"));
    } catch (exc) {
      logger.warning(`reconcile 读取失败 ${f}: ${exc}`);
      continue;
    }
    const fid = d.feature_id;
    if (fid) {
      nodes[fid] = d;
    }
  }
  if (Object.keys(nodes).length === 0) {
    return { total: 0, created: 0, by_level: {} };
  }
  let created = 0;
  for (const fid of Object.keys(nodes)) {
    let parent = _parent_id(fid);
    while (parent !== null) {
      if (!(parent in nodes)) {
        nodes[parent] = node_template(parent);
        created += 1;
      }
      parent = _parent_id(parent);
    }
  }
  const children: Record<string, string[]> = {};
  for (const fid of Object.keys(nodes)) {
    children[fid] = [];
  }
  for (const fid of Object.keys(nodes)) {
    const parent = _parent_id(fid);
    if (parent !== null && parent in children) {
      children[parent].push(fid);
    }
  }
  const height_cache: Record<string, number> = {};
  const height = (fid: string): number => {
    if (fid in height_cache) {
      return height_cache[fid];
    }
    const kids = children[fid] || [];
    const h = kids.length === 0 ? 0 : Math.max(...kids.map((k) => height(k))) + 1;
    height_cache[fid] = h;
    return h;
  };
  const by_level: Record<string, number> = {};
  for (const [fid, node] of Object.entries(nodes)) {
    const lvl = _height_to_level(height(fid));
    node.level = lvl;
    node.children = (children[fid] || []).slice().sort();
    by_level[lvl] = (by_level[lvl] || 0) + 1;
    const filePath = path.join(nodes_dir, `${fid}.json`);
    fs.writeFileSync(filePath, JSON.stringify(node, null, 2) + "\n", "utf8");
  }
  return { total: Object.keys(nodes).length, created, by_level };
}
