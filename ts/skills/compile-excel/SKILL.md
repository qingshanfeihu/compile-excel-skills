---
name: compile-excel
description: "Compile test-case content (mindmap / case list / step text) into a structurally correct case.xlsx and run it on the test bed through the jumphost gateway. Use when the user asks to 编译用例 / 脑图转 excel / 生成 case.xlsx / 出测试卷 / 用例编译 / 上机验证用例 / 用例上机, or hands you case steps and wants the batch workbook or its on-device verdicts. Everything lands in the user's project folder. The scripts own workbook structure (execution sheet, header row, E/F/G/H/I column semantics, contract markers, atomic write); you own case content; the cex_* tools own login, compile data, defect tickets and the bed. Do NOT trigger for: reviewing or auditing existing cases without producing a workbook, hand-editing an existing case.xlsx cell by cell, or deploying/configuring the distribution server or the gateway. Script and reference paths in this skill are relative to the skill's own directory."
license: Proprietary
---

# Compile Excel

Compile case content into a `case.xlsx` the device framework can actually run, then run it on
the bed and bring the verdicts back. Wrong structure does not fail loudly: the framework
silently skips case rows and reports a **vacuous pass**. That is why structure is owned by
scripts, never by hand-rolled xlsx tooling.

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
| Look up manual text / a command's manual line | `cex_docs_query` searches the current build's locally synced manuals first, then online server documents; `cex_lang_query` `{"kind": "param", "name": "<head>"}` |
| Ground commands against the build | `cex_cmd_check` while authoring; `cmdtree_check.js` as the gate for hand-written cases |
| Compile plain step text (no mindmap) | You write `compile_outputs/<batch>/cases.json` → `cmdtree_check.js` → `compile_excel.js` |
| Static acceptance | `verify_batch.js` + `cex_scan_destructive` |
| Run on the bed (上机) | `cex_bed_lease acquire` → `cex_env_prepare` → `run_device.js` (or `cex_case_submit` / `cex_case_status` / `cex_case_results`) → `cex_bed_lease release` |
| Rework a mindmap batch (返工) | `cex_author_submit_case` for the failed cases → `cex_author_emit` → `rework_gate.js` on the emitted `cases.json` → `cex_scan_destructive` → rerun |
| Rework plain step text (返工) | fix the failed cases in `cases.json` → `rework_gate.js` → compile → verify → `cex_scan_destructive` → rerun |
| Backfill results (回填) | `backfill.js` → `footprint.jsonl` |
| Verification failed | `references/gotchas.md` feedback → fix table |

## Tools

The `cex_*` tools come from the compile-excel MCP server (Claude Code plugin), the circle
extension, or the pi extension; all three are generated from the same tool specs. In Claude Code
they are listed with the plugin prefix (`mcp__plugin_compile-excel_compile-excel__<name>`). When the
harness exposes none of them, call the same tools from a shell:

```bash
CEX_HOME="$(node scripts/_cex_path.js)"              # prints the distribution root
node "$CEX_HOME/dist/bin/cex_tool.js" list             # tool names and argument schemas
node "$CEX_HOME/dist/bin/cex_tool.js" cex_status '{"workspace": "<project folder>"}'
node "$CEX_HOME/dist/bin/cex_tool.js" cex_author_submit_case - < args.json   # argument object via stdin
```

Skill scripts live in the same distribution: run them as
`node "$CEX_HOME/dist/skills_scripts/<name>.js"` (compile_excel / verify_batch / run_device /
rework_gate / backfill / cmdtree_check). Resolve `CEX_HOME` once per session with
`node scripts/_cex_path.js` from this skill's directory.

Every tool takes `workspace` (the project folder); when it is omitted the tool uses
`$CEX_WORKSPACE`, else the nearest folder above the current directory that has `.compile-excel/`.
Results are JSON with `ok`; on `ok: false` read `error` / `problems` and relay them.

## Requirements for every output

