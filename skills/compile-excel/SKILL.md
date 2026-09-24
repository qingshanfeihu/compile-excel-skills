---
name: compile-excel
description: "Compile test-case content (mindmap / case list / step text) into a structurally correct, device-ready case.xlsx execution workbook. Use when the user asks to 编译用例 / 脑图转 excel / 生成 case.xlsx / 出测试卷 / 用例编译, or hands you case steps and wants the batch workbook. The script owns workbook structure (execution sheet, header row, E/F/G/H/I column semantics, contract markers, atomic write); you own case content. Do NOT trigger for: reviewing or auditing existing cases without producing a workbook, executing cases on a device (that is the InfoTest engine's job), hand-editing an existing case.xlsx cell by cell, or deploying/configuring the distribution server itself. Script and reference paths in this skill are relative to the skill's own directory."
license: Proprietary
---

# Compile Excel

Compile case content into a `case.xlsx` the device framework can actually run. Wrong
structure does not fail loudly — the framework silently skips case rows and reports a
**vacuous pass**. That is why structure is owned by scripts, never by hand-rolled openpyxl.

| Task | Approach |
|---|---|
| Skill just linked, or first use this session | `scripts/link_status.py` → OAuth login if needed → ask device username/password if missing |
| First use on a machine (no env binding) | Setup interview → `references/env-setup.md` |
| Environment already bound | `scripts/preflight.py` → report → user confirms → compile |
| Recompose a mindmap before compiling | dispatch the `mindmap-recompose` skill (direct preview) → author only its contract cases |
| Ground commands against the cmdtree (compile-time) | `scripts/cmdtree_check.py` — unknown head = fix before compiling, not on the device |
| Compile cases | You write `cases.json` → `scripts/compile_excel.py` |
| Static acceptance of a product | `scripts/verify_batch.py` only. Structure/layout/contract gate. |
| Run a product on-device (上机) | `scripts/run_device.py` → real verdicts per case |
| Backfill run results (回填) | `scripts/backfill.py` → footprint.jsonl (true-PASS writeback) |
| Rework discipline (返工闸) | `scripts/rework_gate.py` → 重派集⊆fail集，pass 案锁卷面 |
| Verification failed | Rework loop → `references/gotchas.md` 反馈→修法对照表 |
| Sync artifacts from the server (optional) | `scripts/login.py` → `scripts/fetch.py` → `references/server-sync.md` |

Script paths below are relative to this skill's directory.

## Requirements for every output

1. **The only path to a workbook is `scripts/compile_excel.py`, gated by `scripts/cmdtree_check.py`.** Never write openpyxl
   by hand: the execution header sits at row 29 (not row 1), the contract marker and
   `IST_EXECUTION_SHEET` defined-name must survive, and hand-rolled sheets misalign the
   C/E/F/G columns — the framework then finds no case rows and passes vacuously.
2. **Every case carries at least one check_point that can pass.** The framework counts
   pass as `success > 0`; an assertion-free case is guaranteed to fail on device.
3. **autoid is 12-24 digits** (production convention: 18). Shorter ids are not recognized
   as case boundaries by the framework — verdicts get attributed to the wrong case.
4. **An assertion reads the echo of the observation step right above it.** `cmd` produces
   no echo, and a step with `h` (save_as) does not update the framework result — either
   way the following `found` is dangling and crashes the whole file on device.
   See `references/gotchas.md` before choosing methods.
5. **Static acceptance is `scripts/verify_batch.py`; the on-device verdict is
   `scripts/run_device.py`.** Do not call InfoTest_Engine or `deep_check_infotest.py`
   yourself. `run_device.py` currently borrows the InfoTest framework client and reads
   `IST_ENGINE_ROOT` from the env binding, which the user sets once; do not set it ad hoc.
   A product ships only when verify_batch fails 0 AND the on-device run has fail 0 and
   underdetermined 0.
6. **Rework goes through `scripts/rework_gate.py`** — redispatch ⊆ prior fail set;
   prior-pass cases are locked. Never recompile a passing case away silently.
7. **Report to the user exactly**: batch name, case count, step/check_point counts, product
   path, verification totals (pass/fail/total), on-device totals (pass/fail/underdetermined)
   with attribution layers, and the receipt/footprint paths (`run_receipt.md`, `footprint.jsonl`).

## Workflow

### 1. Dependency probe (every compile, before anything)

```bash
python3 -c "import openpyxl"
```

If missing, tell the user and get confirmation before `pip install openpyxl` — never
install silently. If the user declines, stop: compiling is impossible without it.

### 2. Link (every session, before compile)

Loading this skill runs `scripts/link_status.py`. That script owns the wording:
re-login text and which credentials are still missing. Relay what it prints; never ask
for a password or other secret in chat.

