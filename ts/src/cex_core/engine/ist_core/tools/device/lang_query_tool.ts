import path from "node:path";

import {
  QueryUnavailable,
  capability_signature,
  capability_usage_of,
  confirmation_prompt_of,
  dispatch_domain_orientation,
  dispatch_kind_cross_check,
  dispatch_kind_of,
  host_observation,
  language_document_catalog,
  apv_full_fs,
  nearest_candidates,
  usage_index_corpus_meta,
  usage_index_empty_bucket_notes,
  MANUAL_SOURCE_UNAVAILABLE,
  NOT_DIRECTLY_HIT,
  PARAM_CONTRACT_UNAVAILABLE,
  manual_param_excerpt,
  param_contract_of,
} from "../../../case_compiler/apv_lang";
import { ExcelContractError, load_excel_contract, contract_enabled_fs_by_e } from "../../../case_compiler/excel_contract";
import { pyJsonDumps } from "../../../_py";

const _KINDS = ["contract", "signature", "dispatch", "usage", "nearest", "prompt_pattern", "docs", "param", "complete", "heads", "host"] as const;
export const COMMAND_HEADS_QUERY_SCHEMA = "ist.command-heads-query";

export interface CommandHeadsQueryResult {
  schema: string;
  status: "complete" | "worker_session_unavailable" | "capability_build_missing" | "command_tree_unavailable" | "capability_identity_mismatch" | "receipt_unavailable" | "result_too_large";
  module_prefix: string;
  device_build: string;
  capability_generation_id: string;
  capability_manifest_sha256: string;
  projection_version: string;
  count: number;
  heads: string[];
  receipt_id: string;
  result_sha256: string;
}

const _COMPLETE_SHOWN_K = 5;
const _MAX_HEADS_RESULT_BYTES = 256 * 1024;
const _ASSERTION_IDENTITY_NOTE = "assertion_identity: a check_point row redeems exactly one claim on this case's frozen contract card. When the card carries a claim with typed_assertion_status `pending author_claim`, the assertion you write must carry that claim's minted expectation_id and semantic_key verbatim — you never mint them yourself, and emit requires every contract expectation_id to be covered by at least one check_point row. Rows sharing one id must differ in observation, operator, or expected value; two assertions doing the same thing verify one thing. A composite combinator that fans out into N rows must also reproduce its complete generator ordinal set.\n  carrier position: the single assertion — an OBSERVE_ASSERT.asserts[] entry, or the one synthesized assertion of CAPTURE_COMPARE / EXPECT_FROM / OBSERVE_DIST / OBSERVE_MEMBER (there block-level IS assertion-level), or a STEP whose E is check_point. Anywhere else (block level of OBSERVE_ASSERT, a non-check_point STEP, a nested sub-container) the expansion refuses, because putting it there would be silently dropped.\n  accepted compiled forms for a pending claim: either source.kind=intent with source.ref equal to the expectation_id and a non-empty G (the expectation is a verbatim transcription of what the author declared), or one of the four relational/composite combinators above, whose observation_ref must close onto an explicit earlier observation step in the same case. Any other source (precedent / footprint / device_runtime …) on a pending claim is refused — that shape is rewriting an expectation from an observation.";

function _renderContractAction(action: Record<string, any>, opts: { e_value: string; contract_sha256: string; prefix?: string; include_contract_sha?: boolean }): string[] {
  const prefix = opts.prefix ?? "";
  const includeContractSha = opts.include_contract_sha ?? true;
  const source = action.source;
  const lines = [
    `${prefix}action: ${action.name}`,
    `${prefix}canonical: ${action.canonical}`,
    `${prefix}equivalent_originals: ${pyJsonDumps(action.equivalent_originals, { ensure_ascii: false })}`,
    `${prefix}status: ${action.status}`,
    `${prefix}reason: ${action.reason}`,
    `${prefix}status_authority: ${action.status_authority}`,
    `${prefix}dispatcher: ${action.dispatcher}`,
    `${prefix}python_symbol: ${action.python_symbol}`,
    `${prefix}signature: ${action.signature.text}`,
    `${prefix}G: ${action.g_syntax}`,
    `${prefix}H: ${action.h_semantics}`,
    `${prefix}I: ${action.i_semantics}`,
    `${prefix}payload_schema: ${action.payload_schema}`,
    `${prefix}python_call_chain: runner -> getattr(${opts.e_value}, execute) -> ${action.dispatcher} registry[${JSON.stringify(action.normalized)}] -> ${action.python_symbol}`,
    `${prefix}source: ${source.path}:${source.line}`,
    `${prefix}minimum_runtime: ${action.minimum_runtime}`,
  ];
  if (includeContractSha) {
    lines.push(`${prefix}contract_sha256: ${opts.contract_sha256}`);
  }
  return lines;
}

function _executeEnabledEs(contract: any): string[] {
  return [...new Set<string>(contract.entries.filter((entry: any) => entry.f === "execute" && entry.status === "enabled").map((entry: any) => entry.e))].sort();
}

function _renderExecuteSurfaceSummary(contract: any, actions: Array<Record<string, any>>, opts: { e_value: string }): string[] {
  const enabled = actions.filter((action) => action.status === "enabled");
  const seats = _executeEnabledEs(contract);
  const lines = [`execute_actions (${actions.length}): ${enabled.length} enabled, ${actions.length - enabled.length} not enabled`];
  if (enabled.length === 0) {
    lines.push('enabled_actions (0): no action on this dispatcher is authorable today — the full list below still shows every action with its status, reason and authority, so you can tell "not certified yet" from "does not exist"');
    return lines;
  }
  let combinations = 0;
  let here = 0;
  lines.push(`enabled_actions (${enabled.length}):`);
  for (const action of enabled) {
    const allowed = [...new Set<string>(action.allowed_es)].filter((e) => seats.includes(e)).sort();
    combinations += allowed.length;
    if (allowed.includes(opts.e_value)) here += 1;
    lines.push(`  - ${action.name} — authorable on ${allowed.length ? allowed.join(", ") : "<no E seat with execute enabled>"} (${action.dispatcher} registry -> ${action.python_symbol})`);
  }
  lines.push(`authorable_on_${opts.e_value}: ${here} of these ${enabled.length} enabled action(s) can be written on ${opts.e_value} itself, whose execute row is ${seats.includes(opts.e_value) ? "enabled" : "not enabled"}.`);
  lines.push(`authorable_execute_surface: ${combinations} (action, E) combination(s) — a contract-wide count over every E, not a count for ${opts.e_value}. An action is authorable only where its own status is enabled AND that E's execute row is enabled; E values whose execute row is enabled: ${seats.length ? seats.join(", ") : "<none>"}. Everything else below is listed for diagnosis, not for authoring.`);
  return lines;
}

