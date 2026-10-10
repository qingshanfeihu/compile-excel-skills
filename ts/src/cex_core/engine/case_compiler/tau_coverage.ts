import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { RESIDUAL_CONFIG_DISCLOSURE_SIDECAR_NAME } from "../engine_managed_outputs";

export class TauAtlasUnavailableError extends Error {
  code = "tau_atlas_unavailable";
  device_build: string;
  constructor(device_build: string) {
    const build = String(device_build || "unknown");
    super(`tau_atlas_unavailable: build-bound command teardown atlas is unavailable for device build ${build}`);
    this.device_build = build;
  }
}

export class TauReport {
  missing: Array<Record<string, any>> = [];
  covered: Array<Record<string, any>> = [];
  out_of_scope: string[] = [];
  residual_config: Array<Record<string, any>> = [];
  device_build = "";
  atlas_identity: Record<string, any> = {};
  get ok(): boolean {
    return !this.missing.length;
  }
}

function _shlexSplit(text: string): string[] {
  // shlex.split (POSIX) subset: whitespace separated, single/double quotes, backslash escapes.
  const tokens: string[] = [];
  let current = "";
  let quote: string | null = null;
  let hasCurrent = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote === "'") {
      if (c === "'") {
        quote = null;
      } else {
        current += c;
      }
      continue;
    }
    if (quote === '"') {
      if (c === '"') {
        quote = null;
      } else if (c === "\\" && i + 1 < text.length && ['"', "\\"].includes(text[i + 1])) {
        current += text[++i];
      } else {
        current += c;
      }
      continue;
    }
    if (c === "\\") {
      if (i + 1 < text.length) {
        current += text[++i];
        hasCurrent = true;
      } else {
        throw new Error("No escaped character");
      }
      continue;
    }
    if (c === '"' || c === "'") {
      quote = c;
      hasCurrent = true;
      continue;
    }
    if (/\s/.test(c)) {
      if (current || hasCurrent) {
        tokens.push(current);
        current = "";
        hasCurrent = false;
      }
      continue;
    }
    current += c;
  }
  if (quote !== null) {
    throw new Error("No closing quotation");
  }
  if (current || hasCurrent) {
    tokens.push(current);
  }
  return tokens;
}

function _persistRes(): RegExp[] {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { load_grammar } = require("./domain_grammar");
    const ld = (load_grammar().persistence_channels ?? {}).local_disk ?? {};
    const pats = ld.patterns ?? [];
    if (pats.length) {
      return pats.map((p: string) => new RegExp(p, "i"));
    }
  } catch (exc) {
    console.warn("persistence_channels 文法读取失败——τ 持久面分流回落硬编集", exc);
  }
  return [/^\s*(?:write|config)\s+(?:all|file|memory|net|segment)\b/i];
}
const _PERSIST_RES = _persistRes();

function _isPersist(line: string): boolean {
  return _PERSIST_RES.some((re) => re.test(line));
}

export function _apv_config_lines(steps: any[], init = ""): string[] {
  const out: string[] = [];
  for (const line of String(init || "").split(/\r?\n/)) {
    if (line.trim()) {
      out.push(line.trim());
    }
  }
  for (const s of steps ?? []) {
    if (s === null || Array.isArray(s) || typeof s !== "object") {
      continue;
    }
    if (!String(s.E ?? "").startsWith("APV")) {
      continue;
    }
    const method = String(s.F ?? "");
    const raw = String(s.G ?? "");
    let values: string[];
    if (method === "cmd_config") {
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const { parse_g_arguments } = require("./excel_contract");
        const [args] = parse_g_arguments(raw, method);
        values = args.length ? [String(args[0])] : [];
      } catch {
        values = [raw];
      }
    } else if (method === "cmds_config") {
      values = raw.split(/\r?\n/);
    } else {
      continue;
    }
    for (const line of values) {
      if (line.trim()) {
        out.push(line.trim());
      }
    }
  }
  return out;
}

