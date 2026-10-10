import { _cex_data_path } from "../../../_root";
import { scrub_text } from "../../security_scrub";
import {
  atomic_write_bytes_nofollow,
  read_regular_nofollow,
  sha256_bytes,
  validate_json_budget,
} from "../../../case_compiler/_sealed_io";
import { P, Match, pyJsonDumps, pyJsonLoads, reFinditer, reSub } from "../../../_py";

const _MINDMAP_LEADING_MARKERS: Buffer[] = [Buffer.from([0xef, 0xbf, 0xbf]), Buffer.from([0xef, 0xbb, 0xbf])];

function _stripMindmapLeadingMarkers(raw: Buffer): Buffer {
  let body = raw;
  for (;;) {
    if (body.length === 0) break;
    const matched = _MINDMAP_LEADING_MARKERS.find((marker) => body.subarray(0, marker.length).equals(marker));
    if (!matched) break;
    body = body.subarray(matched.length);
  }
  return body;
}

function _logicalSourceId(path: P): string {
  const projectRoot = new P(_cex_data_path(""));
  let logical: string;
  try {
    logical = path.resolve().relative_to(projectRoot).as_posix();
  } catch {
    logical = `sandbox-input/${path.name}`;
  }
  return scrub_text(logical, { scrub_paths: false });
}

function _loadMindmap(path: P): [any[], Buffer] {
  const raw = read_regular_nofollow(path._p, {
    errorType: Error,
    invalid_message: "mindmap path is invalid",
    directory_message: "mindmap parent is unavailable",
    open_message: "mindmap is unavailable",
    bounds_message: "mindmap exceeds its sealed size boundary",
    changed_message: "mindmap changed while being read",
    max_bytes: 32 * 1024 * 1024,
    min_bytes: 1,
  }) as Buffer;
  const body = _stripMindmapLeadingMarkers(raw);
  validate_json_budget(body, { errorType: Error, message: "mindmap exceeds the JSON structure budget" });
  let payload: any;
  try {
    payload = pyJsonLoads(body.toString("utf8"));
  } catch (exc) {
    throw new Error("mindmap must be one complete JSON document with no trailing data");
  }
  if (!Array.isArray(payload) || payload.length !== 1) {
    throw new Error("mindmap JSON top level must be a one-element [root] array");
  }
  const root = payload[0];
  if (typeof root !== "object" || root === null || Array.isArray(root)) {
    throw new Error("mindmap root must be an object");
  }
  if (typeof root.data !== "object" || root.data === null || Array.isArray(root.data)) {
    throw new Error("mindmap root must contain a data object");
  }
  if (!Array.isArray(root.children)) {
    throw new Error("mindmap root must contain a children array");
  }
  return [payload, raw];
}

function _verifyPreservedEntryBytes(directory: P, preserved: Map<string, Buffer>): void {
  for (const [name, expected] of preserved) {
    const current = read_regular_nofollow(directory.joinpath(name)._p, {
      errorType: Error,
      trusted_root: directory._p,
      min_bytes: expected.length,
      max_bytes: expected.length,
      require_current_uid: true,
      invalid_message: "preserved entry path is invalid",
      directory_message: "preserved entry directory is unavailable",
      open_message: "preserved entry is unavailable",
      bounds_message: "preserved entry size changed",
      changed_message: "preserved entry changed while reading",
    }) as Buffer;
    if (!current.equals(expected)) {
      throw new Error("preserved entry changed after validation");
    }
  }
}