function _renderContractIndex(): string {
  const header = "=== lang_query(kind=contract) ===";
  let contract: any;
  try {
    contract = load_excel_contract();
  } catch (exc) {
    if (exc instanceof ExcelContractError) {
      return `error: contract query unavailable — ${exc.message}`;
    }
    throw exc;
  }
  const enabledMap = contract_enabled_fs_by_e(contract);
  const counts: Record<string, Record<string, number>> = {};
  const reasons: Record<string, Record<string, number>> = {};
  for (const entry of contract.entries) {
    const bucket = (counts[entry.e] ??= {});
    bucket[entry.status] = (bucket[entry.status] ?? 0) + 1;
    if (entry.status === "disabled") {
      const tally = (reasons[entry.e] ??= {});
      tally[entry.reason] = (tally[entry.reason] ?? 0) + 1;
    }
  }
  const objects = new Map(contract.objects.map((item: any) => [item.e, item]));
  const usable = Object.keys(enabledMap).filter((e) => enabledMap[e].size > 0).sort();
  const unusable = Object.keys(enabledMap).filter((e) => enabledMap[e].size === 0).sort();
  const lines = [
    header,
    `runtime: ${contract.runtime.minimum_version}`,
    `contract_sha256: ${contract.contract_sha256}`,
    `E values (${Object.keys(enabledMap).length}): ${usable.length} with an enabled function surface, ${unusable.length} with none`,
    "",
    `with an enabled surface (${usable.length}):`,
  ];
  for (const eValue of usable) {
    const names = [...enabledMap[eValue]].sort();
    lines.push(`  - ${eValue} (${names.length} enabled F): ${names.join(", ")}`);
  }
  lines.push("");
  lines.push(`with no enabled surface (${unusable.length}) — stated positively so you do not have to discover them by being rejected at emit:`);
  for (const eValue of unusable) {
    const bucket = counts[eValue] ?? {};
    const shape = Object.entries(bucket).sort().map(([status, count]) => `${count} ${status}`).join(", ") || "no F rows";
    const obj: Record<string, any> = objects.get(eValue) ?? {};
    lines.push(`  - ${eValue} (${shape}; object_status=${obj.status ?? "<unknown>"})`);
    const tally = Object.entries(reasons[eValue] ?? {}).sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1));
    for (const [reason, count] of tally.slice(0, 3)) {
      lines.push(`      disabled reason (${count} F): ${reason}`);
    }
    if (tally.length > 3) {
      lines.push(`      (+${tally.length - 3} further distinct reason(s); query this E directly for the full surface)`);
    }
  }
  lines.push("");
  lines.push("next: query kind=contract with domain=<one E> for that object's full enabled/disabled/internal F surface, then domain+name=<one F> for its signature, G/H/I semantics, dispatch and provenance.");
  return lines.join("\n");
}

function _renderContract(eValue: string, fValue = ""): string {
  const header = `=== lang_query(kind=contract, domain=${JSON.stringify(eValue)}, name=${JSON.stringify(fValue)}) ===`;
  let contract: any;
  try {
    contract = load_excel_contract();
  } catch (exc) {
    if (exc instanceof ExcelContractError) {
      return `error: contract query unavailable — ${exc.message}`;
    }
    throw exc;
  }
  const entries = contract.entries.filter((entry: any) => entry.e === eValue);
  if (entries.length === 0) {
    const known = contract.objects.map((item: any) => item.e).join(", ");
    const fRows = contract.entries.filter((entry: any) => entry.f === eValue).map((entry: any) => [String(entry.e), String(entry.status)] as [string, string]).sort();
    if (fRows.length) {
      const orientation = fRows.map(([owner, status]: [string, string]) => `  - E=${owner} (status=${status})`).join("\n");
      return `${header}\nnot found — unknown E value ${JSON.stringify(eValue)}; known E values: ${known}\norientation: ${JSON.stringify(eValue)} is an exact F value, not an E value. It occurs under:\n${orientation}\nnext: query one exact pair with domain=<the E shown above>, name=<this F>. This is contract navigation only; it does not decide whether the current case has enough evidence.`;
    }
    return `${header}\nnot found — unknown E value ${JSON.stringify(eValue)}; known E values: ${known}`;
  }
  if (fValue) {
    const entry = entries.find((e: any) => e.f === fValue) ?? null;
    if (entry === null) {
      const normalized = fValue.toLowerCase().replace(/\s+/g, "");
      const actionMatches = contract.execute_actions.filter((action: any) => action.allowed_es.includes(eValue) && action.normalized === normalized);
      if (actionMatches.length === 1) {
        return [header, ..._renderContractAction(actionMatches[0], { e_value: eValue, contract_sha256: contract.contract_sha256 })].join("\n");
      }
      return `${header}\nnot found — ${JSON.stringify(eValue)} has no F or exact execute action named ${JSON.stringify(fValue)}; query the same E without name to list its function surface`;
    }
    const signature = entry.signature;
    const source = entry.source;
    const lines = [
      header,
      `status: ${entry.status}`,
      `reason: ${entry.reason}`,
      `status_authority: ${entry.status_authority}`,
      `python_symbol: ${entry.python_symbol}`,
      `signature: ${signature.text}`,
      `G: ${entry.g_syntax}`,
      `H: ${entry.h_semantics}`,
      `I: ${entry.i_semantics}`,
      `dispatch: ${entry.dispatch}`,
      `source: ${source.path}:${source.line}`,
      `minimum_runtime: ${entry.minimum_runtime}`,
      `contract_sha256: ${contract.contract_sha256}`,
    ];
    if (entry.dispatch === "execute_registry") {
      const actions = contract.execute_actions.filter((action: any) => action.allowed_es.includes(eValue));
      lines.push(..._renderExecuteSurfaceSummary(contract, actions, { e_value: eValue }));
      for (const action of actions) {
        lines.push(..._renderContractAction(action, { e_value: eValue, contract_sha256: contract.contract_sha256, prefix: "  ", include_contract_sha: false }));
        lines.push("  ---");
      }
      lines.push("next: query name=<exact action name> for one action; disabled actions remain visible with their reason and authority. The contract_sha256 printed once above covers every action listed here.");
    }
    if (eValue === "check_point") {
      lines.push("");
      lines.push(_ASSERTION_IDENTITY_NOTE);
    }
    return lines.join("\n");
  }
  const objectInfo = contract.objects.find((item: any) => item.e === eValue);
  const lines = [
    header,
    `object_status: ${objectInfo.status}`,
    `object_reason: ${objectInfo.reason}`,
    `object_status_authority: ${objectInfo.status_authority}`,
    `runtime: ${contract.runtime.minimum_version}`,
    `contract_sha256: ${contract.contract_sha256}`,
  ];
  for (const status of ["enabled", "disabled", "internal"]) {
    const names = entries.filter((entry: any) => entry.status === status).map((entry: any) => entry.f).sort();
    lines.push(`${status} (${names.length}): ${names.length ? names.join(", ") : "<none>"}`);
  }
  lines.push("next: query this E with name=<one F> for signature, G/H/I semantics and provenance");
  if (eValue === "check_point") {
    lines.push("");
    lines.push(_ASSERTION_IDENTITY_NOTE);
  }
  return lines.join("\n");
}

