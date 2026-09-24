---
name: mindmap-recompose
description: "Recompose a human-authored mindmap (XMind JSON export) into a machine mindmap before compiling it: for every case a contract triple of verbatim intent + sourced verification method + verbatim expectation, relocated from where the author put it. Zero invention: every contract character is a verbatim substring of the mindmap or its engine-resolved governing spec; anything else becomes a proposal, never a contract. The engine's own checks judge every recorded case. Use when the user asks for 脑图重组 / 人工脑图转机器脑图 / 契约重组 / 脑图预处理 / 脑图可重组率 / recompose mindmap, wants a mindmap pre-organized before compiling, or wants to know how much of a mindmap is machine-ready. Do NOT trigger for: compiling cases into case.xlsx (compile-excel), reviewing existing test cases, or running a workbook on the bed. Reference paths in this skill are relative to the skill's own directory."
license: Proprietary
---

# Mindmap Recompose (human mindmap → machine mindmap)

Turn an author's mindmap into a **machine mindmap**: for every case, a contract triple of **verbatim intent +
sourced verification method + verbatim expectation**. The knowledge is usually already in the wrong slot, so
this task is **relocation, not authoring**. The result, `compile_outputs/<out_name>/machine_mindmap.json`, is what
the compile-excel skill authors cases from.

The judging is not yours alone: every case you record goes through the compile engine's own submission checks
(verbatim sourcing, anchors, step structure, consistency citations) inside `cex_recompose_submit_cases`. A
rejection names the entry, the field and the legal form; repair that case and submit it again.

## Tools and workflow

| Tool | Use |
|---|---|
| `cex_status` | Workspace, login and sync state. Not logged in or not synced: set the workspace up first (compile-excel skill, workspace setup) |
| `cex_recompose_prepare` | Once per mindmap: seals a snapshot, resolves the governing spec, opens the submission |
| file read / grep tools | Read the snapshot and the bound spec file |
| `cex_lang_query` (with `out_name`) | Command-tree and manual lookups for grounding (§5) |
| `cex_cmd_check` | Command existence and argument count against the synced projection (§5) |
| `cex_recompose_submit_cases` | Record finished cases; the engine's checks run here |
| `cex_recompose_seal` | Seal the recorded cases into `machine_mindmap.json` |
| `cex_bug_get` | Optional discovery read of a ticket the root title names; never a source |

Every tool takes `workspace` (the project folder). Progress checklist:

```
- [ ] 1. cex_status; the workspace is logged in and synced
- [ ] 2. cex_recompose_prepare(mindmap=<path inside the workspace>)
- [ ] 3. Read mindmap_snapshot once; build the decoded atom map (R23, R41)
- [ ] 4. Per outstanding case: steps 1–5 below, then cex_recompose_submit_cases(out_name, cases=[case])
- [ ] 5. outstanding_autoids is empty → cex_recompose_seal(out_name)
- [ ] 6. Chinese report to the user (§7)
```

`cex_recompose_prepare` returns what the engine would put in the dispatch brief:

- `mindmap_snapshot` — the sealed source. [R36] Read exactly this file; never the original input path or a
  sibling path.
- `out_name` — the batch name every later call takes.
- `case_autoids`, `outstanding_autoids`, `already_recorded` — the dispatched case set in source order. Skip
  `already_recorded` (a previous run recorded them).
- `governing_spec` — `status` is `bound` (read `path`; its `name` is the file in `spec:` origins),
  `no_governing_spec`, or `ambiguous` (several candidates; `references[]` are slices with zero signing power, R47).
- `defect_spec_status` and `defect_spec_receipt_sha256` — the second SPEC channel; see "Sources".
- `consistency_source_atoms` — the unfolded locator bytes the engine will stamp. Judge them (§4.1); do not copy
  them into quote fields.

The input must be an XMind JSON export with exactly one root title. When the user names no file, glob the
workspace for candidates; use the only match, and when there are several, ask which one. Pass `spec=<file>` only
when the user named the governing document themselves, and `spec='none'` only when the user says no document
governs this mindmap; an `ambiguous` status is not a reason to ask — the engine proceeds the same way.
Calling `cex_recompose_prepare` again with the same spec outcome resumes (recorded cases stay recorded); a
different outcome starts the case set over, because those cases were judged against another specification.
Either way it reopens the batch, so seal again afterwards.

## The one rule that outranks everything

[R1] **Zero invention.** Every character you put into a contract field must be a *verbatim substring* of **the
source mindmap or its engine-resolved governing document SPEC**. You are moving text, not writing text. If a
case needs knowledge that is present in neither, it does not get a contract — it gets a `proposal` entry saying
what is missing. A plausible-sounding expectation you composed yourself is worse than an honest gap, because
downstream everything treats a contract as authored truth.