function _derivationData(device_build = ""): [Record<string, any>, Record<string, any>] {
  let pairs: Record<string, any> = {};
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { derive_inverse_pairs } = require("./vendor_stdlib");
    pairs = { ...derive_inverse_pairs(device_build) };
  } catch (exc) {
    console.warn("inverse_forms 现算不可用——τ 仍按 atlas 分类,但实体逆元配对收窄", exc);
  }
  let requestedBuild = String(device_build).trim();
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { load_command_teardown_atlas, verify_atlas_source_identity } = require("../scripts/gen_command_teardown_atlas");
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { configured_device_os_build, device_os_build_suffix } = require("./vendor_stdlib");
    if (!requestedBuild) {
      requestedBuild = String(configured_device_os_build() || "").trim();
    }
    if (!requestedBuild) {
      throw new Error("device build is unavailable for teardown atlas binding");
    }
    requestedBuild = device_os_build_suffix(requestedBuild) || requestedBuild;
    const atlas = load_command_teardown_atlas({ expected_build: requestedBuild });
    verify_atlas_source_identity(atlas);
    return [pairs, atlas];
  } catch (exc) {
    console.warn("command_teardown_atlas 不可用或身份失配——τ 必须失败关闭", exc);
    throw new TauAtlasUnavailableError(requestedBuild);
  }
}

function _headMatch(line: string, pairs: Record<string, any>): string | null {
  const ws = line.split(/\s+/).filter(Boolean);
  for (let k = Math.min(ws.length, 5); k > 0; k--) {
    const cand = ws.slice(0, k).join(" ").toLowerCase();
    if (cand in pairs) {
      return cand;
    }
  }
  return null;
}

function _atlasHeadMatch(line: string, commands: Record<string, any>): string | null {
  const ws = line.toLowerCase().split(/\s+/).filter(Boolean);
  for (let k = ws.length; k > 0; k--) {
    const candidate = ws.slice(0, k).join(" ");
    if (candidate in commands) {
      return candidate;
    }
  }
  return null;
}

function _entities(line: string): Set<string> {
  const out = new Set<string>();
  for (const m of line.matchAll(/[\w.-]+/g)) {
    const t = m[0];
    const octets = new Set(["0", "128", "192", "224", "240", "248", "252", "254", "255"]);
    const cond =
      (/[0-9]/.test(t) && !/^[0-9.]*$/.test(t) && !t.split(".").every((seg) => octets.has(seg))) ||
      /^\d+\.\d+\.\d+\.\d+$/.test(t);
    if (cond) {
      out.add(t);
    }
  }
  return out;
}

function _inverseScopeOf(head: string, teardown: Record<string, any>, suggested: string | null): string {
  const text = String(suggested || "").trim();
  if (!text) {
    return "object";
  }
  if (String(teardown.matched_form || "") === "clear_prefix_all") {
    return "module_wide";
  }
  const tokens = text.split(/\s+/).filter(Boolean);
  if (tokens.length && tokens[tokens.length - 1].toLowerCase() === "all") {
    return "module_wide";
  }
  const verb = tokens.length ? tokens[0].toLowerCase() : "";
  if (!["clear", "no"].includes(verb)) {
    return "object";
  }
  const scopeTokens = tokens.slice(1);
  const headTokens = String(head || "").split(/\s+/).filter(Boolean);
  if (!scopeTokens.length || !headTokens.length) {
    return "object";
  }
  return scopeTokens.length < headTokens.length ? "module_wide" : "object";
}