function _renderSignature(name: string): string {
  let sig: Record<string, any> | null;
  try {
    sig = capability_signature(name);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) {
      return `error: signature query unavailable — ${exc.message}`;
    }
    throw exc;
  }
  const header = `=== lang_query(kind=signature, name=${JSON.stringify(name)}) ===`;
  if (sig === null) {
    return `${header}\nnot found — ${JSON.stringify(name)} is not a member of any apv_full mixin family (ssl_comm/seg_comm/ha_comm/preparation). This covers method-style F values only, not execute action names or cmd_config/cmds_config primitives — if ${JSON.stringify(name)} is an execute action name, it is not in this atlas at all: query lang_query(kind='contract', domain=<the E value you are writing>, name='execute') for that E's whole execute action surface (each action's status, payload schema and G/H/I grammar, enabled ones summarised first), or lang_query(kind='contract', domain=<E>, name=<exact action name>) for one action.`;
  }
  return `${header}\nrequired: ${sig.required}\noptional: ${sig.optional}\nsource: ${sig.source} (family: ${sig._family})`;
}

function _renderDispatchPoint(name: string): string {
  const header = `=== lang_query(kind=dispatch, name=${JSON.stringify(name)}) ===`;
  let kind: string | null;
  try {
    kind = dispatch_kind_of(name);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) {
      return `error: dispatch query unavailable — ${exc.message}`;
    }
    throw exc;
  }
  if (kind === null) {
    return `${header}\nnot found — ${JSON.stringify(name)} is not in the APV_0/1/2 apv_full dispatch surface (ssl_comm/seg_comm/ha_comm/preparation mixins, execute, or the cmd/cmds primitives). This kind only covers those E's; test_env/check_point/host-slot F names have no dispatch-kind ambiguity to query.`;
  }
  const lines = [header, `dispatch_kind: ${kind}`];
  const check = dispatch_kind_cross_check(name);
  if (check.stale) {
    lines.push(`note: the curated atlas snapshot disagrees (atlas says ${JSON.stringify(check.atlas)}, live reflection says ${JSON.stringify(kind)}) — this means the atlas needs regenerating (scripts/gen_capability_atlas.py), it does NOT mean you filled anything wrong. The value above (live) is authoritative regardless.`);
  }
  return lines.join("\n");
}

function _renderDispatchDomain(domain: string): string {
  const header = `=== lang_query(kind=dispatch, domain=${JSON.stringify(domain)}) ===`;
  let o: Record<string, any>;
  try {
    o = dispatch_domain_orientation(domain);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) {
      return `error: dispatch query unavailable — ${exc.message}`;
    }
    return `error: ${exc instanceof Error ? exc.message : String(exc)}`;
  }
  const lines = [header, `dispatch_kind: ${o.dispatch_kind} (constant across this domain's ${o.n} methods, stated once)`, `names (${o.n}): ${(o.names as string[]).join(", ")}`];
  if (o.disabled) {
    const disabled = Object.entries(o.disabled) as Array<[string, string]>;
    lines.push(`\n<disabled n=${disabled.length}>`);
    for (const [n, reason] of disabled) {
      lines.push(`  - ${n}: ${reason}`);
    }
    lines.push("</disabled>");
  }
  lines.push(`\ndisambiguation: ${o.disambiguation}`);
  lines.push("\nsignatures_omitted: true — this domain listing does not include per-method parameter signatures (they don't discriminate between similarly-named methods here any better than the names alone do). next: before writing the F column, query lang_query(kind='signature', name=<the method you picked>) to get its required/optional parameters — this step is not optional, guessing the parameter shape from the name is how silent-wrong F rows happen.");
  return lines.join("\n");
}

function _hostSlotPointer(name: string): string {
  let obs: Record<string, any>;
  try {
    obs = host_observation(name);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) return "";
    throw exc;
  }
  if (!obs.is_known_host) return "";
  return `\nnote: ${JSON.stringify(name)} is also a host slot this build declares. The corpus queried above holds only our own device-verified cases; what the vendor smoke-test suite ran on that machine is a separate record — query lang_query(kind='host', name=${JSON.stringify(name)}) for it.`;
}

function _renderUsage(name: string): string {
  const header = `=== lang_query(kind=usage, name=${JSON.stringify(name)}) ===`;
  let u: Record<string, any> | null;
  try {
    u = capability_usage_of(name);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) {
      return `error: usage query unavailable — ${exc.message}`;
    }
    throw exc;
  }
  if (u === null) {
    const corpusCount = Number(usage_index_corpus_meta().corpus_file_count ?? 0);
    const corpusLabel = corpusCount ? `the current ${corpusCount}-case device-verified mirror corpus` : "the current device-verified mirror corpus";
    const lines = [header, `0 hits across ${corpusLabel} — this does NOT mean the framework doesn't support ${JSON.stringify(name)}, only that no case in the corpus has used it yet. Treat this as "unproven by precedent", not "unsupported".`];
    for (const reason of Object.values(usage_index_empty_bucket_notes())) {
      lines.push(`\n(corpus-wide note: ${reason})`);
    }
    const pointer = _hostSlotPointer(name);
    if (pointer) lines.push(pointer);
    return lines.join("\n");
  }
  const lines = [header, `${u.count} real occurrence(s) in the corpus (bucket: ${u.bucket}), showing ${u.samples.length} representative sample(s) from ${Number(u.corpus_file_count ?? 0)} device-verified case(s):`];
  for (const s of u.samples) {
    lines.push(`\n<usage autoid="${s.autoid ?? ""}" desc="${s.desc ?? ""}">`);
    lines.push(String(s.g ?? ""));
    lines.push("</usage>");
  }
  if (u.count > u.samples.length) {
    lines.push(`\n(${u.count - u.samples.length} more not shown)`);
  }
  const pointer = _hostSlotPointer(name);
  if (pointer) lines.push(pointer);
  return lines.join("\n");
}

