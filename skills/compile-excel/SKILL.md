---
name: compile-excel
description: "Compile test-case content (mindmap / case list / step text) into a structurally correct case.xlsx and run it on the test bed through the jumphost gateway. Use when the user asks to 编译用例 / 脑图转 excel / 生成 case.xlsx / 出测试卷 / 用例编译 / 上机验证用例 / 用例上机, or hands you case steps and wants the batch workbook or its on-device verdicts. Everything lands in the user's project folder. The scripts own workbook structure (execution sheet, header row, E/F/G/H/I column semantics, contract markers, atomic write); you own case content; the cex_* tools own login, compile data, defect tickets and the bed. Do NOT trigger for: reviewing or auditing existing cases without producing a workbook, hand-editing an existing case.xlsx cell by cell, or deploying/configuring the distribution server or the gateway. Script and reference paths in this skill are relative to the skill's own directory."
license: Proprietary
---

# Compile Excel

Compile case content into a `case.xlsx` the device framework can actually run, then run it on
the bed and bring the verdicts back. Wrong structure does not fail loudly: the framework
silently skips case rows and reports a **vacuous pass**. That is why structure is owned by
scripts, never by hand-rolled openpyxl.

The project folder is the workspace. Compile data, the OAuth token and all products live
there (`.compile-excel/` for state, `compile_outputs/` for products). The folder holds exactly
one credential, the OAuth token; jumphost and device passwords stay on the gateway, and the
portal session sits in a private per-user cache. Nothing secret passes through the conversation.

| Task | Approach |
|---|---|
| First use in this folder | `cex_status` → `cex_init` → `cex_login_start` / `cex_login_wait` → `cex_client_config` → `cex_sync` ([workspace setup](references/workspace-setup.md)) |
| Every session | `cex_status`; log in again only if `logged_in` is false; `cex_sync` |
| Read a defect ticket as source | `cex_portal_login_start` → user scans → `cex_portal_login_wait` → `cex_bug_get` |
| Compile a mindmap | `mindmap-recompose` skill (seal) → `cex_bed_lease acquire` → `cex_bed_topology` → `cex_author_prepare` → one `cex_author_submit_case` per case → `cex_author_emit` ([authoring](references/authoring.md)) |
| Type a new verdict shape | `cex_author_prepare` stops at `criterion_pending` → `cex_criterion_record` ([criterion](references/criterion.md)) |
| Look up manual text / a command's manual line | `cex_docs_query`; `cex_lang_query` `{"kind": "param", "name": "<head>"}` |
| Ground commands against the build | `cex_cmd_check` while authoring; `scripts/cmdtree_check.py` as the gate for hand-written cases |
| Compile plain step text (no mindmap) | You write `cases.json` → `scripts/compile_excel.py` |
| Static acceptance | `scripts/verify_batch.py` + `cex_scan_destructive` |
| Run on the bed (上机) | `cex_bed_lease acquire` → `cex_env_prepare` → `scripts/run_device.py` (or `cex_case_submit` / `cex_case_status` / `cex_case_results`) |
| Rework after a failed run (返工) | `scripts/rework_gate.py` → fix only failed cases → recompile → verify → rerun |
| Backfill results (回填) | `scripts/backfill.py` → `footprint.jsonl` |
| Verification failed | `references/gotchas.md` feedback → fix table |

## Tools

The `cex_*` tools come from the compile-excel MCP server (Claude Code plugin), the circle
extension, or the pi extension; all three are generated from the same tool specs. In Claude Code
they are listed with the plugin prefix (`mcp__plugin_compile-excel_compile-excel__<name>`). When the
harness exposes none of them, call the same tools from a shell:

```bash
CEX_HOME="$(python3 scripts/_cex_path.py)"          # prints the distribution root
python3 "$CEX_HOME/bin/cex_tool" list                 # tool names and argument schemas
python3 "$CEX_HOME/bin/cex_tool" cex_status '{"workspace": "<project folder>"}'
```

Every tool takes `workspace` (the project folder); when it is omitted the tool uses
`$CEX_WORKSPACE`, else the nearest folder above the current directory that has `.compile-excel/`.
Results are JSON with `ok`; on `ok: false` read `error` / `problems` and relay them.

## Requirements for every output

1. **The only paths to a workbook are `cex_author_emit` (mindmap batches) and
   `scripts/compile_excel.py` gated by `scripts/cmdtree_check.py` (plain step text).**
   The execution header sits at row 29 (not row 1), the contract marker and the
   `IST_EXECUTION_SHEET` defined-name must survive, and hand-rolled sheets misalign the
   C/E/F/G columns: the framework then finds no case rows and passes vacuously.