function _derivedTau(lines: string[], pairs: Record<string, any>, atlas: Record<string, any>, rep: TauReport): void {
  const pairsLc: Record<string, any> = {};
  for (const [k, v] of Object.entries(pairs)) {
    pairsLc[k.toLowerCase()] = v;
  }
  const commands: Record<string, any> = { ...(atlas.commands ?? {}) };
  rep.device_build = String(atlas.device_build ?? "");
  rep.atlas_identity = { ...(atlas.identity ?? {}) };
  const lo = lines.map((l) => l.toLowerCase());
  let transitionCoverage: Record<string, string> = {};
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { load_ssl_lifecycle_contract } = require("./ssl_lifecycle_contract");
    const lifecycle = load_ssl_lifecycle_contract(rep.device_build, { verify_command_tree_receipts: false });
    for (const [head, cover] of Object.entries<any>(lifecycle.preflight_transition_coverage ?? {})) {
      if (String(head).trim() && String(cover).trim()) {
        transitionCoverage[String(head).trim()] = String(cover).trim();
      }
    }
  } catch {
    transitionCoverage = {};
  }

  function _objectToken(command: string, commandHead: string): string {
    let tokens: string[];
    try {
      tokens = _shlexSplit(command);
    } catch {
      return "";
    }
    const offset = String(commandHead || "").split(/\s+/).filter(Boolean).length;
    return tokens.length > offset ? tokens[offset].toLowerCase() : "";
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const ll = lo[i];
    if (ll.startsWith("no ") || ll.startsWith("clear ") || ll.startsWith("show ")) {
      continue;
    }
    if (_isPersist(line)) {
      rep.out_of_scope.push(line);
      continue;
    }
    const head = _atlasHeadMatch(line, commands);
    if (head === null) {
      continue;
    }
    const record = commands[head] ?? {};
    const className = String(record.class ?? "");
    const coveringHead = transitionCoverage[head];
    if (coveringHead) {
      const transitionObject = _objectToken(line, head);
      let coveredByPriorObject = false;
      for (let prior = 0; prior < i; prior++) {
        if (_atlasHeadMatch(lines[prior], commands) === coveringHead && _objectToken(lines[prior], coveringHead) === transitionObject) {
          coveredByPriorObject = true;
          break;
        }
      }
      if (transitionObject && coveredByPriorObject) {
        rep.covered.push({ cmd: line, head, class: className || "C2", coverage: "same_object_lifecycle_transition", entity: transitionObject, covered_by_head: coveringHead, suggested_inverse: null, atlas_provenance: { ...(record.provenance ?? {}) } });
        continue;
      }
    }
    if (head === "ssl host virtual" || head === "ssl host real") {
      let hostName = "";
      try {
        const forwardTokens = _shlexSplit(line);
        hostName = forwardTokens[head.split(/\s+/).length];
      } catch {
        hostName = "";
      }
      hostName = hostName ?? "";
      let clearedAt: number | null = null;
      for (let later = i + 1; later < lines.length; later++) {
        let tokens: string[];
        try {
          tokens = _shlexSplit(lines[later]);
        } catch {
          continue;
        }
        if (tokens.length >= 4 && tokens.slice(0, 3).map((t) => t.toLowerCase()).join(" ") === "clear ssl host" && (!hostName || tokens[3] === hostName)) {
          clearedAt = later;
          break;
        }
      }
      if (clearedAt !== null && clearedAt + 1 < lines.length && lines[clearedAt + 1].trim().toUpperCase() === "YES") {
        rep.covered.push({ cmd: line, head, class: className || "C2", coverage: "reference_interactive_object_teardown", entity: hostName, suggested_inverse: null, atlas_provenance: { ...(record.provenance ?? {}) } });
        continue;
      }
    }
    if (className === "C1") {
      rep.covered.push({ cmd: line, head, class: "C1", coverage: "framework_per_case_cleanup", entity: "", suggested_inverse: null, atlas_provenance: { ...(record.provenance ?? {}) } });
      continue;
    }
    if (className === "C3") {
      const residual = { command: line, head, class: "C3", provenance: { ...(record.provenance ?? {}) }, xml_src: [...((record.xml ?? {}).src ?? [])] };
      if (!rep.residual_config.some((item) => item.command === line && item.head === head)) {
        rep.residual_config.push(residual);
      }
      continue;
    }
    if (!["C2", "C2b"].includes(className)) {
      continue;
    }
    const pair = pairsLc[head] ?? {};
    const invNo = String(pair.no ?? "").toLowerCase();
    const invClear = String(pair.clear ?? "").toLowerCase();
    const teardown: Record<string, any> = { ...(record.teardown ?? {}) };
    const atlasSuggestion = String(teardown.suggested_inverse ?? "").trim();
    const atlasSuggestionLc = atlasSuggestion.toLowerCase();
    const atlasCoverageLc = teardown.suggested_inverse_executable !== false ? atlasSuggestionLc : "";
    const ents = _entities(line);
    let earlyCovered = false;
    if (invNo && ents.size) {
      for (let j = 0; j < i; j++) {
        if (lo[j].startsWith(invNo)) {
          const other = _entities(lines[j]);
          if ([...ents].some((e) => other.has(e))) {
            earlyCovered = true;
            break;
          }
        }
      }
    }
    if (invNo && ents.size && earlyCovered) {
      rep.covered.push({ cmd: line, entity: [...ents].sort().slice(0, 2).join(", "), suggested_inverse: "(restore write, itself part of τ)" });
      continue;
    }

    function _atlasCovers(index: number): boolean {
      if (!atlasCoverageLc || !lo[index].startsWith(atlasCoverageLc)) {
        return false;
      }
      if (atlasCoverageLc.startsWith("no ")) {
        if (!ents.size) {
          return true;
        }
        const other = _entities(lines[index]);
        return [...ents].some((e) => other.has(e));
      }
      return true;
    }
    let covered = false;
    for (let j = i + 1; j < lines.length; j++) {
      const other = _entities(lines[j]);
      const entOverlap = [...ents].some((e) => other.has(e));
      if ((invNo && lo[j].startsWith(invNo) && (!ents.size || entOverlap)) || (invClear && lo[j].startsWith(invClear)) || _atlasCovers(j)) {
        covered = true;
        break;
      }
    }
    const ordered = [...line.matchAll(/[\w.-]+/g)].map((m) => m[0]).filter((t) => ents.has(t));
    const named = ordered.filter((t) => !/^\d+\.\d+\.\d+\.\d+$/.test(t));
    const ent = named.length ? named[named.length - 1] : ordered.length ? ordered[ordered.length - 1] : "";
    let suggestedInverse: string | null = atlasSuggestion || null;
    if (suggestedInverse && invNo && atlasSuggestionLc === invNo && ent) {
      suggestedInverse = `${atlasSuggestion} ${ent}`.trim();
    }
    const inverseScope = _inverseScopeOf(head, teardown, suggestedInverse);
    if (inverseScope === "module_wide") {
      suggestedInverse = null;
    }
    const item = {
      cmd: line,
      head,
      class: className,
      entity: ent,
      suggested_inverse: suggestedInverse,
      atlas_suggested_inverse: atlasSuggestion || null,
      inverse_scope: inverseScope,
      suggestion_status: String(teardown.status ?? ""),
      suggested_inverse_executable: teardown.suggested_inverse_executable,
      src: String(pair.src ?? ""),
      atlas_provenance: { ...(record.provenance ?? {}) },
    };
    (covered ? rep.covered : rep.missing).push(item);
  }
}