const _HOST_TOKENS_SHOWN = 40;
const _HOST_COMMANDS_SHOWN = 15;
const _HOST_COMMAND_RENDER_MAX = 300;
const _HOST_READING_NOTE = "reading: every line above is a record of something that was run in the past, on a bed addressed by this host slot. None of it states what that machine offers now — a service that answered then may be gone, and something never attempted may still work. Zero rows, for a host or for a first token, means no precedent was recorded, not that the action is unsupported. First tokens are taken mechanically as the first whitespace-separated word of the command cell; this tool does not classify them into services, ports or roles, and hands you no table that does.";

function _hostFirstTokenLines(tokens: Array<Record<string, any>>, label: string): string[] {
  const shown = tokens.slice(0, _HOST_TOKENS_SHOWN);
  const lines = [`${label} (${tokens.length} distinct first token(s), token — rows / distinct case files):`];
  for (const item of shown) {
    const token = String(item.token ?? "");
    lines.push(`  ${token || "<empty command cell>"} — ${item.rows} / ${item.distinct_files}`);
  }
  if (tokens.length > shown.length) {
    lines.push(`  (${tokens.length - shown.length} further first token(s) not printed here; this list is truncated, so a token's absence from these lines is not evidence it was never run)`);
  }
  return lines;
}

function _hostCommandBlock(entry: Record<string, any>): string[] {
  const command = String(entry.command ?? "");
  const storedCut = Number(entry.command_truncated_chars ?? 0);
  const renderCut = Math.max(0, command.length - _HOST_COMMAND_RENDER_MAX);
  const body = command.slice(0, _HOST_COMMAND_RENDER_MAX);
  const cut = storedCut + renderCut;
  const desc = String(entry.first_seen_desc ?? "").replace(/\n/g, " ").slice(0, 120);
  const lines = [
    `\n<observed first_token="${entry.first_token ?? ""}" f="${entry.f ?? ""}" rows="${entry.rows}" distinct_files="${entry.distinct_files}" file="${entry.first_seen_file ?? ""}" autoid="${entry.first_seen_autoid ?? ""}" desc="${desc}">`,
    body,
  ];
  if (cut) {
    lines.push(`[${cut} further character(s) of this command cut from the text above]`);
  }
  lines.push("</observed>");
  return lines;
}

function _renderHost(name: string, query = ""): string {
  const header = `=== lang_query(kind=host, name=${JSON.stringify(name)}, query=${JSON.stringify(query)}) ===`;
  let obs: Record<string, any>;
  try {
    obs = host_observation(name);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) {
      return `${header}\nerror: the usage projection could not be read — ${exc.message}. That is a missing projection on our side, NOT a statement about this machine.`;
    }
    throw exc;
  }
  const corpus = obs.corpus;
  const keySpace = obs.host_key_space as string[];
  const skipped = [...(corpus.vendor_unreadable_files ?? [])];
  const lines = [
    header,
    `projection: capability_usage_index.json — vendor corpus ${corpus.vendor_scanned_file_count} of ${corpus.vendor_corpus_file_count} case file(s) scanned (${skipped.length} skipped, named one by one in the projection's _meta.vendor_unreadable_files); authored corpus ${corpus.corpus_file_count} device-verified case(s).`,
    `host slots this build declares (${keySpace.length}, parsed from mirror ${(corpus.host_key_space_sources ?? []).join(", ")}): ${keySpace.length ? keySpace.join(", ") : "<none recorded>"}`,
  ];
  if (!obs.is_known_host) {
    lines.push(`\n${JSON.stringify(name)} is not one of those host slots, so nothing was looked up for it. Two readings stay open and this tool picks neither: the name may be misspelled, or this bed may address that machine some other way. Pick a slot from the list above, or query kind='docs' for the bed's topology assets.`);
    return lines.join("\n");
  }
  const vendor = obs.vendor;
  const q = (query ?? "").trim().toLowerCase();
  lines.push("");
  lines.push(`--- vendor corpus: what the vendor smoke-test suite ran on ${JSON.stringify(name)} ---`);
  if (!vendor) {
    lines.push(`0 row(s) recorded — no case in that corpus wrote a step against this host slot. Treat this as "unproven by precedent", not "unsupported": it does NOT mean ${JSON.stringify(name)} cannot run commands, only that the vendor corpus carries no example of anyone doing so.`);
  } else {
    const redacted = Number(vendor.redacted_rows ?? 0);
    lines.push(`${vendor.rows} step row(s) across ${vendor.distinct_files} case file(s); ${vendor.distinct_commands} distinct command text(s)` + (redacted ? `; ${redacted} row(s) redacted because their text carried a plaintext credential literal from the framework mirror (the rows are still counted, only their text is withheld)` : "") + ".");
    lines.push(..._hostFirstTokenLines([...(vendor.first_tokens ?? [])], "first tokens"));
    const commands = [...(vendor.commands ?? [])];
    const omitted = Number(vendor.commands_omitted ?? 0);
    if (q) {
      const matched = commands.filter((entry) => q.includes(String(entry.first_token ?? "").toLowerCase()) || String(entry.command ?? "").toLowerCase().includes(q));
      const shown = matched.slice(0, _HOST_COMMANDS_SHOWN);
      lines.push(`\nverbatim commands whose first token or text contains ${JSON.stringify(query)}: ${matched.length} of the ${commands.length} command text(s) this projection records for ${JSON.stringify(name)}, showing ${shown.length}. The search covers only those ${commands.length} recorded texts, not all ${vendor.distinct_commands} distinct ones (${omitted} were left out by the projection's per-token storage cap) — so zero matches here is not proof the string never appeared on this machine.`);
      for (const entry of shown) {
        lines.push(..._hostCommandBlock(entry));
      }
      if (matched.length > shown.length) {
        lines.push(`\n(${matched.length - shown.length} further match(es) not printed)`);
      }
    } else {
      const byToken = new Map<string, Record<string, any>>();
      for (const entry of commands) {
        const key = String(entry.first_token ?? "");
        if (!byToken.has(key)) byToken.set(key, entry);
      }
      const reps = [...byToken.values()].slice(0, _HOST_COMMANDS_SHOWN);
      lines.push(`\nverbatim commands — the highest-count example per first token, ${reps.length} of ${byToken.size} token(s) with a recorded text. The projection stores ${commands.length} of this host's ${vendor.distinct_commands} distinct command texts (${omitted} left out by the per-token storage cap); pass query=<substring> to search the recorded ones.`);
      for (const entry of reps) {
        lines.push(..._hostCommandBlock(entry));
      }
    }
  }
  const authored = obs.authored;
  lines.push("");
  lines.push(`--- authored corpus: what our own device-verified cases did on ${JSON.stringify(name)} (counts only) ---`);
  lines.push("No command text is carried for this column, by construction: these cases were written by this engine and have not been through the vendor suite's long-running use of this bed, so they are not precedent for what the machine tolerates. Counting them beside the vendor rows would blur who verified what.");
  if (!authored) {
    lines.push(`0 row(s) — none of our device-verified cases addressed ${JSON.stringify(name)}. Again: no precedent, not a limit.`);
  } else {
    lines.push(`${authored.rows} step row(s) across ${authored.distinct_files} case file(s).`);
    lines.push(..._hostFirstTokenLines([...(authored.first_tokens ?? [])], "first tokens"));
  }
  lines.push("");
  lines.push(_HOST_READING_NOTE);
  return lines.join("\n");
}