1. **The only paths to a workbook are `cex_author_emit` (mindmap batches) and
   `compile_excel.js` gated by `cmdtree_check.js` (plain step text).**
   The execution header sits at row 29 (not row 1), the contract marker and the
   `IST_EXECUTION_SHEET` defined-name must survive, and hand-rolled sheets misalign the
   C/E/F/G columns: the framework then finds no case rows and passes vacuously. A mindmap
   batch's `cases.json` is the engine's expansion of its sealed cases: it changes only through
   `cex_author_submit_case` + `cex_author_emit`. `compile_excel.js` refuses it (it carries the
   `_generated` marker) unless the user asks for `--allow-edited-emit`, and then the product is no
   longer the engine-sealed batch; say so in the report.
2. **Every case carries at least one check_point that can pass.** The framework passes a case
   only when none of its check points failed and at least one passed (`fail == 0` and
   `success > 0`); an assertion-free case is guaranteed to fail on the device.
3. **autoid is 12-24 digits** (production convention: 18). Shorter ids are not recognized
   as case boundaries by the framework, so verdicts get attributed to the wrong case.
4. **An assertion reads the result of the nearest step above it in the same case that has no
   `h`.** Only an observation leaves a result to read: `cmd_config` (the device CLI), a
   `test_env` probe, and `cmd` (which runs in the device's Linux root shell, not the CLI). A step
   with `h` (save_as) stores its output in a register and leaves the result alone; `cmds_config`
   and `time::sleep` return nothing. An assertion with no un-`h` step before it, or whose nearest
   one is not an observation, is dangling: `verify_batch.js` fails it and the engine rejects it
   (`dangling_assertion`); on the device a missing result makes the framework reject the file or
   raise at that row, and no later case runs. See `references/gotchas.md` before choosing methods.
5. **Expected values come from sources, never from the device.** A check_point's expectation
   is author text, spec, manual, defect ticket, config binding or capability XML, cited in its
   `source`. Output from `cex_probe_show` or a failed run is the *actual* side: use it to
   understand a failure, never copy it into an expectation to make a case pass.
6. **A product ships only when** `verify_batch.js` fails 0, `cex_scan_destructive` finds
   nothing, and the on-device run has fail 0, broken 0 and not_run 0.
7. **Rework goes through `rework_gate.js`**: the cases you rerun must come from the prior
   fail set, and prior-pass cases are locked: every row of them, and the shared `init_commands`,
   must stay exactly as they ran. Never recompile a passing case away silently; a wholesale
   restart needs `--force --reason "<why>"` and is recorded.
8. **The bed is shared.** Take the lease when you need the bed or its facts (`cex_bed_topology`,
   `cex_env_prepare`, the run, `cex_probe_show`, `cex_init_device`) and release it as soon as that
   work is done: authoring reads the stored bed facts and needs no lease, so release it after
   `cex_bed_topology` when writing the cases will take long and acquire it again for the run.
   `heartbeat` during long work (`run_device.js` does so while it waits); the lease lapses after
   the `expires_in_s` that `acquire` reports. When `acquire` reports the bed is leased by someone
   else, tell the user who holds it and for how long, and wait for their call instead of retrying
   in a loop.

## Workflow

### 1. Dependency probe (every compile, before anything)

```bash
node --version                                                  # needs v20 or newer
node -e "require.resolve('exceljs', {paths:[process.env.CEX_HOME]})"
```

If Node is too old, tell the user and stop until a newer one is on PATH. If the module probe
fails, tell the user and get confirmation before `npm install --omit=dev` inside `$CEX_HOME`.
Never install silently; if the user declines, stop, because compiling is impossible without it.

### 2. Workspace, login, compile data

Call `cex_status` with the project folder.

- `ok: false` (no workspace): ask the user for the connection string their administrator gave
  (`https://host:8900#ca=<fingerprint>`) and pass it to `cex_init` as `server`, exactly as given.
  Leave `device_build` out; it is chosen after login. Errors from `cex_init` are in Chinese and
  say what to fix; relay them. Details: `references/workspace-setup.md`.
- `logged_in: false`: `cex_login_start`, show the user `verification_uri` and `user_code`, then
  `cex_login_wait`; call it again while it returns `pending`. The user types their username and
  access code into the server's page, not into the conversation. Never invent a token. When the
  result has `browser_certificate`, relay it word for word first: it explains the browser's
  certificate warning and the fingerprint to compare.
- No device build yet (`device_build_selected: false`): the successful `cex_login_wait` picks it
  when the server publishes only one. When it returns `builds` instead, ask the user which one the
  bed runs and call `cex_init` with only `device_build` (no `server`; the session is kept). Never
  guess a build.
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
this stage and go to 5B. A batch whose governing spec is `bound` cannot be authored in this
client (every `cex_author_submit_case` is rejected with `consistency_stage_unavailable`): the
recompose skill asks the user before anything is recomposed against it.

The synced bundle (`.compile-excel/bundle/<build>/`) carries spec and manual files when the
server publishes them. `cex_docs_query` searches the current build's local manuals first and
also searches server documents when available. Results mark `source` as `local_manual` or
`server_document`; only local manual results have a `manual:<version>/<file>.md:<line>` ref.
`limit` caps each source separately (default 3, maximum 10), so online results can contain up to
twice that many matches.
Offline results say server documents were not searched. If neither source is available, the
tool reports a supply failure. Sync the current device build when local manuals are expected.
Spec and manual text are legal verbatim sources, quoted as `spec:<file>:<line>` /
`manual:<file>:<line>`. Server document snippets have no build-bound manual ref. Sources widen
the pool; they never license paraphrase.

### 5A. Author a mindmap batch (after the seal)

Read `references/authoring.md` before the first case. In short:

1. `cex_bed_lease` `acquire`, then `cex_bed_topology`: the bed's devices and addresses as the
   engine reads them (VIPs a trigger host can reach, which trigger host pairs with which VIP,
   backend addresses) and `services`, the backend services declared for this bed
   (`host`, `ip`, `proto`, `port`, `note`). The authoring gates judge every address against these
   facts. Pick backends only from `services` for the protocol you need; when none is listed, do
   not guess an address: tell the user which service is missing. The facts are stored in the
   workspace, so the lease can go back until the run when writing the cases will take long
   (requirement 8).
2. `cex_author_prepare` with the batch name: the engine projects the sealed mindmap into one
   contract card per case (the author's expectations, each typed with a criterion and the exact
   `allowed_slots` that may redeem it, plus the recompose `concretizations`) and returns them with
   the bed view and `blocks_schema`, the path of the block-language field reference. When it
   stops at `criterion_pending`, type each pending shape per `references/criterion.md`
   (`cex_criterion_record`); the cards are published after the last one. The user-facing
   disclosures (how each verdict was typed, recompose proposals) are written to
   `compile_outputs/<batch>/author_disclosures.json` for your final report. No tool vetoes a
   typed criterion in this client: when the user disagrees with one, put the objection in the
   report.
3. Per case, write one mechanical case in the block language and submit it with
   `cex_author_submit_case`. Every card expectation must be redeemed and every assertion must
   redeem a card expectation. An expectation over several objects (分别 / 各 / 每 / 三个 …) gets one
   assertion per object, each with its own `expectation_binding` entry carrying the same
   `expectation_id`. Traffic verdicts such as 「访问成功」「访问失败」「使用原有协议访问失败」 are
   redeemed by `OBSERVE_EXIT` from the paired trigger host even when the card types them
   `status_value`, and a failing arm must fail because of the authored difference (whatever the
   author did not change — address, port, trigger host, backend — stays as in its success arm).
   Configuration/display verdicts go to `OBSERVE_ASSERT` on the device. A rejection lists every
   violation with its locus and legal form: fix them all and resubmit the complete body. A sealed
   result may still carry `advisories`: resolve each one, or disclose it in the report with the
   reason it stays.
4. `cex_author_emit` when every case is sealed: the engine expands the sealed cases into
   `cases.json` (assertion sources included), `case.xlsx` is compiled and `verify_batch` runs.
   It returns `ok: false` when a contracted case is not sealed (`not_sealed_autoids`) or its
   sealed file was replaced (`not_emitted`): do not run that workbook; submit those cases and
   emit again, or tell the user which cases are missing. Continue at step 8
   (`cex_scan_destructive`) and the on-device run.

A case the engine quarantines, abandons or puts under `needs_decision` in the prepare result is
not authored: report it with the reason the result gives.

The cards stand on the sealed mindmap they were projected from. `cex_recompose_prepare` on a
sealed batch reopens it and removes `machine_mindmap.json`; from then on
`cex_author_submit_case`, `cex_criterion_record` and `cex_author_emit` refuse until the batch is
sealed again (`cex_recompose_seal`) and `cex_author_prepare` has re-projected the cards. A
recorded recompose case cannot be replaced once every case is recorded: a changed
concretization goes into the mechanical case and its `desc`, and into your report.

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
guarantees the structure. A sentinel case is appended automatically; do not add one.
`init_commands` replay before every case on the device that runs them: a list runs on `APV_0`;
`{"APV_0": [...], "APV_1": [...]}` gives each device its own block (for example clearing the peer
of a two-device case). A case that plays two nodes needs two devices: `cex_env_prepare` reports
the bed's `device_count`, and the gateway refuses a workbook that names a device the bed does not
have (`APV_1` on a one-device bed). Keep
`cases.json` at `compile_outputs/<batch>/cases.json`, next to the workbook the compile writes:
the on-device run fingerprints the `cases.json` beside the workbook, and the rework gate compares
the next round against those fingerprints.

### 6. Command grounding (compile-time, mandatory)

While authoring, `cex_cmd_check` answers "does this command exist on this build, and do its
parameters fit" for a list of candidate commands (at most 200 per call). Before compiling, run
the gate:

```bash
node "$CEX_HOME/dist/skills_scripts/cmdtree_check.js" --cases <workspace>/compile_outputs/<batch>/cases.json
```

Whether a command exists on this build is decided by the command-tree projection alone. The gate
checks every device CLI line: `init_commands`, and every `APV_*` step whose method is
`cmd_config`, `cmds_config` or `cmd_enable` (each line of a multi-line `cmds_config` on its own;
lowercase and uppercase keys alike). `cmd` runs in the device's root shell and is not judged
against the CLI tree; a CLI command given to `cmd` is reported as a warning. An unknown head or a
parameter outside the recorded contract (arity, type, value domain) is fixed **before**
compiling, never discovered as `% invalid` on the device. Exit 1 = fix `cases.json` first (init
rows included). Exit 2 = no projection yet: run `cex_sync`.

### 7. Compile

```bash
node "$CEX_HOME/dist/skills_scripts/compile_excel.js" --cases <workspace>/compile_outputs/<batch>/cases.json \
    --out <workspace>/compile_outputs
```

`--out` is the output root: the workbook lands in `<out>/<batch>/case.xlsx` (an `--out` that
already ends in the batch name is used as the batch folder itself). The result names it as
`batch_dir`.

Output is a stats JSON (path / case_count / check_point_count / template identity, plus
`sources_defaulted`: how many check_points fell back to author-verbatim). A non-zero exit with
`{"ok": false, "error": ...}` means `cases.json` violated a hard requirement: fix the JSON,
never work around the script. A `cases.json` emitted by `cex_author_emit` is refused here
(requirement 1).

Every compile also writes `provenance.json` beside the xlsx: the per-case expected-value
sources. check_point steps may carry `"source": {"kind": ..., "ref": ...}` (kinds:
author-verbatim / author / spec / manual / defectspec / configbinding / capabilityxml); missing
ones default to `author-verbatim → mindmap:<autoid>` and are counted in `sources_defaulted`.
Cite the real source (mindmap node text, spec file:line, manual file:line, defect ticket)
whenever it exists.

### 8. Static verification (every time)

```bash
node "$CEX_HOME/dist/skills_scripts/verify_batch.js" --xlsx <workspace>/compile_outputs/<batch>/case.xlsx
```

Then `cex_scan_destructive` with the same `xlsx`. The first is the structural gate: structure,
layout, E/F membership, check_point coverage, autoid discipline, **dangling assertions**
(requirement 4), assertions that would match the command text itself, the **tautology family**
(expected hitting prompt shapes / regex matching the empty string / not_found of a token in the
feeding command), the **provenance sidecar**, and **init isolation**: `init_commands` replay
before every case, so they may only reset state (`clear` / `no`, `show`, mode switches); an
object a case needs is created in that case's own steps. The second rejects device-wide
destructive commands using rules from the synced bundle; the gateway runs the same check again
on submit. On failure, use `references/gotchas.md`. A mindmap batch is fixed in its mechanical
cases (`cex_author_submit_case`, then `cex_author_emit`), never in the emitted `cases.json`;
plain step text is fixed in `cases.json`, then recompiled and re-verified.

### 9. On-device run (上机)

1. `cex_bed_lease` with `action: acquire`. If someone else holds the bed, see requirement 8.
2. `cex_env_prepare`: framework present, devices reachable, device build equals the workspace
   build, safety rules available. Report a failed check to the user as-is; do not submit past it.
3. Run the workbook:

   ```bash
   node "$CEX_HOME/dist/skills_scripts/run_device.js" --xlsx <workspace>/compile_outputs/<batch>/case.xlsx
   ```

   It submits through the gateway, prints `task_id` to stderr as soon as the gateway accepts the
   workbook, polls until the run ends (renewing the lease) and fetches the verdicts; the
   step-by-step equivalent is `cex_case_submit` → `cex_case_status` (until `done`) →
   `cex_case_results`. The gateway re-checks the workbook (Excel contract, destructive commands,
   credential literals) and refuses rather than rewriting it; a refusal lists `problems`. Exit
   codes: 0 every case passed; 1 the run finished with fail, broken or not_run; 2 not submitted
   (refused, or the submit call failed); 3 still running after `--max-s`; 4 submitted, but
   polling or fetching the results failed; 5 the run was lost (its runner died without recording
   an end: gateway restart, OOM, operator kill) and has no verdicts. On 3 and 4 continue with
   `cex_case_status` / `cex_case_results` for the printed `task_id`; do not resubmit, which runs
   the whole workbook again. On 5 resubmit.
4. Verdicts come from the framework result database, bound to this task; pytest's own
   `1 passed` means nothing. A pass or fail counts only when the case's own log ends with the
   framework's closing (the PASS/FAIL banner followed by `end case: <autoid>`): the framework
   writes a case's result row when the case begins, holding the previous case's result, so a run
   killed or crashed inside a case leaves that placeholder behind. Without the closing, or when
   the closing disagrees with the row, the case is `broken` (`broken_reason`, `recorded_result`).
   A pass whose log shows an execution failure the case's own assertions were not waiting for
   (`Failed to execute the command` and the other markers of the bundle's domain grammar) is also
   `broken`: a configuration step did not take and the assertion matched anyway. Totals are
   pass / fail / broken / not_run; `rc` is the framework process's exit status (not 0 = the run
   stopped early). `run_results.json` and `run_receipt.md` are written beside the
   xlsx (only for the latest submission of that workbook), with the run's identity on the jump
   host (`run_dir`, `submit_autoid`, `module`, `report_dir`). Non-pass cases carry `failed_checks`
   (each failed check point with the output it was matched against, e.g. `IST_EXIT_STATUS=56`
   for a traffic check), the framework log as the gateway returned it (`detail_tail`), and a
   mechanical first-pass attribution (`G` = CLI error text in the log, `transient?` =
   timeout/connection suspects, `undetermined` otherwise). The semantic call (expectation wrong,
   product defect, environment) stays with you: read `failed_checks` first, then the log, then
   the session dumps: for a non-pass case the gateway returns each device's CLI session
   (`apv_<ip>.txt`) and each trigger host's session, saved under
   `compile_outputs/<batch>/evidence/<task_id>/<autoid>/` and listed in the case's `sessions`.
   A log marked stale predates this submission and is no evidence for it. The sentinel
   `999999999999999` the compile appended is not a case: the FAIL banner it leaves at the end of
   the raw log means nothing.
5. `cex_probe_show` runs one read-only `show`/`get` command when you need the device's actual
   state to understand a failure (requirement 5 still holds).
6. `cex_init_device` wipes and re-baselines devices. Use it only when the user asks for it:
   `step: prepare` returns the plan and a one-time code; show both to the user and call
   `step: confirm` with the code only after they agree. It needs admin rights on the gateway.
7. `cex_bed_lease` with `action: release` when you are done with the bed.

On fail: read each case's `failed_checks`, `detail_tail` and attribution, then rework only the
failed cases, in this order:

- **Mindmap batch:** fix the failed cases' mechanical cases and resubmit them
  (`cex_author_submit_case`) → `cex_author_emit` → the rework gate on the emitted
  `compile_outputs/<batch>/cases.json` → `cex_scan_destructive` → rerun.
- **Plain step text:** fix the failed cases in `cases.json` per `references/gotchas.md` → the
  rework gate → compile → `verify_batch.js` → `cex_scan_destructive` → rerun.

```bash
node "$CEX_HOME/dist/skills_scripts/rework_gate.js" --batch-dir <workspace>/compile_outputs/<batch> \
    --cases <workspace>/compile_outputs/<batch>/cases.json
```

(`--results <batch>/run_results.json` is the same as `--batch-dir <batch>`, and `--rework` is
the same as `--cases`.) A `broken` case reworks like a fail.

The gate compares the new `cases.json` with what actually ran: the per-case fingerprints of
every row (its E/F/G/H/I and source) and of the shared `init_commands` that `run_results.json`
carries as `case_fingerprints`. A prior-pass case whose rows changed, a changed `init_commands` (they replay
before every case, so every prior-pass case changed with them), a prior-pass case that
disappeared and a case the prior run did not have are violations; changed and unchanged fail
cases may be rerun. Results from an older client carry no `case_fingerprints`: the gate then
compares check points only and says so in `baseline` / `baseline_note`. Exit 0 writes
`rework.json` (round, prior fail set, redispatch set, kept passes, violations); exit 1 lists the
violations and writes nothing; exit 2 is bad input. A wholesale restart the user asked for
(e.g. a pass that rested on a false observation) is `--force --reason "<why>"`: the violations
stay listed as overridden and the reason is recorded in `rework.json`.

### 10. Backfill (回填)

```bash
node "$CEX_HOME/dist/skills_scripts/backfill.js" --results <workspace>/compile_outputs/<batch>/run_results.json
```

Appends every case verdict of the run to `footprint.jsonl` (append-only; once per `task_id`).
Each line carries the run identity from `run_results.json`: the workbook SHA-256 the gateway
staged, `task_id`, submit and finish times, the result channel, plus the case's `failed_checks`.
True PASSes are the writeback record; fails stay open for the rework loop. The workbook and
`cases.json` are never edited by backfill.

## Report

Tell the user: batch name, case count, step / check_point counts, product path, verification
totals (pass / fail / total), destructive-scan result, on-device totals (pass / fail / broken / not_run)
with attribution layers, the receipt and footprint paths (`run_receipt.md`, `footprint.jsonl`),
the bundle id the compile used, every case not compiled (quarantined, abandoned, awaiting a
user decision) with its reason, every criterion you typed with `cex_criterion_record` and every
objection the user raised to a typed criterion, every advisory you left in place with its reason,
and for a rework round the `rework.json` round and any `--force` reason. Name the stages that did
not run (e.g. no bed lease) instead of implying they passed.

## Done when

- `compile_outputs/<batch>/` holds `case.xlsx`, `provenance.json`, `run_results.json`,
  `run_receipt.md` and `footprint.jsonl` with this run appended;
- `verify_batch.js` fails 0, `cex_scan_destructive` is clean, and the on-device run has
  fail 0, broken 0 and not_run 0 (or the user accepted the remaining failures after seeing the
  evidence);
- the bed lease is released;
- the report above is delivered.

## Gotchas that bite hardest (details in references/gotchas.md)

- `cmd` runs its G in the device's Linux root shell, not the CLI: CLI commands (`show …`,
  `slb …`) go through `cmd_config`.
- A step with `h` captures into a variable **and does not update the framework result**;
  a bare `found` right after it reads an older result, or none (then it is dangling).
- Capture-compare needs the three-step form: observe (`h=v1`) → observe (no `h`) →
  check_point (`h=v1`, auto-normalized to `abs_found`).
- `found` treats G as a **regex**; expected text containing `.` `+` `@` needs
  `abs_found` (literal) or escaping.
- **A `found` G that matches the command itself is a false pass**: an expectation that is a
  word of the observation command matches the echoed command line, not the output.
  `verify_batch.js` rejects this; make G specific enough to match only a data line.

## Dependencies

Node.js ≥ 20 · the distribution's npm dependencies installed once by the installer or with
user consent via `npm install --omit=dev` in `$CEX_HOME` (exceljs, fast-xml-parser, yaml, zod,
cheerio). No Python runtime is needed. The on-device stage needs the gateway the server
publishes (`cex_client_config`) and a bed lease.
