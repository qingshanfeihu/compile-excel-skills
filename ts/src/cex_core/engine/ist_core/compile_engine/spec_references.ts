import crypto from "node:crypto";
import path from "node:path";
import { P as Path, strPartition, pyShutilRmtree } from "../../_py";
import { atomic_write_bytes_nofollow } from "../../case_compiler/_sealed_io";
import { resolve_indexed_spec } from "../../kms/spec_index";

const _SLICE_HEADER =
  "<!-- ist.spec-reference-slice level=reference signing_power=none scenario_1=not_judged source={name} sha256={sha256} anchor={anchor} -->";
const _HEADING_RE = /^(#{1,6})\s/;
const _SLICE_MAX_LINES = 240;
const _SLICE_MAX_CHARS = 20000;
const _WINDOW_BEFORE = 20;
const _WINDOW_AFTER = 80;
const _HEAD_LINES = 80;

function _num_re(num: string): RegExp {
  return new RegExp(`(?<!\\d)${escapeRegExp(num)}(?!\\d)`);
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function _evidence_numbers(evidence: string): string[] {
  const [channel, , payload] = strPartition(String(evidence ?? ""), ":");
  if (!channel.startsWith("bug_") || !payload) return [];
  return payload.split(",").filter(Boolean);
}

function _slice_bounds(lines: string[], numbers: string[]): [number, number] {
  let hit: number | null = null;
  if (numbers.length) {
    const pats = numbers.map(_num_re);
    for (let idx = 0; idx < lines.length; idx++) {
      if (pats.some((p) => p.test(lines[idx]))) {
        hit = idx;
        break;
      }
    }
  }
  if (hit === null && numbers.length) {
    numbers = [];
  }
  if (!numbers.length) {
    return [0, Math.min(lines.length, _HEAD_LINES)];
  }
  let start_heading: number | null = null;
  for (let idx = hit!; idx >= 0; idx--) {
    if (_HEADING_RE.test(lines[idx])) {
      start_heading = idx;
      break;
    }
  }
  if (start_heading === null) {
    return [Math.max(0, hit! - _WINDOW_BEFORE), Math.min(lines.length, hit! + _WINDOW_AFTER)];
  }
  const level = _HEADING_RE.exec(lines[start_heading])![1].length;
  let end = lines.length;
  for (let idx = start_heading + 1; idx < lines.length; idx++) {
    const m = _HEADING_RE.exec(lines[idx]);
    if (m && m[1].length <= level) {
      end = idx;
      break;
    }
  }
  end = Math.min(end, start_heading + _SLICE_MAX_LINES);
  return [start_heading, end];
}

export function build_spec_references(
  project_root: Path,
  out_dir: Path,
  out_name: string,
  matches: Record<string, any>[]
): Record<string, any> {
  const references: Record<string, any>[] = [];
  const dropped: Record<string, any>[] = [];
  const slice_dir = out_dir.join("spec_references");
  if (slice_dir.is_dir() && !slice_dir.is_symlink()) {
    pyShutilRmtree(slice_dir.toString());
  }
  let written_dir = false;
  for (const match of matches) {
    const name = String(match?.file ?? "").trim();
    const evidence = String(match?.evidence ?? "");
    if (!name) {
      dropped.push({ file: "", reason: "invalid_match" });
      continue;
    }
    const resolved = resolve_indexed_spec(project_root.toString(), name);
    if (resolved === null) {
      dropped.push({ file: name, reason: "identity_unresolved" });
      continue;
    }
    const text = resolved.content.toString("utf8");
    const lines = text.split(/\r?\n/);
    const [start, end] = _slice_bounds(lines, _evidence_numbers(evidence));
    const body = lines.slice(start, end).join("\n").slice(0, _SLICE_MAX_CHARS);
    const end_line = start + Math.max(1, body.split(/\r?\n/).length);
    const anchor = `${name}:${start + 1}-${end_line}`;
    const header = _SLICE_HEADER.replace("{name}", name).replace("{sha256}", resolved.sha256).replace("{anchor}", anchor);
    if (!written_dir) {
      slice_dir.mkdir({ recursive: false });
      written_dir = true;
    }
    const slice_bytes = Buffer.from(header + "\n\n" + body + "\n", "utf8");
    atomic_write_bytes_nofollow(slice_dir.join(name).toString(), slice_bytes, {
      errorType: ValueError,
      invalid_message: "spec reference slice path is invalid",
      unavailable_message: "spec reference slice directory is unavailable",
    });
    references.push({
      name,
      sha256: resolved.sha256,
      size: resolved.size,
      slice_sha256: crypto.createHash("sha256").update(slice_bytes).digest("hex"),
      slice_size: slice_bytes.length,
      anchor,
      ref: `workspace/outputs/${out_name}/spec_references/${name}`,
      evidence,
    });
  }
  return { references, dropped };
}

class ValueError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "ValueError";
  }
}