function _renderPromptPattern(name: string): string {
  const header = `=== lang_query(kind=prompt_pattern, name=${JSON.stringify(name)}) ===`;
  let entry: Record<string, any> | null;
  try {
    entry = confirmation_prompt_of(name);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) {
      return `error: prompt_pattern query unavailable — ${exc.message}`;
    }
    throw exc;
  }
  if (entry === null) {
    return `${header}\nnot found — ${JSON.stringify(name)} is not among the recorded confirmation-prompt sequences projected from the framework mirror (cert/CA and reboot confirmation methods, provenance redacted). This does NOT mean this method has no confirmation prompt — it means no precedent sequence for it is in this projection yet (the projection's scope is currently lib/ only). If you suspect it does trigger one, the framework-wide pattern is: the triggering command must be sent with an anchor (\`,prompt=<expected-text>\`, not the default prompt), then each response step waits for its own anchor in turn — retrieve the actual anchor values from the version manual, not by guessing a generic ':'.`;
  }
  const steps = entry.steps as Array<Record<string, any>>;
  const stepsRepr = steps.map((s) => `${JSON.stringify(s.send)} -> wait_for ${JSON.stringify(s.wait_for)}`).join("; ");
  const lines = [header, `trigger_command: ${entry.trigger_command}`, `steps (${steps.length}): ${stepsRepr}`, `anchor_values_used: ${entry.anchor_values_used}`];
  const fsna = entry.final_step_no_anchor;
  if (fsna === "no_anchor") {
    lines.push(`final_step_no_anchor: no_anchor — after the steps above, send ${JSON.stringify(entry.final_step_value)} with NO anchor (returns to the default prompt)`);
  } else if (fsna === "has_anchor") {
    lines.push(`final_step_no_anchor: has_anchor — ${entry.final_step_note}`);
  } else {
    lines.push(`final_step_no_anchor: not_observed — ${entry.final_step_note}`);
  }
  const p = entry.provenance;
  lines.push(`source: ${p.file}:${p.def_line} (${p.function})`);
  return lines.join("\n");
}

function _renderNearest(name: string, domain: string): string {
  const header = `=== lang_query(kind=nearest, name=${JSON.stringify(name)}) ===`;
  let pool: Iterable<any>;
  if (domain) {
    try {
      pool = dispatch_domain_orientation(domain).names;
    } catch (exc) {
      return `error: ${exc instanceof Error ? exc.message : String(exc)}`;
    }
  } else {
    pool = apv_full_fs();
    if ([...(pool as Set<string>)].length === 0) {
      return "error: nearest query unavailable — mirror unreachable, apv_full_fs() is empty";
    }
  }
  const ranked = nearest_candidates(name, pool, { top_n: 5 });
  return `${header}\nnearest candidates (ranked by similarity, for reference only — confirm deliberately, this never auto-rewrites): ${ranked.join(", ")}`;
}

function _valueDomainLines(argument: any, opts: { manual_version?: string } = {}): string[] {
  const manualVersion = opts.manual_version ?? "";
  if (typeof argument !== "object" || argument === null || Array.isArray(argument)) return [];
  if (String(argument.type ?? "") === "REDACTED_SENSITIVE" && argument.executable === false) {
    return ["    value domain: not applicable — this position holds a credential-class literal, so the projection redacts it and the rule rejects any value here with `sensitive_parameter_unexecutable`, whatever you write"];
  }
  const domain = argument.value_domain;
  if (typeof domain !== "object" || domain === null || Array.isArray(domain) || Object.keys(domain).length === 0) {
    return ["    value domain: not recorded for this position — the rule checks it on type/arity only; that is a gap in our projection, NOT a statement that the device accepts anything here"];
  }
  const { display_manual_locator, parse_adoc_style_src } = require("../../../kms/manual_locator");
  const lines = ["    value domain (claims listed side by side; no source wins):"];
  let rejecting = false;
  for (const kind of ["enum", "union", "range", "length", "default"]) {
    for (const claim of domain[kind] ?? []) {
      if (typeof claim !== "object" || claim === null) continue;
      const source = String(claim.source ?? "");
      let body: string;
      if (kind === "enum") {
        body = "one of " + (claim.values ?? []).map((item: any) => JSON.stringify(String(item))).join(", ");
      } else if (kind === "union") {
        const separator = String(claim.separator ?? "");
        body = `two or more of the listed members joined by ${JSON.stringify(separator)} are also accepted here`;
      } else if (kind === "default") {
        body = `documented default ${JSON.stringify(String(claim.value))}`;
      } else {
        body = `${kind} ${claim.min}..${claim.max}`;
      }
      let note: string;
      if (kind === "union") {
        note = " (composition syntax stated verbatim in the XML help; the rule splits on it before rejecting)";
      } else if (kind === "length" || kind === "default") {
        note = " (supply only, not a rejection rule)";
      } else if (kind === "enum" && source === "xml_help") {
        note = " (accept-only: XML help lists these as legal, which does not prove the set is closed, so the rule never rejects on it)";
      } else {
        note = "";
        rejecting = true;
      }
      const rawLocator = String(claim.locator ?? "");
      let shownLocator: string;
      if (source === "manual_table" && manualVersion && parse_adoc_style_src(rawLocator)) {
        shownLocator = display_manual_locator(rawLocator, manualVersion);
      } else {
        shownLocator = rawLocator;
      }
      lines.push(`      ${body}${note} — source: ${source}, locator: ${shownLocator}`);
    }
  }
  if (!rejecting) {
    lines.push("      no claim on this position can carry a rejection — the rule still checks it on type/arity only");
  }
  return lines;
}

