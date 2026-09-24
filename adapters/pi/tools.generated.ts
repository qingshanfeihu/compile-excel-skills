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
		description: "Create or update the compile-excel workspace in a project folder. Stores the server URL and device build in <folder>/.compile-excel/config.json. Run once per folder before logging in.",
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
		description: "Start the OAuth device login. Returns a URL and a user code; show both to the user, who signs in with their username and access code in a browser. Then call cex_login_wait.",
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
		description: "Fetch the organisation constants published by the server (portal, defect tracker and gateway addresses) and cache them in the workspace.",
		snippet: "Fetch the organisation constants published by the server (portal, defect tracker and gateway addresses) and cache them in the workspace.",
		readOnly: false,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_docs_query",
		label: "CEX docs query",
		description: "Keyword search over the server's CLI and product manuals. Returns matching documents with short snippets.",
		snippet: "Keyword search over the server's CLI and product manuals.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"q": Type.String({"description": "Search terms."}),
			"limit": Type.Optional(Type.Integer({"minimum": 1, "maximum": 10})),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_cmd_check",
		label: "CEX cmd check",
		description: "Check device commands against the synced command-tree projection: whether each command exists on this build and whether its parameters fit the recorded contract. This is the same judgment the engine uses; a miss means the command will not run on the device.",
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
		description: "Scan a compiled case workbook for device-wide destructive commands (whole-config wipes, factory restore, reboot/shutdown). Rules come from the synced domain grammar; any finding means the workbook must not run on a shared bed.",
		snippet: "Scan a compiled case workbook for device-wide destructive commands (whole-config wipes, factory restore, reboot/shutdown).",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"xlsx": Type.String({"description": "Workbook path inside the workspace."}),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_bed_lease",
		label: "CEX bed lease",
		description: "Manage your lease on the test bed through the jumphost gateway. acquire before any device work, heartbeat during long sessions, release when done, status to see who holds it. The lease is kept in the workspace; other device tools use it automatically.",
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
		description: "Check the bed before running cases: framework present, devices reachable, device build matches the bundle build, safety rules available. Needs the lease.",
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
		description: "State of a submitted run (running or done) with the tail of its log.",
		snippet: "State of a submitted run (running or done) with the tail of its log.",
		readOnly: true,
		parameters: Type.Object({
			"workspace": Type.Optional(Type.String()),
			"task_id": Type.String(),
		}, { additionalProperties: false }),
	},
	{
		name: "cex_case_results",
		label: "CEX case results",
		description: "Per-case framework verdicts of a finished run. Writes run_results.json and run_receipt.md next to the workbook. Logs from earlier runs are marked and not used as evidence.",
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
];