export const RESIDUAL_DISCLOSURE_SIDECAR = RESIDUAL_CONFIG_DISCLOSURE_SIDECAR_NAME;
export const RESIDUAL_DISCLOSURE_SCHEMA = "ist.residual-config-disclosure";

function _residualDisclosurePayload(autoid: string, report: TauReport, opts: { discovery_stages: string[]; existing_commands?: Array<Record<string, any>> | null }): Record<string, any> | null {
  if (!report.residual_config.length) {
    return null;
  }
  const commandRows: Record<string, Record<string, any>> = {};
  for (const raw of [...(opts.existing_commands ?? []), ...report.residual_config]) {
    if (raw === null || Array.isArray(raw) || typeof raw !== "object") {
      continue;
    }
    const command = String(raw.command ?? "").trim();
    const head = String(raw.head ?? "").trim();
    if (!command || !head) {
      continue;
    }
    commandRows[JSON.stringify([head, command])] = { command, head, class: "C3", provenance: { ...(raw.provenance ?? {}) }, xml_src: [...(raw.xml_src ?? [])].map(String).sort() };
  }
  const commands = Object.keys(commandRows).sort().map((key) => commandRows[key]);
  if (!commands.length) {
    return null;
  }
  const identity = { ...(report.atlas_identity ?? {}) };
  const identitySha = String(identity.sha256 ?? "");
  const core = { code: "residual_config_disclosure", autoid: String(autoid), device_build: String(report.device_build), atlas_identity_sha256: identitySha, commands };
  const disclosureId = crypto.createHash("sha256").update(JSON.stringify(core), "utf8").digest("hex");
  return {
    schema: RESIDUAL_DISCLOSURE_SCHEMA,
    autoid: String(autoid),
    disclosure: {
      ...core,
      disclosure_id: disclosureId,
      message_zh: "本案配置无机械收回途径，会留残留",
      atlas_identity: identity,
      discovery_stages: [...new Set(opts.discovery_stages.map(String).filter(Boolean))].sort(),
    },
  };
}