The governing document SPEC is a legal verbatim source because manual cases are written *from* it; quoting that
exact, identity-bound file is citing upstream authority, not inventing. Text lifted from the spec must carry
`origin` `spec:<file>:<line>` (span form `spec:<file>:<start>-<end>`) so the quote is independently checkable.

## Sources

[R3] `governing_spec` is derived mechanically from the sealed mindmap root, the synced SPEC generation and its
index before you start. It is a credential, not a suggestion: when status is `bound`, read only the file at
`governing_spec.path`; when it is `no_governing_spec` or `ambiguous`, no `spec:` atom is legal. Do not scan the
spec store to replace, override, or fill a missing identity. Do not put source/SPEC/DefectSpec identity into
case objects or the seal: the tools inject them from the prepared dispatch, so transcription cannot alter
artifact identity.

[R48] A product manual or converted product document (what `cex_docs_query` searches, the manuals `cex_lang_query`
names) is not a SPEC and is never a legal backfill source in this skill. Only the singular engine-resolved SPEC
may supply `spec:<file>:<line>` atoms.

[R47] On `ambiguous`, `governing_spec.references[]` (name, anchor, evidence, local `path`) are reference-level
supply with zero signing power — never `spec:` atoms, never the governing question, never the case-versus-
specification conflict; the only legal use is filling underdetermined procedure blanks.

[R4] This client binds no DefectSpec projection: the engine's ticket lookup and sealed safe projection are not
part of it. `defect_spec_status` is therefore `not_queried` (a spec is bound or ambiguous), `no_ticket_reference`
(the root title names no ticket), or `resolved_absent` (the root title names a ticket, or the user said no spec
governs), and `defect_spec_receipt_sha256` is null; a `defect:` origin is rejected at submission. A root title
whose first identity token is an optional `BUG` marker followed by at least four decimal digits names a ticket;
derive that from the decoded root atom, never by grepping the serialized source. You may read the ticket with
`cex_bug_get` to understand the case (it needs the user's portal QR login; ask before starting one). It is
discovery only: never copy its text into a contract field, and never treat actual result, reproduction, log, or
comments as expected. Device actual, probe output, precedent, and footprint observations are not sources either.

### XMind export: verified structural facts

[R41] Every `.txt` export here begins with the bytes `EF BF BF EF BB BF` — a stray `U+FFFF` followed by a BOM — so
`json.loads` on the raw text fails; strip both leading characters first. The remainder is a non-empty list of
roots; process every root.

[R42] A case is a node carrying `autoid` and either no `auto` marker or `auto: "YES"`. Skip an explicit non-YES case.
Two source layouts exist and their roles are not interchangeable:

1. **Title/step/expectation layout:** the autoid node text is the title, its children are steps, and each step's
   children are expectations.
2. **Case-body/leaf-expectation layout:** the autoid node text itself is the numbered action block or single
   intent/action. Use this layout when the autoid node has exactly one child, that child is a leaf, and its text
   begins with one or more `[checkN]` locators. Split the autoid-node text into steps and split the leaf into
   expectation atoms, then bind matching `[checkN]` locators. Do not turn the leaf expectation into a step. A
   locator is an identity, not an ordinal: `[check1]` maps to `expectation:check1`, `[check2]` maps to
   `expectation:check2`, and so on. Never rewrite these as zero-based `expectation:0` / `expectation:1` origins.

[R43] Additional shapes: bind multiple expectation siblings by authored number without merging them. For an explicit
previous-case dependency, set `depends_on` only when that predecessor autoid is verbatim in the case; otherwise
keep null and retain the continuation sentence in `adaptation_notes`. Keep case-depth notes without autoid under
indexed `orphan_notes`; they have no mechanically bound target, so never cite them as contract origins and
disclose the unresolved gap.

## Steps

### 1. Decompose — atomize the tree, keep every character

Read the snapshot once. Walk it into atoms and record where each atom came from, without reformatting text. Atoms
per case: `group_path` (ancestor titles, outermost first), `title`, `steps_block` (raw merged text, newlines
intact), `expectation_block` (raw, may be absent), and any sibling notes that are not cases (no `autoid`) — keep
those under `orphan_notes`, they often hold verification knowledge for a neighbouring case.

Success criteria: every case node with an `autoid` appears exactly once; no atom text has been edited.

### 2. Split — follow authored locators and preserve atomic children

Author blocks are usually numbered runs inside a single node. Split on the author's own numbering, not your
judgement of what a step is, and keep the author's numbers — they are the anchor you cite in step 4. In the
case-body/leaf-expectation layout, an unnumbered multi-line action block uses each non-empty authored line as one
ordered action atom; preserve every line as a whole — a newline is not permission to trim conditions, prefixes,
or trailing `[checkN]` locators.

[R24] Expectation nodes use a narrower split rule. Only explicit authored numbering or a `[checkN]` locator may
split one expectation node into more than one atom. An unnumbered multi-line expectation child is one atomic
expectation. Preserve its internal newlines and punctuation in one `expectations_by_step` item, bound to the
child node's single origin; commas and newlines alone are content, not locators. A newline inside it does not
create `expectation:1.2`. Never move an additional expected claim into `adaptation_notes`. Every authored
expected claim remains in `expectations_by_step`; `adaptation_notes` is never its only carrier.

Success criteria: concatenating the split pieces back reproduces the original block character for character
(modulo the separators you split on).

### 3. Classify — three buckets

For each case, decide where its verification knowledge actually lives:

- `exp_recipe` — the expectation slot already contains an observation target and expected content.
- `step_recipe` — the expectation slot is empty or vacuous, but the title or a step line carries extractable
  verification knowledge (an observation command, an expected state, a comparison). This is the recomposable
  bucket.
- `true_gap` — none of title, steps, expectation carries verification knowledge.

Judge on what the text says, not on whether you could imagine a reasonable expectation. "Check the connection
between nodes" is an *action*, not an expectation — a case whose only clue is that line is `true_gap` unless
something else states what a correct connection looks like.

[R39] **Classify by content, never by slot occupancy.** A non-empty expectation node whose entire text is an
*outcome label* is the recurring trap: it names a verdict without saying what observation would produce it,
so it is not verification knowledge and does not make the case `exp_recipe`. Ask of every expectation:

> If I ran the step and stared at the device output, could I decide pass/fail from this sentence alone?

`<observation A> and <observation B> have equal results` → yes: it names two observations and a relation.
`<successful outcome>` → no: nothing to compare against, no output shape, no value. An expectation that fails
that question does **not** make the case `exp_recipe`. Look at the title and steps: if they carry the real
criterion, it is `step_recipe`; if nothing anywhere does, it is `true_gap`. Either way put the vacuous sentence
verbatim in the contract's `expectation` (it is still the author's text) and add a `proposal` naming what a
usable criterion would need to state. Do not soften this to keep the recomposable rate high: a rate earned by
counting an outcome label as verification knowledge is a lie that costs a device round to discover.