function _archiveNonemptyBatchBeforeRecreate(batchDir: P, batchName: string): string {
  if (!batchDir.exists()) return "";
  if (batchDir.is_symlink() || !batchDir.is_dir()) {
    throw new Error("batch output directory is not a safe regular directory");
  }
  const names = new Set<string>(batchDir.iterdir().map((entry: any) => String(entry.name)));
  if (names.size === 0) return "";
  let preserved = new Map<string, Buffer>();
  let validatedEntry = false;
  const sh = require("../compile_engine/_shared");
  const CC = require("../compile_engine/compile_context");
  const context = sh.current_engine_node_context();
  const setsEqual = (a: Set<string>, b: Iterable<string>): boolean => {
    const bs = new Set(b);
    return a.size === bs.size && [...a].every((x) => bs.has(x));
  };
  if (context !== null && context !== undefined && context[1] === "prep") {
    const validated = CC.validate_entry_initialization(new P(String(sh.project_root())), batchDir.parent, batchName, { state: context[0] });
    preserved = validated instanceof Map ? validated : new Map(Object.entries(validated));
    validatedEntry = true;
    _verifyPreservedEntryBytes(batchDir, preserved);
    if (setsEqual(names, preserved.keys())) return "";
  } else if (setsEqual(names, ["compile_context.json", "compile_entry_inputs.json"])) {
    return "";
  } else if (!names.has("manifest.json") && (setsEqual(names, ["compile_context.json"]) || names.has("engine_run.json"))) {
    throw new CC.CompileContextIdentityError("current entry initialization requires a trusted prep scope");
  }
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  let archiveStem = `${batchName}_pre_recreate_${stamp}`;
  if (archiveStem.length > 180) {
    const digest = sha256_bytes(Buffer.from(batchName, "utf8")).slice(0, 12);
    archiveStem = `${batchName.slice(0, 120)}_${digest}_pre_recreate_${stamp}`;
  }
  const { quarantine_root } = require("../compile_engine/batch_storage");
  const archiveRoot = new P(String(quarantine_root(batchDir.parent._p)));
  archiveRoot.mkdir({ parents: true, exist_ok: true });
  let archive = archiveRoot.joinpath(archiveStem);
  let sequence = 0;
  while (archive.exists() || archive.is_symlink()) {
    sequence += 1;
    archive = archiveRoot.joinpath(`${archiveStem}_${sequence}`);
  }
  const contextPath = batchDir.joinpath("compile_context.json");
  if (contextPath.is_symlink()) {
    throw new Error("compile context is a symbolic link before batch archive");
  }
  if (!validatedEntry && contextPath.is_file()) {
    const contextRaw = read_regular_nofollow(contextPath._p, {
      errorType: Error,
      invalid_message: "compile context path is invalid before batch archive",
      directory_message: "compile context directory is unavailable before batch archive",
      open_message: "compile context is unavailable before batch archive",
      bounds_message: "compile context exceeds its archive boundary",
      changed_message: "compile context changed during batch archive",
      max_bytes: 4 * 1024 * 1024,
      min_bytes: 2,
    }) as Buffer;
    preserved.set("compile_context.json", contextRaw);
  }
  const sidecarPath = batchDir.joinpath("compile_entry_inputs.json");
  if (sidecarPath.is_symlink()) {
    throw new Error("entry input sidecar is a symbolic link before batch archive");
  }
  if (!validatedEntry && sidecarPath.is_file()) {
    const sidecarRaw = read_regular_nofollow(sidecarPath._p, {
      errorType: Error,
      invalid_message: "entry input sidecar path is invalid before batch archive",
      directory_message: "entry input sidecar directory is unavailable before batch archive",
      open_message: "entry input sidecar is unavailable before batch archive",
      bounds_message: "entry input sidecar exceeds its archive boundary",
      changed_message: "entry input sidecar changed during batch archive",
      max_bytes: 64 * 1024,
      min_bytes: 2,
    }) as Buffer;
    preserved.set("compile_entry_inputs.json", sidecarRaw);
  }
  _verifyPreservedEntryBytes(batchDir, preserved);
  batchDir.rename(archive);
  let created = false;
  try {
    _verifyPreservedEntryBytes(archive, preserved);
    batchDir.mkdir();
    created = true;
    for (const [name, raw] of preserved) {
      atomic_write_bytes_nofollow(batchDir.joinpath(name)._p, raw, {
        errorType: Error,
        invalid_message: "new entry path is invalid after batch archive",
        unavailable_message: "new batch directory is unavailable after batch archive",
      });
    }
  } catch (exc) {
    try {
      if (created) {
        for (const name of preserved.keys()) {
          batchDir.joinpath(name).unlink({ missing_ok: true });
        }
        batchDir.rmdir();
      }
    } catch {
      console.error("批目录归档失败后新目录清理不完整");
    }
    if (!batchDir.exists() && archive.exists()) {
      archive.rename(batchDir);
    }
    throw exc;
  }
  return archive.name;
}