export function persist_residual_config_disclosure(case_dir: string, autoid: string, report: TauReport, opts: { discovery_stage: string }): Record<string, any> | null {
  if (!report.residual_config.length) {
    return null;
  }
  const sidecarPath = path.join(String(case_dir), RESIDUAL_DISCLOSURE_SIDECAR);
  let existingCommands: Array<Record<string, any>> = [];
  const stages = [opts.discovery_stage];
  const lst = fs.existsSync(sidecarPath) || fs.existsSync(sidecarPath);
  let stat: fs.Stats | null = null;
  try {
    stat = fs.lstatSync(sidecarPath);
  } catch {
    stat = null;
  }
  if (stat !== null) {
    if (stat.isSymbolicLink() || !stat.isFile()) {
      throw new Error("residual disclosure sidecar path is invalid");
    }
    let old: any;
    try {
      old = JSON.parse(fs.readFileSync(sidecarPath, "utf8"));
    } catch (exc) {
      throw new Error("residual disclosure sidecar is unreadable");
    }
    const oldDisclosure = old !== null && typeof old === "object" && !Array.isArray(old) ? old.disclosure : null;
    const sameIdentity =
      oldDisclosure !== null &&
      typeof oldDisclosure === "object" &&
      !Array.isArray(oldDisclosure) &&
      old.schema === RESIDUAL_DISCLOSURE_SCHEMA &&
      String(old.autoid ?? "") === String(autoid) &&
      String(oldDisclosure.device_build ?? "") === report.device_build &&
      String(oldDisclosure.atlas_identity_sha256 ?? "") === String((report.atlas_identity ?? {}).sha256 ?? "");
    if (!sameIdentity) {
      throw new Error("residual disclosure sidecar identity/schema does not match this case");
    }
    existingCommands = [...(oldDisclosure.commands ?? [])];
    stages.push(...(oldDisclosure.discovery_stages ?? []));
  }
  const payload = _residualDisclosurePayload(autoid, report, { discovery_stages: stages, existing_commands: existingCommands });
  if (payload === null) {
    return null;
  }
  const raw = Buffer.from(JSON.stringify(payload, null, 2) + "", "utf8");
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { atomic_write_bytes_nofollow } = require("./_sealed_io");
  const digest = atomic_write_bytes_nofollow(sidecarPath, raw, {
    error_type: Error,
    invalid_message: "residual disclosure sidecar path is invalid",
    unavailable_message: "residual disclosure sidecar write failed",
    create_parents: true,
    mode: 0o600,
  });
  return { path: sidecarPath, sha256: digest, payload };
}