### 4. Recompose — fill the triple, cite the origin of every field

Read `references/case-fields.md` before the first case: it is the per-field contract (`contract`, `origin`,
`expectations_by_step`, `steps`, `adapted_steps`, `adaptation_notes`, `proposal`, the two status axes and
`scenario2`). `references/step-structure.md` is the `step_structure` contract, and `references/output-shape.md`
shows a whole case object. The rules that decide most cases:

- `intent` is verbatim — normally the title; `verification_method` is verbatim text of *how* one observes;
  `expectation` is verbatim text of *what* the correct result is. Each carries an `origin`: `title`,
  `step:<author number>`, `expectation:<label>`, or `spec:<file>:<line>` / `spec:<file>:<start>-<end>`. A
  contract field without an origin is not acceptable output.
- [R40] **Spec backfill — the move that turns step_recipe into a contract.** When the mindmap gives the
  observation command but the expectation is only a verdict label, search the governing spec for the concrete
  criterion the author was working from: default values, file paths where config lands, error prompts, display
  rules, limits. Lift that sentence **verbatim** into verification material or `expectations_by_step`, cite it
  as `spec:<file>:<line>`, and the case gets a checkable criterion instead of a proposal. The spec sentence must
  be about the same object and behaviour the case exercises; a sentence that merely mentions the feature name is
  not a criterion. If the spec states no usable criterion either, fall back to `proposal`. [R26] The scalar
  `contract.expectation` itself stays one whole authored atom with its authored origin, never spec wording.
- [R6] If a field cannot be filled verbatim from either source, leave it `null` and add a `proposal` entry
  describing the missing signed declaration. Never request an observed device output as the expected value:
  device output is `actual` only and cannot sign `expected`. `proposal` is an array of non-empty plain strings.

Success criteria: every non-null contract field is a whole source atom from the mindmap or governing document
SPEC, and every one has an origin naming which source it came from.

### 4.1 Judge case versus specification once — here