function _tokenPermutationFactLines(name: string): string[] {
  const { recorded_heads_with_token_permutation } = require("../../../case_compiler/vendor_stdlib");
  const hits: string[] = recorded_heads_with_token_permutation(name);
  if (!hits.length) return [];
  return [`${hits.length} recorded head(s) use the same words as ${JSON.stringify(name)} in a different order (or with at most one extra token). Verbatim from this build's tree, never auto-applied. This list is not a recommendation:`, ...hits.map((head) => `  * ${head}`)];
}

const _PERMUTATION_NEXT_PARAM = "next: lang_query(kind='param', name=<one of these heads>) for that head's argument contract.";
const _PERMUTATION_NEXT_COMPLETE = "next: lang_query(kind='param', name=<one of these heads>) for that head's per-argument XML contract side by side with the manual's explanation.";

function _permutationFactBlock(name: string, nextLine: string): string[] {
  const permutation = _tokenPermutationFactLines(name);
  return permutation.length ? [...permutation, nextLine] : [];
}

function _nextTokenFactLines(name: string, opts: { truncated: boolean }): string[] {
  const { norm_command_tokens, recorded_next_tokens_after_shared_prefix } = require("../../../case_compiler/vendor_stdlib");
  const fact = recorded_next_tokens_after_shared_prefix(name);
  if (!fact) return [];
  const query = norm_command_tokens(name);
  const extraUnmatched = fact.shared_tokens < query.length;
  if (!opts.truncated && !extraUnmatched) return [];
  const shown = [...fact.tokens];
  const total = Number(fact.total);
  const lines = [`next-token fact from the same projection: ${total} recorded token(s) appear at word ${fact.position} after ${JSON.stringify(fact.prefix)}. Verbatim inventory of this build's tree, never auto-applied, not a ranking:`, ...shown.map((tok: string) => `  * ${tok}`)];
  if (total > shown.length) {
    lines.push(`${total - shown.length} further recorded token(s) at that position are NOT listed.`);
  }
  return lines;
}

function _renderParam(name: string, position: number | null = null): string {
  const { manual_source_dir } = require("../../../case_compiler/vendor_stdlib");
  const lines = [`=== lang_query(kind=param, name=${JSON.stringify(name)}) ===`];
  const contract = param_contract_of(name, position);
  const manualRoot = manual_source_dir();
  const manualVersion = manualRoot !== null ? path.basename(String(manualRoot)) : "";
  if (contract === null) {
    lines.push("XML: loaded command tree has no matching head for this name — capability unknown for this lookup, not a device rejection");
    lines.push(..._permutationFactBlock(name, _PERMUTATION_NEXT_PARAM));
  } else if (contract.status === PARAM_CONTRACT_UNAVAILABLE) {
    const reason = String(contract.reason ?? "command-tree projection could not be loaded");
    lines.push(`XML: ${reason} — this is a missing projection on our side, not a statement that the command is absent and not a statement that it is present`);
    lines.push(..._permutationFactBlock(name, _PERMUTATION_NEXT_PARAM));
  } else {
    lines.push(`XML (version ${contract.version}, build ${contract.device_os_build}, head: ${contract.head}):`);
    if (!contract.args.length) {
      lines.push("  (no parameters declared)");
    }
    for (const item of contract.args) {
      const mark = contract.selected === item ? "  <-- selected" : "";
      lines.push(`  position ${item.position}: ${item.type}${item.optional ? ", optional" : ""} — help: ${JSON.stringify(item.help)}${mark}`);
      lines.push(..._valueDomainLines(item, { manual_version: manualVersion }));
    }
    if (position !== null && contract.selected === null) {
      lines.push(`  position ${position}: no entry at this position`);
    }
  }
  const excerpt = manual_param_excerpt(name);
  if (excerpt.hit) {
    for (const section of excerpt.sections) {
      const note = section.has_parameter_table ? "" : " (section has no parameter table)";
      const filename = path.basename(String(section.file));
      let locator: string;
      if (manualVersion && filename) {
        locator = `${manualVersion}/${filename}:${section.line}`;
      } else {
        locator = `${section.file}:${section.line}`;
      }
      lines.push(`manual:${locator}${note}`);
      lines.push(section.text);
    }
  } else if (excerpt.note === MANUAL_SOURCE_UNAVAILABLE) {
    lines.push(`manual: ${MANUAL_SOURCE_UNAVAILABLE} — the manual root comes from the command tree projection and the projection is not loadable; this is a supply failure, not evidence that the manual lacks this command`);
  } else {
    lines.push(`manual: ${NOT_DIRECTLY_HIT}`);
  }
  return lines.join("\n");
}

export const COMPLETE_PROJECTION_UNAVAILABLE_MARK = "could not be loaded, so no completion can be offered";