function _nodeText(node: Record<string, any>): string {
  return String((node.data ?? {}).text ?? "").trim();
}

function _nodeChildren(node: Record<string, any>): any[] {
  return node.children ?? [];
}

function _nodeData(node: Record<string, any>): Record<string, any> {
  return node.data ?? {};
}

const _NUMBERED_STEP_RE = "^\\s*(?:\\[?([0-9]+)\\]?)[.、:：)）]\\s*";
const _CHECK_REF_RE = "\\[([A-Za-z0-9_-]+)\\]";

function _numberedSourceAtoms(text: string): Array<[string, string]> {
  const source = String(text ?? "");
  const matches = reFinditer(_NUMBERED_STEP_RE, source, "m");
  const atoms: Array<[string, string]> = [];
  for (const [index, match] of matches.entries()) {
    const end = index + 1 < matches.length ? matches[index + 1].start() : source.length;
    const atom = source.slice(match.start(), end).trim();
    if (atom) atoms.push([String(match.group(1)), atom]);
  }
  return atoms;
}

function _actionSourceAtoms(text: string): Array<[string, string]> {
  const source = String(text ?? "");
  const numbered = _numberedSourceAtoms(source);
  if (numbered.length > 0) return numbered;
  const lines = source.split(/\r?\n/).map((line) => line.trim()).filter((line) => line.length > 0);
  if (lines.length > 1) {
    return lines.map((line, index) => [String(index + 1), line] as [string, string]);
  }
  return source.trim() ? [["1", source.trim()]] : [];
}

function _labeledExpectationAtoms(text: string): Map<string, string> {
  const source = String(text ?? "");
  const matches = reFinditer("^\\s*\\[([A-Za-z0-9_-]+)\\]\\s*", source, "m");
  const atoms = new Map<string, string>();
  for (const [index, match] of matches.entries()) {
    const end = index + 1 < matches.length ? matches[index + 1].start() : source.length;
    const atom = source.slice(match.start(), end).trim();
    if (atom) atoms.set(String(match.group(1)).toLowerCase(), atom);
  }
  return atoms;
}

function _sourceStepIntents(node: Record<string, any>): [Array<Record<string, string>>, string, string[]] {
  const children = _nodeChildren(node);
  if (children.length === 1 && _nodeChildren(children[0]).length === 0 && _numberedSourceAtoms(_nodeText(children[0])).length === 0) {
    const actionBlock = _nodeText(node);
    const expectationBlock = _nodeText(children[0]);
    const actions = _actionSourceAtoms(actionBlock);
    const labeled = _labeledExpectationAtoms(expectationBlock);
    const intents: Array<Record<string, string>> = [];
    const matchedLabels = new Set<string>();
    for (const [, action] of actions) {
      const refs = reFinditer(_CHECK_REF_RE, action, "i").map((m: Match) => String(m.group(1)).toLowerCase());
      const expectedParts = refs.filter((label: string) => labeled.has(label)).map((label: string) => labeled.get(label)!);
      for (const label of refs) if (labeled.has(label)) matchedLabels.add(label);
      if (expectedParts.length === 0 && actions.length === 1) {
        if (expectationBlock) expectedParts.push(expectationBlock);
        for (const label of labeled.keys()) matchedLabels.add(label);
      }
      intents.push({ desc: action, expected: expectedParts.join("  ") });
    }
    const unmatched = [...labeled.entries()].filter(([label]) => !matchedLabels.has(label)).map(([, value]) => value);
    return [intents, "case_body_with_leaf_expectation", unmatched];
  }
  const intents: Array<Record<string, string>> = [];
  for (const stepNode of children) {
    const stepDesc = _nodeText(stepNode);
    const expects = _nodeChildren(stepNode).map((c: any) => _nodeText(c)).filter((t: string) => t);
    intents.push({ desc: stepDesc, expected: expects.length ? expects.join("  ") : "" });
  }
  return [intents, "title_steps_expectations", []];
}

