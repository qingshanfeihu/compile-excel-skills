# Case versus specification: `consistency`

[R11] You hold both sides here — the bound governing SPEC and the sealed case source. Nothing downstream holds that
pair again, so the judgement is made once, here, per case, in `consistency`: an `ist.recompose-consistency` object
or JSON `null`. Name locators and judgement fields (`verdict`, `incompatibility`, `premises[].origin+locator`,
`spec_clauses`, `missing_preconditions`). Omit quote bytes; the engine stamps them from the locators. Do not emit
case-level `scenario1`.

Two inputs are already decided and you do not re-derive either: case completeness is the
description/steps/expectation triple in `source_status`, and specification presence is `governing_spec.status`
from `cex_recompose_prepare` — judging either again gives one question two answers. Emit `consistency: null` when
`source_status` is `incomplete` (that case goes down the Scenario 2 path) or when no specification is bound: with
nothing to compare against there is no judgement, and compiling from the author's text alone is not a conflict.

## Three verdicts

[R13] Otherwise `verdict` is one of three:

**`consistent`** — both can hold. The ordinary outcome.

**`mutually_exclusive`** — two complete sources contradict. This abandons the case — no workbook, no question to a
human — so the bar is both locators, one `incompatibility` sentence, and every premise pointing at a complete
source atom by locator. Name the span that carries the whole proposition; cutting a condition or negation can
reverse the sentence.

**`underdetermined`** — the case is complete and the specification is clear, but the expected result does not
follow from the procedure *as written*, because the procedure never establishes a precondition the specification
requires. **This is not a conflict and not a terminal.** The case keeps going: the compile stage adds the missing
precondition steps and compiles it normally. Put each gap in `missing_preconditions`, naming the configuration
object or state the specification requires and the authored step the procedure jumps past — the compile stage
works from that text, so "preconditions are insufficient" is useless where a concrete gap is not.

Telling those two apart is where this stage earns its keep. A reason of the form "the procedure never configures
the object the specification requires, so the expected result cannot be derived" describes the third bucket, not
the second; signing it as a conflict abandons a compilable case, and a batch abandoned on that reading drags its
already-verified siblings down with it. Ask which you have: *do the two sources contradict*, or *does the case not
yet say enough for the expectation to follow*? Only the first is mutual exclusion.

## Evidence fields

For `mutually_exclusive` and `consistent` alike: `spec_locator` (bound `spec:<file>:<line>` /
`spec:<file>:<start>-<end>`); `case_locator` (`title`, `step:<n>`, `expectation:<label>` or `orphan_note:<n>`);
`incompatibility`, one sentence that replaces neither locators nor premises; `premises` as
`{origin: spec|case, locator}`; and `spec_clauses` as `{text, disposition, reason}` slices. Judge
`consistency_source_atoms` (from `cex_recompose_prepare`) and the bound specification file *before* naming
locators.

[R14] One mechanical check runs on this object, and it is why `spec_clauses` exists: **the slices, in order, must
reconstruct the whole of the engine-stamped `spec_quote` with no gap between them.** Name a three-sentence span and
cover two and the object is rejected — that is exactly how a fallback branch or an exception clause disappears from
an argument for abandoning a case. The dispositions are recorded, not counted: relabelling a slice does not move
the verdict. Device output, probe echoes, precedent and footprint observations are not sources here.

## A case that contradicts itself: `authored_conflict`

[R12] `verdict` answers case versus specification. Whether two of the case's **own** surfaces can both be what it
verifies is a different question with its own optional record on the same object: `authored_conflict` =
`{surfaces: [{locator}], incompatibility}`, at least two distinct authored locators (`title`, `step:<n>`,
`expectation:<label>`, `orphan_note:<n>`) and one sentence saying why they cannot hold together. It cites the
author's surfaces, never the specification, so the `spec_clauses` seam law has no part in it; omit `quote` and the
engine stamps each surface from its locator. It leaves `verdict` alone, reaches the compile stage as
machine-readable supply, and is the record a `proposal` sentence cannot be — downstream reads it, prose it cannot.
Deciding which surface is the slip is an authority call this stage does not hold, so leave both authored words
where the author put them and name the pair here.

## Shape

`missing_preconditions` is non-empty only for `underdetermined`:

```json
{
  "schema": "ist.recompose-consistency",
  "verdict": "consistent|mutually_exclusive|underdetermined",
  "spec_locator": "spec:<governing-spec>.md:221",
  "case_locator": "expectation:check1",
  "incompatibility": "<why both cannot hold, or why the expectation does not follow>",
  "premises": [{"origin": "spec", "locator": "spec:<governing-spec>.md:221"},
               {"origin": "case", "locator": "step:2"}],
  "spec_clauses": [{"text": "<slice of the engine-stamped spec span>", "disposition": "contradicts",
                    "reason": "<why>"}],
  "missing_preconditions": [],
  "authored_conflict": null
}
```

`authored_conflict`, when present:
`{"surfaces": [{"locator": "title"}, {"locator": "step:2"}], "incompatibility": "<why these two authored surfaces
cannot both be what this case verifies>"}`.