Read `references/consistency.md` before judging the first case that has a bound specification. [R11] You hold
both sides here — the bound governing SPEC and the sealed case source — and nothing downstream holds that pair
again, so the judgement is made once, per case, in `consistency`. Emit `consistency: null` when `source_status`
is `incomplete` or when no specification is bound.

[R13] The distinction that matters most: **`mutually_exclusive`** means two complete sources contradict, and it
abandons the case with no workbook and no question to a human. **`underdetermined`** means the case is complete
and the specification is clear, but the procedure never establishes a precondition the specification requires;
that is not a conflict and not a terminal — the compile stage adds the missing precondition steps. Ask which you
have: *do the two sources contradict*, or *does the case not yet say enough for the expectation to follow*? Only
the first is mutual exclusion; signing the second as a conflict abandons a compilable case.

### 4.2 Enhance — adapt steps, concretize ambiguous process values, license unreachable literals

Read `references/adaptation.md` before writing `adapted_steps`, `concretizations`, or `rebind_licenses`. All three
are bed-agnostic side records: the sealed fields stay verbatim, no bed values, reasoning disclosed. [R2] Adaptation
may change a command's arguments, never remove a command, a negation, a condition, or a stated difference, and
never add an object or action the author did not write.

### 5. Ground every command against the product command tree

Read `references/command-grounding.md` before the first lookup. [R21] `command_check` is diagnostic output only; the
engine recomputes command existence independently. [R20] **Do not repair anything**: when the author's head is
not in the tree, record it and keep the author's text.

[R22] The durable progress unit is one finished case. Ground only what the first outstanding case needs, record it,
then move on; reuse results already in context instead of prefetching the whole batch.

### 6. Self-check before recording

[R23] For a one-line XMind JSON export, do not use repeated grep calls to prove decoded atom whitespace — grep sees
the serialized representation, not the decoded evidence surface. Validate exact text against the decoded atom map
from the initial read; if a non-contract note remains uncertain, omit it rather than enumerating whitespace regex
variants.

[R49] Verify each of these and report the numbers honestly, including failures:

1. **Verbatim check** — for each non-null field, confirm the exact string occurs in the source. Report any field
   that fails; do not silently drop it.
2. **Coverage check** — case count in equals case count out, and every case's `steps` equals the ordered
   complete source atom list with no drop, truncation, reorder, or duplicate.
3. **No-invention check** — if you cannot point to the origin of a field, that field is invented; null it and
   move it to `proposal`.
4. **Bucket totals** — count of `exp_recipe` / `step_recipe` / `true_gap`.
5. **Command grounding** — how many distinct commands checked, how many absent from the vendor tree, and how
   many with an argument-count mismatch; or state that grounding was unavailable and why.
6. **Consistency verdicts** — count of `consistent` / `mutually_exclusive` / `underdetermined` and how many
   cases carry `null`. For every `mutually_exclusive`, re-read the bytes at the two locators with their
   surrounding sentence; confirm the contradiction still holds uncut and `spec_clauses` covers the stamped span.
   If either fails, the case is not abandoned. For every `underdetermined`, confirm `missing_preconditions` names
   a concrete gap.

### 7. Record, seal, report

[R34] Record each finished case with `cex_recompose_submit_cases(out_name, cases=[...])` as a native array of case
objects before moving to the next; resubmitting an autoid replaces its earlier record. A rejected payload records
nothing and names the next legal action. Do not repeat unchanged rejected arguments; if a receipt reports an empty
or unparseable payload, re-issue once as a compact native array (trim free-form prose, keep every verbatim atom
exact). [R38] Use this skill's case shape as the only template; do not copy a `machine_mindmap.json` from another
batch — it may carry another source or SPEC identity.

When `outstanding_autoids` is empty, call `cex_recompose_seal(out_name)` once. It seals the recorded cases in source
order; a case never recorded falls back to the author's original text and is listed in `missing_autoids`. Do not
read the artifact back to re-verify it; the seal already did.

[R53] Close with a short Chinese report to the user: the artifact path, the three bucket counts, null-field count,
Scenario 2 cases, consistency verdict counts, command grounding numbers (or why grounding was unavailable), and
every rejection you could not resolve. Printing the machine-mindmap JSON is not a submission; only the tools
record it. Do not claim compile readiness: that is decided when compile-excel consumes the artifact.

## Done when

- `cex_recompose_seal` returned `ok: true` and `missing_autoids` is empty, or every missing case is named in the
  report with the reason it could not be recorded;
- every recorded case passed the engine's submission checks (no case was recorded by working around a rejection);
- the report gives the numbers in §7.