2. **Every case carries at least one check_point that can pass.** The framework counts
   pass as `success > 0`; an assertion-free case is guaranteed to fail on the device.
3. **autoid is 12-24 digits** (production convention: 18). Shorter ids are not recognized
   as case boundaries by the framework, so verdicts get attributed to the wrong case.
4. **An assertion reads the echo of the observation step right above it.** `cmd` produces
   no echo, and a step with `h` (save_as) does not update the framework result. Either way
   the following `found` is dangling and crashes the whole file on the device.
   See `references/gotchas.md` before choosing methods.
5. **Expected values come from sources, never from the device.** A check_point's expectation
   is author text, spec, manual, defect ticket, config binding or capability XML, cited in its
   `source`. Output from `cex_probe_show` or a failed run is the *actual* side: use it to
   understand a failure, never copy it into an expectation to make a case pass.
6. **A product ships only when** `verify_batch.py` fails 0, `cex_scan_destructive` finds
   nothing, and the on-device run has fail 0 and not_run 0.
7. **Rework goes through `scripts/rework_gate.py`**: the redispatch set is a subset of the prior
   fail set and prior-pass cases are locked. Never recompile a passing case away silently.
8. **The bed is shared.** Hold the lease only while you use it, `heartbeat` during long work,
   `release` when done. When `acquire` reports the bed is leased by someone else, tell the user
   who holds it and for how long, and wait for their call instead of retrying in a loop.

## Workflow

### 1. Dependency probe (every compile, before anything)

```bash
python3 -c "import openpyxl"
```

If it is missing, tell the user and get confirmation before
`pip install -r "$CEX_HOME/requirements.txt"`. Never install silently; if the user declines,
stop, because compiling is impossible without it.

### 2. Workspace, login, compile data

Call `cex_status` with the project folder.

- `ok: false` (no workspace): ask the user for the server URL and the device build of the bed
  they will run on, then `cex_init`. Details: `references/workspace-setup.md`.
- `logged_in: false`: `cex_login_start`, show the user `verification_uri` and `user_code`, then
  `cex_login_wait`; call it again while it returns `pending`. The user types their username and
  access code into the server's page, not into the conversation. Never invent a token.
- `cex_client_config` once per session (it publishes the gateway and portal addresses).
- `cex_sync` every session. `source: server` = fresh; `source: cache` = the server was
  unreachable and the cached bundle is in use: tell the user its `note` (bundle id and date).
  A `SHA256 mismatch` error means a download was rejected; report it, do not work around it.

### 3. Defect tickets as source (only when the case comes from a defect)

`cex_portal_login_start` saves a QR image to a private file and returns its path. Ask the user
to open that file and scan it with the company app, then `cex_portal_login_wait` (again while
`pending`). `cex_bug_get` with `backend` (`bugzilla` / `zentao` / `zentao_story`) and the ticket
id fetches the ticket with the user's own permissions and saves the scrubbed result under
`defects/<backend>/<ticket>.json`. When it reports the session expired, ask the user to scan
again; the tool does not retry by itself. Never ask for a portal password.

### 4. Recompose before authoring (when the input is a human mindmap)

Run the `mindmap-recompose` skill first. It seals
`compile_outputs/<out_name>/machine_mindmap.json`, every case of which passed the compile
engine's submission checks. The authoring stage (5A) compiles from that sealed file; keep the
`exp_recipe / step_recipe / true_gap` counts for your final report. Plain step-text inputs skip
this stage and go to 5B.

The synced bundle (`.compile-excel/bundle/<build>/`) carries spec and manual files when the
server publishes them, and `cex_docs_query` searches the manuals. Both are legal verbatim
sources, quoted as `spec:<file>:<line>` / `manual:<file>:<line>`. Sources widen the pool; they
never license paraphrase.

### 5A. Author a mindmap batch (after the seal)

Read `references/authoring.md` before the first case. In short:

1. `cex_bed_lease` `acquire`, then `cex_bed_topology`: the bed's devices and addresses as the
   engine reads them (VIPs a trigger host can reach, which trigger host pairs with which VIP,
   real server addresses). The authoring gates judge every address against these facts.
2. `cex_author_prepare` with the batch name: the engine projects the sealed mindmap into one
   contract card per case (the author's expectations, each typed with a criterion and the block
   kinds / operators allowed to redeem it) and returns them with the bed summary. When it stops
   at `criterion_pending`, type each pending shape per `references/criterion.md`
   (`cex_criterion_record`); the cards are published after the last one. The user-facing
   disclosures (how each verdict was typed, recompose proposals) are written to
   `compile_outputs/<batch>/author_disclosures.json` for your final report.