export function _extract_cases(root: Record<string, any>): Array<Record<string, any>> {
  return _extractCases(root);
}

function _extractCases(root: Record<string, any>): Array<Record<string, any>> {  const cases: Array<Record<string, any>> = [];
  const walk = (node: Record<string, any>, groupPath: string[]): void => {
    const d = _nodeData(node);
    const autoid = String(d.autoid ?? "").trim();
    if (autoid) {
      const autoMarker = String(d.auto ?? "").trim();
      if (autoMarker && autoMarker.toUpperCase() !== "YES") return;
      const [stepIntents, sourceLayout, unboundExpectations] = _sourceStepIntents(node);
      cases.push({
        autoid,
        title: _nodeText(node),
        group_path: [...groupPath],
        priority: d.priority ?? null,
        resource: d.resource ?? null,
        source_layout: sourceLayout,
        step_intents: stepIntents,
        unbound_expectations: unboundExpectations,
        init_commands: null,
        steps: null,
        assertions_provenance: null,
        compile_state: { draft_xlsx: null, verdict: null, device_truth: null, grade: null, rounds: 0, status: "pending" },
      });
      return;
    }
    const title = _nodeText(node);
    const nextPath = title ? [...groupPath, title] : groupPath;
    for (const c of _nodeChildren(node)) walk(c, nextPath);
  };
  walk(root, []);
  return cases;
}

function _counts(values: Iterable<string>): Map<string, number> {
  const out = new Map<string, number>();
  for (const v of values) out.set(v, (out.get(v) ?? 0) + 1);
  return out;
}

function _mapToSortedObject(m: Map<string, number>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of [...m.entries()].sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))) out[k] = v;
  return out;
}