function _renderComplete(name: string): string {
  const { load_vendor_stdlib, norm_command_tokens, rank_vendor_command_completions } = require("../../../case_compiler/vendor_stdlib");
  const header = `=== lang_query(kind=complete, name=${JSON.stringify(name)}) ===`;
  const inventory = load_vendor_stdlib();
  if (inventory === null) {
    return `${header}\ncapability unknown — the vendor command-tree projection for this device build ${COMPLETE_PROJECTION_UNAVAILABLE_MARK}. That is a missing projection on our side, NOT a statement about whether the command exists on the device.`;
  }
  const identity = `projection: version ${inventory.version ?? ""}, build ${inventory.device_os_build ?? ""}, ${Object.keys(inventory.heads ?? {}).length} recorded command heads`;
  const ranked = rank_vendor_command_completions(name);
  if (!ranked.length) {
    const lines = [header, identity, `0 recorded heads share a leading token with ${JSON.stringify(name)}. Two readings stay open and this tool does not pick one: the first word may be misspelled, or this command family may genuinely not be in this build's tree. Nothing is rewritten for you.`];
    lines.push(..._permutationFactBlock(name, _PERMUTATION_NEXT_COMPLETE));
    return lines.join("\n");
  }
  const shown = ranked.slice(0, _COMPLETE_SHOWN_K);
  const continuing = ranked.filter((candidate: any) => candidate.prefix_continuation).length;
  const lines = [header, identity, `${ranked.length} recorded head(s) line up with ${JSON.stringify(name)} — each shares at least one whole leading token with it, or continues one of your tokens as a prefix. In ${continuing} of them the recorded token at the first position that did not match as a whole word starts with your token there; when the word you left half-typed is your last one, that is the completion you are after. Showing the ${shown.length} highest-ranked, verbatim from the projection, never auto-applied. Ranking: most whole leading tokens shared first, then heads whose next recorded token starts with your token at that position, then the shortest head:`, ...shown.map((candidate: any) => `  - ${candidate.head}`)];
  if (ranked.length > shown.length) {
    lines.push(`${ranked.length - shown.length} further recorded candidate(s) exist and are NOT listed above — this list is truncated, so its absence from these lines is not evidence that a head is missing from the build. Type more of the head into name= to narrow the ranking.`);
  }
  const queryTokens = norm_command_tokens(name);
  if (queryTokens.length && continuing === 0) {
    const topShared = Math.max(...ranked.map((candidate: any) => candidate.shared_tokens));
    const tiedAtTop = ranked.filter((candidate: any) => candidate.shared_tokens === topShared).length;
    const headers = inventory.headers ?? {};
    const longestPrefixIsRecordedHead = queryTokens.some((_t: string, k0: number) => {
      const k = queryTokens.length - k0;
      return k >= 1 && k <= queryTokens.length - 1 && queryTokens.slice(0, k).join(" ") in headers;
    });
    if (topShared < queryTokens.length && tiedAtTop > _COMPLETE_SHOWN_K && !longestPrefixIsRecordedHead) {
      const { recorded_command_heads } = require("../worker_device_context");
      for (let k = queryTokens.length - 1; k >= 1; k--) {
        const parentHeads = recorded_command_heads(inventory, queryTokens.slice(0, k).join(" "));
        if (parentHeads.length) {
          const position = k + 1;
          lines.push(`heads fact from the same projection: ${parentHeads.length} recorded head(s) begin with ${JSON.stringify(queryTokens.slice(0, k).join(" "))}, and 0 begin with ${JSON.stringify(queryTokens.slice(0, position).join(" "))} — query word ${position}, ${JSON.stringify(queryTokens[k])}, has no recorded head at that position in this build's vendor XML command tree.`);
          break;
        }
      }
    }
  }
  lines.push(..._nextTokenFactLines(name, { truncated: ranked.length > shown.length }));
  lines.push(..._tokenPermutationFactLines(name));
  lines.push(_PERMUTATION_NEXT_COMPLETE);
  return lines.join("\n");
}

export function command_heads_result(module_prefix: string): CommandHeadsQueryResult {
  const prefix = String(module_prefix ?? "").split(/\s+/).filter((s) => s).join(" ").toLowerCase();
  const base: CommandHeadsQueryResult = { schema: COMMAND_HEADS_QUERY_SCHEMA, status: "worker_session_unavailable", module_prefix: prefix, device_build: "", capability_generation_id: "", capability_manifest_sha256: "", projection_version: "", count: 0, heads: [], receipt_id: "", result_sha256: "" };
  let session: any = null;
  try {
    const { current_worker_device_session } = require("../worker_device_context");
    session = current_worker_device_session();
  } catch {
    session = null;
  }
  if (session === null || session === undefined) return base;
  const deviceBuild = String(session.capability_build ?? "").trim();
  base.device_build = deviceBuild;
  base.capability_generation_id = String(session.capability_generation_id ?? "").trim();
  base.capability_manifest_sha256 = String(session.capability_manifest_sha256 ?? "").trim().toLowerCase();
  if (!deviceBuild) {
    base.status = "capability_build_missing";
    return base;
  }
  const { load_vendor_stdlib } = require("../../../case_compiler/vendor_stdlib");
  const inventory = load_vendor_stdlib("", deviceBuild);
  if (inventory === null) {
    base.status = "command_tree_unavailable";
    return base;
  }
  const inventoryBuild = String(inventory.device_os_build ?? "").trim();
  if (inventoryBuild && inventoryBuild !== deviceBuild) {
    base.status = "capability_identity_mismatch";
    return base;
  }
  const { recorded_command_heads } = require("../worker_device_context");
  const heads: string[] = recorded_command_heads(inventory, prefix);
  const result: CommandHeadsQueryResult = { ...base, status: "complete", device_build: deviceBuild, projection_version: String(inventory.version ?? ""), count: heads.length, heads };
  const budgetCandidate = { ...result, receipt_id: "r".repeat(256), result_sha256: "0".repeat(64) };
  const sortedJson = (v: any): any => {
    if (Array.isArray(v)) return v.map(sortedJson);
    if (typeof v === "object" && v !== null) {
      const out: Record<string, any> = {};
      for (const k of Object.keys(v).sort()) out[k] = sortedJson(v[k]);
      return out;
    }
    return v;
  };
  if (Buffer.byteLength(JSON.stringify(sortedJson(budgetCandidate)), "utf8") > _MAX_HEADS_RESULT_BYTES) {
    return { ...base, status: "result_too_large", projection_version: String(inventory.version ?? ""), count: heads.length };
  }
  const [receipt, receiptError] = session.record_command_heads_query(result);
  if (receiptError) {
    result.status = "receipt_unavailable";
    return result;
  }
  return { ...result, receipt_id: String(receipt.receipt_id ?? ""), result_sha256: String(receipt.result_sha256 ?? "") };
}