```bash
python3 scripts/link_status.py
```

Read the JSON. Do not continue while `ok` is false.

- `oauth.ok` is false: run `python3 scripts/login.py --no-browser`. Show the user the
  `verification_uri` and wait until they authorize. Then run `python3 scripts/fetch.py`.
  Do not invent a token.
- `ask` is not empty: some credentials were never collected. Tell the user which keys
  are missing and the `target_file` path, and ask them to fill those keys themselves —
  in an editor, or by running `scripts/collect_credentials.sh --target <target_file>` in
  their own terminal (masked input, writes a 600 file). Values never pass through the
  conversation. Wait for the user to say it is done.
- After both succeed, run `link_status.py` again. Only `ok: true` may proceed.

### 3. Environment binding

Lookup order: `$COMPILE_EXCEL_ENV` → `<workspace>/.circle/compile-excel.env` →
`~/.config/compile-excel/env`.

- **Found** → run preflight (step 4).
- **Not found** → run the Setup interview in `references/env-setup.md` (one question at
  a time, defaults offered). Never guess KMS/jumphost values yourself.

### 4. Preflight (two-phase, never skipped)

```bash
python3 scripts/preflight.py
```

Report the structured check results to the user and get confirmation **before**
compiling. Probe failure → relay the failing checks verbatim, fix the env, re-run.
Do not silently retry, do not compile past a red probe.

### 5. Recompose before authoring (when the input is a human mindmap)

The compile engine always runs a recompose stage before authoring; this skill matches it.
When the source is a mindmap (XMind JSON export or Markdown table), dispatch the
`mindmap-recompose` skill first (direct invocation = preview, `governing_spec: null`) and:

- author `cases.json` **only from its contract cases** (verbatim intent + sourced method +
  verbatim expectation);
- anything the recompose filed as `proposal` (e.g. 「访问成功」 traffic verdicts with no
  client on the bed) must NOT become an assertion — report it to the user as un-compiled;
- keep `exp_recipe / step_recipe / true_gap` counts in your final report.

Plain step-text inputs (no mindmap) skip this stage.

**Local knowledge folder**: if a `KNOWLEDGE_DIR` is bound (env binding) or `<workspace>/knowledge/`
exists, its files feed this stage; `*.md` (manual / spec) are legal verbatim sources for contract fields, quoted with
`origin spec:<file>:<line>` / `manual:<file>:<line>`. Zero invention still rules: knowledge
files widen the source pool, they never license paraphrase.

### 6. Author cases.json

Contract: `references/column-semantics.md` (read it the first time; it defines the
E/F/G/H/I five-tuple and the per-object method families). Minimal shape:

```json
{"batch": "smoke_0923", "init_commands": ["configure terminal"],
 "cases": [{"autoid": "202609236681010001", "priority": "P1",
   "steps": [
     {"e": "APV_0", "f": "cmd_config", "g": "show version", "h": "", "i": "", "desc": "观察版本"},
     {"e": "check_point", "f": "found", "g": "version", "h": "", "i": "", "desc": "断言版本"}]}]}
```

You decide the content (which commands, which assertions, which expectations); the script
guarantees the structure. A sentinel case is appended automatically — do not add one.

### 7. Command grounding (compile-time, mandatory)

```bash
python3 scripts/cmdtree_check.py --cases cases.json
```

"Does this command exist on this build" is decided by the command-tree projection alone — an
unknown head is fixed **before** compiling, never discovered as `% invalid` on the device. The
checker reads the projection (`vendor_stdlib_*.json`) from the workspace's synced bundle
(`cex_sync`), or `--projection <file>`, and uses the same judgment function as the engine: it
flags unknown heads and parameters that do not fit the recorded contract (arity, type, value
domain). It also validates a compiled workbook (`--xlsx ...`). Exit 1 = fix `cases.json` first
(this includes init rows). Exit 2 = no projection yet: run `cex_sync`. The raw command-tree XML
is not distributed (it carries parameter defaults, including credential defaults); `--tree`
exists only for local debugging with a file you already have.

### 8. Compile

```bash
python3 scripts/compile_excel.py --cases cases.json --out compile_outputs
```

Output is a stats JSON (path/case_count/check_point_count/template identity, plus
`sources_defaulted` — how many check_points fell back to author-verbatim). A non-zero
exit with `{"ok": false, "error": ...}` means your cases.json violated a hard requirement —
fix the JSON, never work around the script.