export function inverse_line(item: Record<string, any>, opts: { audience?: string } = {}): string {
  const audience = opts.audience ?? "machine";
  const suggested = item.suggested_inverse;
  if (suggested) {
    return String(suggested);
  }
  if (String(item.inverse_scope ?? "") === "module_wide") {
    if (audience === "user") {
      return `[module-wide] ${item.head}:XML 只提供模块级复位，作用域大于本案对象，需自行给出对象级恢复步`;
    }
    return `[module-wide] ${item.head}: the XML only offers a module-wide reset, whose scope exceeds the object this case created — derive an object-scoped teardown yourself (lang_query kind='heads'/'param').`;
  }
  if (audience === "user") {
    return `[unknown] ${item.head}:默认方向表无记录，不得机械翻转`;
  }
  return `[unknown] ${item.head}: no default-direction record exists; do not mechanically invert.`;
}

export function tau_ledger_mutator(report: TauReport): (claims: any[]) => any[] {
  const invSeq = [...report.missing].reverse().map((m) => inverse_line(m, { audience: "user" }));
  const invSeqEn = [...report.missing].reverse().map((m) => inverse_line(m));
  const commands = report.missing.map((m) => m.cmd);
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { conflict_chain_id } = require("../ist_core/compile_engine/conflict_chain");
  const chainId = conflict_chain_id({
    scenario: "missing_teardown",
    commands,
    teardown_axis: [...report.missing].reverse().map((item) => ({
      head: String(item.head ?? ""),
      scope: String(item.inverse_scope ?? "object"),
      inverse: item.suggested_inverse ?? null,
    })),
  });

  function _mutate(claims: any[]): any[] {
    const kept = claims.filter((c) => c.claim_kind !== "missing_teardown");
    kept.push({
      claim_kind: "missing_teardown",
      conflict_chain_id: chainId,
      commands,
      suggested_tau: invSeq,
      suggested_tau_en: invSeqEn,
      teardown_evidence: report.missing.map((item) => ({
        command: String(item.cmd ?? ""),
        head: String(item.head ?? ""),
        class: String(item.class ?? ""),
        suggested_inverse: item.suggested_inverse,
        inverse_scope: String(item.inverse_scope ?? "object"),
        suggestion_status: String(item.suggestion_status ?? ""),
        suggested_inverse_executable: item.suggested_inverse_executable,
        atlas_provenance: { ...(item.atlas_provenance ?? {}) },
      })),
      atlas_identity: { ...(report.atlas_identity ?? {}) },
      device_build: String(report.device_build ?? ""),
      reason: `卷面有 ${report.missing.length} 条配置写不属于框架 C1 自动清理面,且没有案尾恢复步——会污染同批后续用例。atlas 建议序列:` + invSeq.join("；"),
      suggested_fix: "按 atlas 已知逆元在案尾追加恢复序列；unknown 默认方向须先补来源/实测，不得机械翻转；或确认该写是被测行为本身需保留",
      min_requests: 0,
      ordering_sensitive: false,
    });
    return kept;
  }
  return _mutate;
}

export function check_tau_coverage_lines(lines: string[], opts: { device_build?: string } = {}): TauReport {
  const rep = new TauReport();
  const normalized = lines.map((line) => String(line ?? "").trim().toLowerCase());
  if (normalized.every((line) => !line || line.startsWith("show ") || line.startsWith("no ") || line.startsWith("clear "))) {
    rep.device_build = String(opts.device_build ?? "");
    return rep;
  }
  const [pairs, atlas] = _derivationData(opts.device_build ?? "");
  _derivedTau(lines, pairs, atlas, rep);
  return rep;
}

export function check_tau_coverage(steps: any[], init = "", opts: { device_build?: string } = {}): TauReport {
  return check_tau_coverage_lines(_apv_config_lines(steps, init), opts);
}