function _renderHeads(modulePrefix: string): string {
  const result = command_heads_result(modulePrefix);
  const header = `=== lang_query(kind=heads, name=${JSON.stringify(modulePrefix)}) ===`;
  if (result.status !== "complete") {
    if (result.status === "result_too_large") {
      return [header, `schema: ${result.schema}`, `status: ${result.status}`, `module: ${result.module_prefix}`, `device_build: ${result.device_build}`, `recorded_heads: ${result.count}`, `[${result.count} truncated]`, "error: the complete inventory exceeds the tool-result byte limit; zero heads are shown and no completeness receipt was minted. name= accepts a multi-token prefix: tokens are matched as whole words from the left, so a longer prefix narrows the listing to only the heads that begin with it. Use kind='complete' with a longer command prefix to inspect a bounded candidate list, but do not treat that list as proof that the module has no equivalent command."].join("\n");
    }
    return `error: ${result.status} — schema=${result.schema} module=${JSON.stringify(result.module_prefix)} device_build=${JSON.stringify(result.device_build)}`;
  }
  const lines = [header, `schema: ${result.schema}`, `module: ${result.module_prefix}`, `projection_version: ${result.projection_version}`, `device_build: ${result.device_build}`, `capability_generation_id: ${result.capability_generation_id}`, `capability_manifest_sha256: ${result.capability_manifest_sha256}`, `receipt_id: ${result.receipt_id}`, `result_sha256: ${result.result_sha256}`, `recorded_heads: ${result.count}`, ...result.heads.map((head) => `  - ${head}`)];
  if (result.count === 0) {
    lines.push("note: zero recorded heads begin with this prefix in this build's vendor XML command tree. name= accepts a multi-token prefix — tokens are matched as whole words from the left, so a longer prefix narrows the list and a shorter one widens it.");
  }
  return lines.join("\n");
}

function _renderDocs(query: string): string {
  const header = `=== lang_query(kind=docs, query=${JSON.stringify(query)}) ===`;
  let catalog: Record<string, any>;
  try {
    catalog = language_document_catalog(query);
  } catch (exc) {
    if (exc instanceof QueryUnavailable) {
      return `error: language docs query unavailable — ${exc.message}`;
    }
    throw exc;
  }
  const matches = catalog.matches as Array<Record<string, any>>;
  if (!matches.length) {
    return `${header}\n0 indexed language assets matched`;
  }
  const lines = [header, `matches: ${matches.length}`];
  for (const entry of matches) {
    const details: string[] = [];
    for (const key of ["status", "record_count", "device_os_build"]) {
      if (entry[key] !== null && entry[key] !== undefined && entry[key] !== "") {
        details.push(`${key}=${entry[key]}`);
      }
    }
    const suffix = details.length ? ` (${details.join(", ")})` : "";
    lines.push(`- ${entry.id ?? ""}: ${entry.path ?? ""}${suffix}`);
    if (entry.symbols) {
      lines.push(`  symbols: ${(entry.symbols as string[]).join(", ")}`);
    }
    if (entry.sections) {
      lines.push(`  sections: ${(entry.sections as string[]).join(", ")}`);
    }
  }
  return lines.join("\n");
}

function _withRecomposeGrounding(render: () => string, opts: { kind: string; name: string; domain: string; query: string; position: number; scope_refusal_reason?: string }): string {
  const { resolve_recompose_command_grounding } = require("./recompose_submission");
  const [result, receipt] = resolve_recompose_command_grounding(render, { kind: opts.kind, name: opts.name, domain: opts.domain, query: opts.query, position: opts.position, scope_refusal_reason: opts.scope_refusal_reason ?? "" });
  if (receipt === null || receipt === undefined) {
    return result;
  }
  return `${result}\ngrounding_receipt: ${receipt}`;
}

export function lang_query(kind: string, name = "", domain = "", query = "", position = 0): string {
  const k = (kind ?? "").trim().toLowerCase();
  if (!(_KINDS as readonly string[]).includes(k)) {
    return `error: kind must be one of ${_KINDS.join("/")}, got ${JSON.stringify(kind)}`;
  }
  name = (name ?? "").trim();
  const domainRaw = (domain ?? "").trim();
  const domainLower = domainRaw.toLowerCase();
  if (k === "contract") {
    if (!domainRaw) return _renderContractIndex();
    return _renderContract(domainRaw, name);
  }
  if (k === "signature") {
    if (!name) return "error: kind='signature' requires name";
    return _renderSignature(name);
  }
  if (k === "dispatch") {
    if (!name === !domainLower) return "error: kind='dispatch' requires exactly one of name or domain, not both/neither";
    return domainLower ? _renderDispatchDomain(domainLower) : _renderDispatchPoint(name);
  }
  if (k === "usage") {
    if (!name) return "error: kind='usage' requires name";
    return _renderUsage(name);
  }
  if (k === "host") {
    if (!name) return "error: kind='host' requires name (one host slot)";
    return _renderHost(name, query);
  }
  if (k === "prompt_pattern") {
    if (!name) return "error: kind='prompt_pattern' requires name";
    return _renderPromptPattern(name);
  }
  if (k === "docs") {
    return _renderDocs(query || name);
  }
  if (k === "param") {
    if (!name) return "error: kind='param' requires name (the device CLI command head)";
    return _withRecomposeGrounding(() => _renderParam(name, position ? position : null), { kind: k, name, domain: domainRaw, query, position });
  }
  if (k === "complete") {
    if (!name) return "error: kind='complete' requires name (a command head or its prefix)";
    return _withRecomposeGrounding(() => _renderComplete(name), { kind: k, name, domain: domainRaw, query, position });
  }
  if (k === "heads") {
    if (!name) return "error: kind='heads' requires name (a command module prefix)";
    const { RECOMPOSE_HEADS_SCOPE_REFUSAL, RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT, in_recompose_dispatch_scope } = require("./recompose_submission");
    if (in_recompose_dispatch_scope()) {
      return _withRecomposeGrounding(() => RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT, { kind: k, name, domain: domainRaw, query, position, scope_refusal_reason: RECOMPOSE_HEADS_SCOPE_REFUSAL });
    }
    return _withRecomposeGrounding(() => _renderHeads(name), { kind: k, name, domain: domainRaw, query, position });
  }
  if (!name) return "error: kind='nearest' requires name";
  return _renderNearest(name, domainLower);
}

export const compile_query = lang_query;