3. Per case, write one mechanical case in the block language and submit it with
   `cex_author_submit_case`. Every card expectation must be redeemed by exactly one assertion —
   traffic verdicts such as 「访问成功」「访问失败」 by `OBSERVE_EXIT` from the paired trigger host,
   configuration/display verdicts by `OBSERVE_ASSERT` on the device. A rejection lists every
   violation with its locus and legal form: fix them all and resubmit the complete body.
4. `cex_author_emit` when every case is sealed: the engine expands the sealed cases into
   `cases.json` (assertion sources included), `case.xlsx` is compiled and `verify_batch` runs.
   Continue at step 8 (`cex_scan_destructive`) and the on-device run.

A case the engine quarantines, abandons or puts under `needs_decision` in the prepare result is
not authored: report it with the reason the result gives.

### 5B. Author cases.json (plain step text only)

Contract: `references/column-semantics.md` (read it the first time; it defines the
E/F/G/H/I five-tuple and the per-object method families). Output shape:

```json
{"batch": "smoke_0923", "init_commands": ["<init command>"],
 "cases": [{"autoid": "202609236681010001", "priority": "P1",
   "steps": [
     {"e": "APV_0", "f": "cmd_config", "g": "<observation command>", "h": "", "i": "", "desc": "观察"},
     {"e": "check_point", "f": "found", "g": "<expected text>", "h": "", "i": "", "desc": "断言",
      "source": {"kind": "spec", "ref": "spec:<file>:<line>"}}]}]}
```

You decide the content (which commands, which assertions, which expectations); the script
guarantees the structure. A sentinel case is appended automatically; do not add one. Keep
`cases.json` inside the workspace, e.g. `compile_outputs/<batch>/cases.json`.

### 6. Command grounding (compile-time, mandatory)

While authoring, `cex_cmd_check` answers "does this command exist on this build, and do its
parameters fit" for a list of candidate commands. Before compiling, run the gate:

```bash
python3 scripts/cmdtree_check.py --cases <workspace>/compile_outputs/<batch>/cases.json
```

Whether a command exists on this build is decided by the command-tree projection alone. An
unknown head or a parameter outside the recorded contract (arity, type, value domain) is fixed
**before** compiling, never discovered as `% invalid` on the device. Exit 1 = fix `cases.json`
first (init rows included). Exit 2 = no projection yet: run `cex_sync`.

### 7. Compile

```bash
python3 scripts/compile_excel.py --cases <workspace>/compile_outputs/<batch>/cases.json \
    --out <workspace>/compile_outputs
```

Output is a stats JSON (path / case_count / check_point_count / template identity, plus
`sources_defaulted`: how many check_points fell back to author-verbatim). A non-zero exit with
`{"ok": false, "error": ...}` means `cases.json` violated a hard requirement: fix the JSON,
never work around the script.

Every compile also writes `provenance.json` beside the xlsx: the per-case expected-value
sources. check_point steps may carry `"source": {"kind": ..., "ref": ...}` (kinds:
author-verbatim / author / spec / manual / defectspec / configbinding / capabilityxml); missing
ones default to `author-verbatim → mindmap:<autoid>` and are counted in `sources_defaulted`.
Cite the real source (mindmap node text, spec file:line, manual file:line, defect ticket)
whenever it exists.

### 8. Static verification (every time)

```bash
python3 scripts/verify_batch.py --xlsx <workspace>/compile_outputs/<batch>/case.xlsx
```

Then `cex_scan_destructive` with the same `xlsx`. The first is the structural gate: structure,
layout, E/F membership, check_point coverage, autoid discipline, assertions that would match the
command text itself, the **tautology family** (expected hitting prompt shapes / regex matching
the empty string / not_found of a token in the feeding command), the **provenance sidecar**,
and **init isolation**: `init_commands` replay before every case, so they may only reset state
(`clear` / `no`, `show`, mode switches); an object a case needs is created in that case's own steps.
The second rejects device-wide destructive commands using rules from the synced bundle; the
gateway runs the same check again on submit. On failure, use `references/gotchas.md`, fix
`cases.json`, recompile, re-verify.

### 9. On-device run (上机)

1. `cex_bed_lease` with `action: acquire`. If someone else holds the bed, see requirement 8.
2. `cex_env_prepare`: framework present, devices reachable, device build equals the workspace
   build, safety rules available. Report a failed check to the user as-is; do not submit past it.