Every compile also writes `provenance.json` beside the xlsx: the per-case expected-value
sources (mirror of the engine's `case.provenance.json`, light form). check_point steps
may carry `"source": {"kind": ..., "ref": ...}` (kinds: author-verbatim / author / spec /
manual / defectspec / configbinding / capabilityxml); missing ones default to
`author-verbatim → mindmap:<autoid>` and are counted in `sources_defaulted` — cite the
real source (mindmap node text, spec file:line, manual file:line) whenever it exists.

### 9. Static verification (every time)

```bash
python3 scripts/verify_batch.py --xlsx compile_outputs/<batch>/case.xlsx
```

This is the structural gate: structure, layout, E/F membership, check_point coverage,
autoid discipline, assertions that would match the command text itself, the **tautology
family** (expected hitting prompt shapes / regex matching the empty string / not_found
of a token in the feeding command — all 恒真或恒假), and the **provenance sidecar**
(every check_point carries a non-empty expected-value source).
`pass/fail/totals` come from this script. Do not shell out to InfoTest_Engine.
On failure, use `references/gotchas.md`, fix `cases.json`, recompile, re-verify.

### 10. On-device run (上机)

```bash
python3 scripts/run_device.py --xlsx compile_outputs/<batch>/case.xlsx
```

The excel is NOT interpreted locally: this script is a headless driver of the InfoTest
`FrameworkMCPClient`. Real chain: xlsx → SFTP to the jumphost staging dir
(`ist_staging_<module>/<autoid>/`) → the framework converts xlsx→`test_xlsx.py` → pytest
runs it on the bound APV bed → every check_point verdict lands in the framework result
DB → verdicts are read back per autoid (fail-closed; `=== 1 passed ===` alone means
nothing). Credentials come from the env binding (`RUN_JUMPHOST_IP` = run bed,
`JUMPHOST_USER/PASS`, `IST_DEVICE_BUILD`); none enter the conversation. The script
self-selects a py≥3.10 + paramiko interpreter if the default one lacks them.

Writes `run_results.json` + `run_receipt.md` beside the xlsx. Non-pass cases carry the
framework log tail plus a **mechanical first-pass attribution** (`G` = CLI error markers,
`transient?` = timeout/connection/bus suspects, `undetermined` = the semantic call
E/V/product-defect stays with the session — the script never over-reaches). Exit 0 only
when every real case passes.
On fail: read the per-case `detail_tail` + attribution, fix `cases.json` per
`references/gotchas.md`, **pass the rework gate**, recompile, re-verify, re-run.

**Rework gate (mandatory before recompiling into the same batch dir):**

```bash
python3 scripts/rework_gate.py --batch-dir compile_outputs/<batch> --cases cases.json
```

Mirror of the engine's merge discipline: the redispatch set must be a subset of the
prior fail set; prior-pass cases are locked (content change = violation; a wholesale
restart requires `--force` and is recorded). Writes `rework.json` (round, fail set,
redispatch set, kept passes) for audit.

### 11. Backfill (回填)

```bash
python3 scripts/backfill.py --results compile_outputs/<batch>/run_results.json
```

Appends every case verdict to `footprint.jsonl` (append-only ledger, run identity = xlsx
SHA-256 + timestamps). True PASSes are the writeback record; fails/underdetermined stay
open for the rework loop. The workbook and `cases.json` are never edited by backfill.

## Gotchas that bite hardest (details in references/gotchas.md)

- `cmd` produces no echo; only `cmd_config`'s output can feed the next assertion.
- A step with `h` captures into a variable **and does not update the framework result**;
  a bare `found` after it is dangling (crashes the whole file on device).
- Capture-compare needs the three-step form: observe(`h=v1`) → observe(no `h`) →
  check_point(`h=v1`, auto-normalized to `abs_found`).
- `found` treats G as a **regex**; expected text containing `.` `+` `@` needs
  `abs_found` (literal) or escaping.
- **`found` G matches the command itself = false pass**: `g="version"` after
  `show version` matches the command line, not the output. `verify_batch.py`
  rejects this. Fix: make G more specific so it matches a data line, not the command.

## Artifact sync from the distribution server

The link gate in step 2 requires a logged-in server session; compiling does not start
without it. `login.py` once (browser authorization), then `fetch.py` (per-file SHA256,
mismatch rejected, offline falls back to cache with an explicit version notice),
`docs_query.py` for manual retrieval. Details and env vars: `references/server-sync.md`.

## Dependencies

python3 (3.9+) · openpyxl (probe first, install only with user consent) · paramiko + py≥3.10
(same consent rule — needed only for the on-device stage; `run_device.py` auto re-execs on a
suitable interpreter). Static verification is `scripts/verify_batch.py`; on-device runs are
`scripts/run_device.py` (framework client). The on-device stage is the only part that
still needs an InfoTest checkout (`IST_ENGINE_ROOT` in the env binding); it moves to the
jumphost gateway next.
