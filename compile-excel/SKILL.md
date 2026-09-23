---
name: compile-excel
description: "Compile test-case content (mindmap / case list / step text) into a structurally correct, device-ready case.xlsx execution workbook. Use when the user asks to 编译用例 / 脑图转 excel / 生成 case.xlsx / 出测试卷 / 用例编译, or hands you case steps and wants the batch workbook. The script owns workbook structure (execution sheet, header row, E/F/G/H/I column semantics, contract markers, atomic write); you own case content. Do NOT trigger for: reviewing or auditing existing cases without producing a workbook, executing cases on a device (that is the InfoTest engine's job), hand-editing an existing case.xlsx cell by cell, or deploying/configuring the distribution server itself."
license: Proprietary
---

# Compile Excel

Compile case content into a `case.xlsx` the device framework can actually run. Wrong
structure does not fail loudly — the framework silently skips case rows and reports a
**vacuous pass**. That is why structure is owned by scripts, never by hand-rolled openpyxl.

| Task | Approach |
|---|---|
| First use on a machine (no env binding) | Setup interview → `references/env-setup.md` |
| Environment already bound | `scripts/preflight.py` → report → user confirms → compile |
| Compile cases | You write `cases.json` → `scripts/compile_excel.py` |
| Verify a product | `scripts/verify_batch.py` (structure) + engine lint (semantics, see Verification) |
| Engine lint rejected the product | Rework loop → `references/gotchas.md` 反馈→修法对照表 |
| Sync artifacts from the server (optional) | `scripts/login.py` → `scripts/fetch.py` → `references/server-sync.md` |

Script paths below are relative to this skill's directory.

## Requirements for every output

1. **The only path to a workbook is `scripts/compile_excel.py`.** Never write openpyxl
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
5. **Nothing ships with `fail > 0` in verification.** Run the Verification section every
   time; a local clean bill does not replace engine lint (see its semantics there).
6. **Report to the user exactly**: batch name, case count, step/check_point counts,
   product path, verification totals (pass/fail/total).

## Workflow

### 1. Dependency probe (every compile, before anything)

```bash
python3 -c "import openpyxl"
```

If missing, tell the user and get confirmation before `pip install openpyxl` — never
install silently. If the user declines, stop: compiling is impossible without it.

### 2. Environment binding

Lookup order: `$COMPILE_EXCEL_ENV` → `<workspace>/.circle/compile-excel.env` →
`~/.config/compile-excel/env`.

- **Found** → run preflight (step 3).
- **Not found** → run the Setup interview in `references/env-setup.md` (one question at
  a time, defaults offered). Never guess KMS/jumphost values yourself.

### 3. Preflight (two-phase, never skipped)

```bash
python3 scripts/preflight.py
```

Report the structured check results to the user and get confirmation **before**
compiling. Probe failure → relay the failing checks verbatim, fix the env, re-run.
Do not silently retry, do not compile past a red probe.

### 4. Author cases.json

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

### 5. Compile

```bash
python3 scripts/compile_excel.py --cases cases.json --out compile_outputs
```

Output is a stats JSON (path/case_count/check_point_count/template identity). A non-zero
exit with `{"ok": false, "error": ...}` means your cases.json violated a hard requirement —
fix the JSON, never work around the script.

### 6. Verification (both layers, every time)

```bash
python3 scripts/verify_batch.py --xlsx compile_outputs/<batch>/case.xlsx
```

- Layer 1 (local, always runs): structure, layout, E/F membership, check_point coverage,
  autoid discipline → `pass/fail/totals`.
- Layer 2 (engine, the semantic final judge): when `IST_ENGINE_ROOT` is set or a sibling
  `InfoTest_Engine` exists, the report includes the data-driven row-by-row contract check.
  A **skip is not a pass**: local 11/11 says nothing about dangling assertions or G-column
  semantics — if the engine is available, run it:

  ```bash
  IST_ENGINE_ROOT=<engine> python3 tests/deep_check_infotest.py <case.xlsx>
  ```

  `tests/` ships with this skill. When the user reports a lint finding, go to
  `references/gotchas.md`, match the code, apply the fix, recompile, re-verify.

## Gotchas that bite hardest (details in references/gotchas.md)

- `cmd` produces no echo; only `cmd_config`'s output can feed the next assertion.
- A step with `h` captures into a variable **and does not update the framework result**;
  a bare `found` after it is dangling (crashes the whole file on device).
- Capture-compare needs the three-step form: observe(`h=v1`) → observe(no `h`) →
  check_point(`h=v1`, auto-normalized to `abs_found`).
- `found` treats G as a **regex**; expected text containing `.` `+` `@` needs
  `abs_found` (literal) or escaping.

## Optional: artifact sync from the distribution server

`login.py` once (browser authorization), then `fetch.py` (per-file SHA256, mismatch
rejected, offline falls back to cache with an explicit version notice), `docs_query.py`
for manual retrieval. Details and env vars: `references/server-sync.md`. No server
configured? Skip this section entirely — local compiling does not depend on it.

## Dependencies

python3 (3.9+) · openpyxl (probe first, install only with user consent). Engine-side
verification additionally needs the InfoTest engine root — see Verification.