export function compile_prep(mindmap_path: string, out_name = ""): string {
  let p: P;
  try {
    const { _resolve_inside_root } = require("../deepagent/file_tools");
    p = new P(String(_resolve_inside_root(mindmap_path, { must_exist: true })));
  } catch {
    return `error: mindmap file does not exist: ${scrub_text(mindmap_path)}`;
  }
  if (!p.is_file()) {
    return `error: mindmap file does not exist: ${scrub_text(mindmap_path)}`;
  }
  let cases: Array<Record<string, any>>;
  let sourceBytes: Buffer;
  try {
    const [mm, raw] = _loadMindmap(p);
    sourceBytes = raw;
    cases = _extractCases(mm[0]);
  } catch (exc) {
    return `error: mindmap parse failed: ${scrub_text(exc)}`;
  }
  if (cases.length === 0) {
    return "error: no case node with an autoid found in the mindmap — confirm this is a test-case mindmap (case nodes should carry an autoid field in their data).";
  }
  const _sh = require("../compile_engine/_shared");
  const invalidAutoids: string[] = [];
  for (const case_ of cases) {
    const autoid = String(case_.autoid ?? "");
    try {
      _sh.safe_output_component(autoid, { field: "autoid" });
    } catch {
      invalidAutoids.push(autoid);
      continue;
    }
    if (!/^\d{18}$/.test(autoid)) {
      invalidAutoids.push(autoid);
    }
  }
  if (invalidAutoids.length > 0) {
    return "error: mindmap contains invalid production autoid values; each case autoid must be one 18-digit requirements-system id";
  }
  const seen = new Set<string>();
  const dups: string[] = [];
  for (const c of cases) {
    if (seen.has(c.autoid)) dups.push(c.autoid);
    seen.add(c.autoid);
  }
  if (dups.length > 0) {
    return "error: mindmap contains duplicate autoid primary keys";
  }
  const groups = _counts(cases.map((c) => c.group_path.join(" / ")));
  const titles = _counts(cases.map((c) => c.title));
  const dupTitles = new Map([...titles.entries()].filter(([, n]) => n > 1));
  const familyKey = (c: Record<string, any>): string => {
    const si: Array<Record<string, string>> = c.step_intents ?? [];
    const first = si.length ? si[0].desc ?? "" : "";
    return reSub("\\s+", "", reSub("\\d+", "N", first));
  };
  const famMap = new Map<string, string[]>();
  for (const c of cases) {
    const key = familyKey(c);
    if (!famMap.has(key)) famMap.set(key, []);
    famMap.get(key)!.push(c.autoid);
  }
  let famId = 0;
  const families: Array<Record<string, any>> = [];
  for (const [key, aids] of famMap) {
    famId += 1;
    const fid = `F${String(famId).padStart(2, "0")}`;
    for (const c of cases) {
      if (aids.includes(c.autoid)) c.family = fid;
    }
    families.push({ family: fid, size: aids.length, head: aids[0], members: aids, key_hint: key.slice(0, 60) });
  }
  families.sort((a, b) => b.size - a.size);
  let sub: string;
  try {
    sub = String(_sh.safe_output_component(out_name || p.stem, { field: "out_name" }));
  } catch (exc) {
    return `error: ${exc instanceof Error ? exc.message : String(exc)}`;
  }
  const manifest = {
    batch_id: `compile-${sub}`,
    source: _logicalSourceId(p),
    source_snapshot: `workspace/outputs/${sub}/mindmap_source.json`,
    source_sha256: sha256_bytes(sourceBytes),
    source_size: sourceBytes.length,
    out_name: sub,
    case_count: cases.length,
    groups: _mapToSortedObject(groups),
    families,
    cases,
  };
  const batchDir = new P(String(_sh.outputs_root())).joinpath(sub);
  const archivedBatch = _archiveNonemptyBatchBeforeRecreate(batchDir, sub);
  const out = batchDir.joinpath("manifest.json");
  const snapshot = out.parent.joinpath("mindmap_source.json");
  atomic_write_bytes_nofollow(snapshot._p, sourceBytes, {
    errorType: Error,
    invalid_message: "mindmap snapshot path is invalid",
    unavailable_message: "mindmap snapshot directory is unavailable",
  });
  const manifestBytes = Buffer.from(pyJsonDumps(manifest, { ensure_ascii: false, indent: 2 }) + "\n", "utf8");
  atomic_write_bytes_nofollow(out._p, manifestBytes, {
    errorType: Error,
    invalid_message: "manifest output path is invalid",
    unavailable_message: "manifest output directory is unavailable",
  });
  const dupNote = dups.length ? `\n⚠️ duplicate autoids: [${dups.map((d) => `'${d}'`).join(", ")}]` : "";
  const groupsShown = _mapToSortedObject(new Map([...groups.entries()].slice(0, 12)));
  const groupsText = pyJsonDumps(groupsShown, { ensure_ascii: false });
  return (
    `=== compile_prep ===\nmanifest written: ${out}\n` +
    (archivedBatch ? `previous non-empty batch quarantined: workspace/quarantine/compile_engine/${archivedBatch}\n` : "") +
    `mindmap: ${p.name}  total cases: ${cases.length}\n` +
    `groups (${groups.size}): ${groupsText}\n` +
    `intent families (${families.length}): ` +
    families.slice(0, 8).map((f) => `${f.family}×${f.size}`).join("; ") +
    `\nduplicate titles: ${dupTitles.size} (autoid is the primary key; duplicate titles are not deduplicated, each compiles independently)\n${dupNote}\n--- the manifest holds requirements only (title/group/steps/expectations), no commands ---\nevery case's init_commands/steps/assertions_provenance is null,\nfilled in by the authoring sub-agent after consulting manuals/precedents. Next: the orchestrator dispatches briefs per case.`
  );
}