3. Run the workbook:

   ```bash
   python3 scripts/run_device.py --xlsx <workspace>/compile_outputs/<batch>/case.xlsx
   ```

   It submits through the gateway, polls until the run ends and fetches the verdicts; the
   step-by-step equivalent is `cex_case_submit` → `cex_case_status` (until `done`) →
   `cex_case_results`. The gateway re-checks the workbook (Excel contract, destructive commands,
   credential literals) and refuses rather than rewriting it; a refusal lists `problems`.
4. Verdicts come from the framework result database, bound to this task; pytest's own
   `1 passed` means nothing. `run_results.json` and `run_receipt.md` are written beside the
   xlsx. Non-pass cases carry the framework log tail plus a mechanical first-pass attribution
   (`G` = CLI error text in the log, `transient?` = timeout/connection suspects, `undetermined`
   otherwise). The semantic call (expectation wrong, product defect, environment) stays with
   you: read the `detail_tail` itself. A log marked stale predates this submission and is no
   evidence for it.
5. `cex_probe_show` runs one read-only `show`/`get` command when you need the device's actual
   state to understand a failure (requirement 5 still holds).
6. `cex_init_device` wipes and re-baselines devices. Use it only when the user asks for it:
   `step: prepare` returns the plan and a one-time code; show both to the user and call
   `step: confirm` with the code only after they agree. It needs admin rights on the gateway.
7. `cex_bed_lease` with `action: release` when you are done with the bed.

On fail: read each case's `detail_tail` and attribution. For a mindmap batch, fix the failed
cases' mechanical cases and resubmit them (`cex_author_submit_case`), then `cex_author_emit`;
for hand-written cases fix `cases.json` per `references/gotchas.md`. Either way **pass the rework
gate** on the new `cases.json`, recompile/re-emit, re-verify, re-run.

```bash
python3 scripts/rework_gate.py --batch-dir <workspace>/compile_outputs/<batch> --cases <cases.json>
```

The redispatch set must be a subset of the prior fail set; prior-pass cases are locked (content
change = violation; a wholesale restart needs `--force` and is recorded). Writes `rework.json`
(round, fail set, redispatch set, kept passes).

### 10. Backfill (回填)

```bash
python3 scripts/backfill.py --results <workspace>/compile_outputs/<batch>/run_results.json
```

Appends every case verdict to `footprint.jsonl` (append-only; run identity = xlsx SHA-256 +
timestamps). True PASSes are the writeback record; fails stay open for the rework loop. The
workbook and `cases.json` are never edited by backfill.

## Report

Tell the user: batch name, case count, step / check_point counts, product path, verification
totals (pass / fail / total), destructive-scan result, on-device totals (pass / fail / not_run)
with attribution layers, the receipt and footprint paths (`run_receipt.md`, `footprint.jsonl`),
the bundle id the compile used, every case not compiled (quarantined, abandoned, awaiting a
user decision) with its reason, and every criterion you typed with `cex_criterion_record`. Name
the stages that did not run (e.g. no bed lease) instead of implying they passed.

## Done when

- `compile_outputs/<batch>/` holds `case.xlsx`, `provenance.json`, `run_results.json`,
  `run_receipt.md` and `footprint.jsonl` with this run appended;
- `verify_batch.py` fails 0, `cex_scan_destructive` is clean, and the on-device run has
  fail 0 and not_run 0 (or the user accepted the remaining failures after seeing the evidence);
- the bed lease is released;
- the report above is delivered.

## Gotchas that bite hardest (details in references/gotchas.md)

- `cmd` produces no echo; only `cmd_config`'s output can feed the next assertion.
- A step with `h` captures into a variable **and does not update the framework result**;
  a bare `found` after it is dangling (crashes the whole file on the device).
- Capture-compare needs the three-step form: observe (`h=v1`) → observe (no `h`) →
  check_point (`h=v1`, auto-normalized to `abs_found`).
- `found` treats G as a **regex**; expected text containing `.` `+` `@` needs
  `abs_found` (literal) or escaping.
- **A `found` G that matches the command itself is a false pass**: an expectation that is a
  word of the observation command matches the echoed command line, not the output.
  `verify_batch.py` rejects this; make G specific enough to match only a data line.

## Dependencies

python3 (3.9+) · openpyxl (probe first, install only with user consent) · beautifulsoup4 and
PyYAML for `cex_bug_get`. The client itself uses only the standard library. The on-device
stage needs the gateway the server publishes (`cex_client_config`) and a bed lease.
