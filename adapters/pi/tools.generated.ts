// 由 tools/gen_adapters.py 从 cex_client/tool_specs.json 生成，不在这里手改（--check 查漂移）。
import { StringEnum } from "@mariozechner/pi-ai";
import { type TSchema, Type } from "typebox";

export interface CexToolSpec {
	name: string;
	label: string;
	description: string;
	snippet: string;
	readOnly: boolean;
	parameters: TSchema;
}

export const CEX_TOOLS: CexToolSpec[] = [
	{
		name: "cex_init",
		label: "CEX init",
		description: "Create or update the compile-excel workspace in a project folder. Stores the server URL and device build in <folder>/.compile-excel/config.json. Run once per folder before logging in. Pointing an existing workspace at another server drops the old session, the cached organisation config and any bed lease.",
		snippet: "Create or update the compile-excel workspace in a project folder.",
		readOnly: false,
		parameters: Type.Object({
			"server": Type.String({"description": "compile-excel-server base URL (https, or http on loopback)."}),
			"device_build": Type.String({"description": "Execution build identifier the bundles are published under."}),
			"workspace": Type.Optional(Type.String({"description": "Folder to initialise; defaults to the current directory."})),
			"channel": Type.Optional(StringEnum(["stable", "candidate"] as const, {"description": "Bundle channel to sync; defaults to stable."})),
			"insecure_lan": Type.Optional(Type.Boolean({"description": "Allow plain http to a non-loopback server on a trusted lab network."})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_status",
		label: "CEX status",
		description: "Report the workspace state: server, device build, whether the user is logged in, and which bundle is synced.",
		snippet: "Report the workspace state: server, device build, whether the user is logged in, and which bundle is synced.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_login_start",
		label: "CEX login start",
		description: "Start the OAuth device login. Returns a URL and a user code; show both to the user, who signs in with their username and access code in a browser. Then call cex_login_wait. The login asks for every permission the tools use (including jumphost:admin for cex_init_device); the server grants only those the account holds.",
		snippet: "Start the OAuth device login.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_login_wait",
		label: "CEX login wait",
		description: "Wait for the user to approve the device login started by cex_login_start. Returns pending if they have not approved within timeout_s; call again in that case.",
		snippet: "Wait for the user to approve the device login started by cex_login_start.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"timeout_s": Type.Optional(Type.Number({"description": "Seconds to wait in this call (1-300, default 60)."})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_logout",
		label: "CEX logout",
		description: "Revoke the workspace session on the server and delete the local token.",
		snippet: "Revoke the workspace session on the server and delete the local token.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_sync",
		label: "CEX sync",
		description: "Download the compile data bundle for the workspace's device build into .compile-excel/bundle/<build>/, verifying every file against the manifest SHA-256. Falls back to a verified local cache when the server is unreachable and says so.",
		snippet: "Download the compile data bundle for the workspace's device build into .compile-excel/bundle/<build>/, verifying every file against the manifest SHA-256.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"channel": Type.Optional(StringEnum(["stable", "candidate"] as const)),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_client_config",
		label: "CEX client config",
		description: "Fetch the organisation constants published by the server (portal, defect tracker and gateway addresses) and cache them in the workspace. The gateway address is taken only from this cache, so call it again after switching servers.",
		snippet: "Fetch the organisation constants published by the server (portal, defect tracker and gateway addresses) and cache them in the workspace.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_docs_query",
		label: "CEX docs query",
		description: "Search verified manuals for the current build's bound manual version and, when available, server documents. Local manual matches come first with manual:<path>:<line> citations; server documents are marked separately and have no manual citation. Limit applies to each source independently, so online results can contain up to twice the limit. Offline results state that server documents were not searched. If neither source is available, reports a supply failure.",
		snippet: "Search verified manuals for the current build's bound manual version and, when available, server documents.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"q": Type.String({"description": "Search terms."}),
			"limit": Type.Optional(Type.Integer({"description": "Maximum results per source (1–10, default 3); online results can contain up to twice this number.", "minimum": 1, "maximum": 10})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_cmd_check",
		label: "CEX cmd check",
		description: "Check device commands against the synced command-tree projection: whether each command exists on this build and whether its parameters fit the recorded contract. This is the same judgment the engine uses; a miss means the command will not run on the device. Each result carries the resolved head and its command-tree path (src). At most 200 commands per call; a longer list is refused (not truncated), so split it.",
		snippet: "Check device commands against the synced command-tree projection: whether each command exists on this build and whether its parameters fit the recorded contract.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"commands": Type.Array(Type.String(), {"maxItems": 200}),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_scan_destructive",
		label: "CEX scan destructive",
		description: "Scan a compiled case workbook for device-wide destructive commands (whole-config wipes, factory restore, reboot/shutdown) with the rules from the synced domain grammar. Every row is scanned, including those after the 999999999999999 pseudo case; formula cells are findings (the framework runs their cached values); a finding may carry executed, the string the framework actually sends. Any finding means the workbook must not run on a shared bed.",
		snippet: "Scan a compiled case workbook for device-wide destructive commands (whole-config wipes, factory restore, reboot/shutdown) with the rules from the synced domain grammar.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"xlsx": Type.String({"description": "Workbook path inside the workspace."}),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_bed_lease",
		label: "CEX bed lease",
		description: "Manage your lease on the test bed through the jumphost gateway. acquire before any device work, heartbeat during long sessions, release when done, status to see who holds it. The lease (including its fencing token, which is never shown) is kept in the workspace; other device tools use it automatically.",
		snippet: "Manage your lease on the test bed through the jumphost gateway.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"action": StringEnum(["acquire", "heartbeat", "release", "status"] as const),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_env_prepare",
		label: "CEX env prepare",
		description: "Check the bed before running cases: framework present, devices reachable, device build matches the bundle build, safety rules available. Sends the workspace's device build so the gateway checks the device against it. Needs the lease.",
		snippet: "Check the bed before running cases: framework present, devices reachable, device build matches the bundle build, safety rules available.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_case_submit",
		label: "CEX case submit",
		description: "Submit a compiled workbook from the workspace to run on the bed. The gateway re-checks it (Excel contract, destructive commands, credential literals) and refuses on any finding. Returns task_id. Needs the lease.",
		snippet: "Submit a compiled workbook from the workspace to run on the bed.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"xlsx": Type.String({"description": "Workbook path inside the workspace."}),
			"module": Type.Optional(Type.String({"description": "Staging module; default is the gateway's."})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_case_status",
		label: "CEX case status",
		description: "State of a submitted run (running, done or lost) with the tail of its log. lost means the runner died without recording an end (gateway restart, OOM, operator kill): that run has no verdicts; resubmit the workbook.",
		snippet: "State of a submitted run (running, done or lost) with the tail of its log.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"task_id": Type.String(),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_case_results",
		label: "CEX case results",
		description: "Per-case framework verdicts of a finished run. Writes run_results.json and run_receipt.md next to the workbook, but only for the latest submission of that workbook: results of an older run are returned with receipt null and a note, and the receipt is left alone. Logs from earlier runs are marked and not used as evidence. A pass or fail counts only when the case's own log ends with the framework's closing (PASS/FAIL banner, then end case); otherwise the case is broken (the run stopped inside it and the result row is a placeholder). A pass whose log shows an execution failure its assertions were not waiting for is broken too. Non-pass cases come with their device and trigger-host session dumps saved under evidence/<task_id>/<autoid>/.",
		snippet: "Per-case framework verdicts of a finished run.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"task_id": Type.String(),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_probe_show",
		label: "CEX probe show",
		description: "Run one read-only show/get command on a bed device and return the output. Needs the lease.",
		snippet: "Run one read-only show/get command on a bed device and return the output.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"command": Type.String(),
			"device_index": Type.Optional(Type.Integer({"minimum": 0})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_init_device",
		label: "CEX init device",
		description: "Wipe and re-baseline bed devices over the serial console (needs jumphost:admin). step=prepare returns the exact plan and a one-time confirmation code; show the plan to the user and call step=confirm with the code only after they approve.",
		snippet: "Wipe and re-baseline bed devices over the serial console (needs jumphost:admin).",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"step": StringEnum(["prepare", "confirm"] as const),
			"device_index": Type.Optional(Type.Integer({"minimum": 0})),
			"device_count": Type.Optional(Type.Integer({"minimum": 1})),
			"confirmation": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_portal_login_start",
		label: "CEX portal login start",
		description: "Start a QR-code login to the company portal (needed before cex_bug_get). Saves the QR image to a private file and returns its path; ask the user to open it and scan it with the company app, then call cex_portal_login_wait. No password is ever asked for or stored.",
		snippet: "Start a QR-code login to the company portal (needed before cex_bug_get).",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_portal_login_wait",
		label: "CEX portal login wait",
		description: "Wait for the user to finish scanning the portal QR code. Returns pending if not yet scanned; call again in that case.",
		snippet: "Wait for the user to finish scanning the portal QR code.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"timeout_s": Type.Optional(Type.Number()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_portal_logout",
		label: "CEX portal logout",
		description: "Forget the portal session stored on this machine.",
		snippet: "Forget the portal session stored on this machine.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_bug_get",
		label: "CEX bug get",
		description: "Fetch one defect ticket through the portal session with the user's own permissions, parse it and save the scrubbed result under defects/ in the workspace. Only ticket detail pages of the configured trackers are fetched. If the session expired, run the portal QR login again.",
		snippet: "Fetch one defect ticket through the portal session with the user's own permissions, parse it and save the scrubbed result under defects/ in the workspace.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"backend": StringEnum(["bugzilla", "zentao", "zentao_story"] as const),
			"ticket": Type.String({"description": "Ticket id, e.g. 12345, BUG-12345 or STORY-7."}),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_recompose_prepare",
		label: "CEX recompose prepare",
		description: "Start recomposing a human mindmap (XMind JSON export inside the workspace) into a machine mindmap. Seals a snapshot, locates the governing spec in the synced spec generation, and opens a submission. Returns the case autoids, the governing spec (bound: a file path you can read; ambiguous: reference slices with zero signing power; no_governing_spec), the defect-spec status, and consistency_source_atoms. Pass spec=<file> when the user names the governing spec, or spec='none' when the user says no spec governs it. Calling it again for the same mindmap and the same spec outcome resumes: already recorded cases are listed. Without out_name the batch is named after the file (reduced to a safe name when the file name has spaces or non-ASCII characters; the result says which).",
		snippet: "Start recomposing a human mindmap (XMind JSON export inside the workspace) into a machine mindmap.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"mindmap": Type.String({"description": "Path of the XMind JSON export, relative to the workspace."}),
			"out_name": Type.Optional(Type.String({"description": "Batch name for the outputs; defaults to a safe name derived from the file name."})),
			"spec": Type.Optional(Type.String({"description": "Governing spec file name the user named, or 'none' when the user says no spec governs it."})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_recompose_submit_cases",
		label: "CEX recompose submit cases",
		description: "Record finished machine-mindmap cases for a prepared batch. The engine's checks run here (verbatim sourcing, anchors, consistency citations); a rejection lists the violations and records nothing, so fix those cases and submit again. Record cases as you finish them; resubmitting an autoid replaces it. Returns outstanding_autoids.",
		snippet: "Record finished machine-mindmap cases for a prepared batch.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"out_name": Type.String(),
			"cases": Type.Array(Type.Record(Type.String(), Type.Unknown()), {"description": "Machine-mindmap case objects (autoid, contract, origin, …)."}),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_recompose_seal",
		label: "CEX recompose seal",
		description: "Seal the recorded cases of a batch into machine_mindmap.json. Cases never recorded fall back to the author's original text and are listed in missing_autoids. Call it once all cases are recorded (or when you have to stop).",
		snippet: "Seal the recorded cases of a batch into machine_mindmap.json.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"out_name": Type.String(),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_lang_query",
		label: "CEX lang query",
		description: "Look up the compile language before writing it: E/F contract, method signatures, dispatch, precedent usage, confirmation prompts, near-miss names, the language-document catalog, parameter contracts. kind is one of contract / signature / dispatch / usage / host / nearest / prompt_pattern / docs / param / complete / heads. Pass out_name while recomposing so command lookups are recorded for that batch.",
		snippet: "Look up the compile language before writing it: E/F contract, method signatures, dispatch, precedent usage, confirmation prompts, near-miss names, the language-document catalog, parameter contracts.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"kind": Type.String(),
			"name": Type.Optional(Type.String()),
			"domain": Type.Optional(Type.String()),
			"query": Type.Optional(Type.String()),
			"position": Type.Optional(Type.Integer({"minimum": 0})),
			"out_name": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_bed_topology",
		label: "CEX bed topology",
		description: "Fetch this bed's network facts and its service list (services: host, ip, proto, port, note) from the gateway and store them in the workspace; the authoring gates read them. Needs the lease. Pick VIPs and trigger hosts from the returned summary and backends from services (matching protocol and port); never guess an address.",
		snippet: "Fetch this bed's network facts and its service list (services: host, ip, proto, port, note) from the gateway and store them in the workspace; the authoring gates read them.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"refresh": Type.Optional(Type.Boolean({"description": "Re-collect on the jump host instead of reusing the gateway's cached facts."})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_author_prepare",
		label: "CEX author prepare",
		description: "Project a sealed machine mindmap into per-case contract cards and stamp every case for authoring. Each expectation carries its criterion type and allowed_slots: the exact [block_kind, operator] pairs the submission gate accepts (slot_rule explains how a binding is matched). Each card carries the case's concretizations (what step_structure refs point at). When a criterion shape is not yet adjudicated it stops and lists the shapes for cex_criterion_record. Needs cex_recompose_seal and cex_bed_topology first.",
		snippet: "Project a sealed machine mindmap into per-case contract cards and stamp every case for authoring.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"out_name": Type.String(),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_criterion_record",
		label: "CEX criterion record",
		description: "Record your criterion judgement for one pending shape (read its brief_path first). judgment is one object: criterion_type copied from the brief's catalogue, rationale (English), disclosure (Chinese), optionally manual_anchor_ids / tree_context_ids / behaviour_classes. The engine re-checks it; after the last shape the contracts are published.",
		snippet: "Record your criterion judgement for one pending shape (read its brief_path first).",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"out_name": Type.String(),
			"shape_key": Type.String(),
			"judgment": Type.Record(Type.String(), Type.Unknown(), {"description": "{criterion_type, rationale, disclosure, manual_anchor_ids?, tree_context_ids?, behaviour_classes?}"}),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_author_submit_case",
		label: "CEX author submit case",
		description: "Submit one mechanical case (ist.mechanical-case body in the blocks language: schema, autoid, description, binding {}, init_commands, blocks, expectation_binding, escape_hatches; no seal). The engine's submission gates run (expansion, command tree, bed reachability, teardown, expectation bijection, criterion binding, provenance). A rejection lists every violation with its locus and a legal form; fix all and resubmit the complete body. Sealed cases are emitted by cex_author_emit.",
		snippet: "Submit one mechanical case (ist.mechanical-case body in the blocks language: schema, autoid, description, binding {}, init_commands, blocks, expectation_binding, escape_hatches; no seal).",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"out_name": Type.String(),
			"mechanical_case": Type.Record(Type.String(), Type.Unknown(), {"description": "The complete ist.mechanical-case submission body."}),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_author_emit",
		label: "CEX author emit",
		description: "Expand every sealed mechanical case of the batch (the engine's own block expansion) into compile_outputs/<batch>/cases.json, compile case.xlsx and run verify_batch. Returns ok:false with error when a contracted case is not sealed (not_sealed_autoids) or its sealed file changed since sealing (not_emitted); the workbook then holds only the other cases.",
		snippet: "Expand every sealed mechanical case of the batch (the engine's own block expansion) into compile_outputs/<batch>/cases.json, compile case.xlsx and run verify_batch.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"out_name": Type.String(),
		}, { additionalProperties: false }),
	},
];
