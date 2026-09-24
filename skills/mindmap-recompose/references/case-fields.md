# Case fields

The per-field contract of one machine-mindmap case. `output-shape.md` shows a whole case object;
`step-structure.md`, `consistency.md` and `adaptation.md` cover the structured side records.

## Contents

- Identity fields
- The contract triple and `origin`
- `expectations_by_step`
- `steps` and `adapted_steps`
- `adaptation_notes`
- Cases that read alike
- `proposal`
- Two status axes and `scenario2`

## Identity fields

`autoid` is the 18-digit autoid of a dispatched case, verbatim. `group_path` (ancestor titles, outermost first)
and `title` are verbatim; the engine refills `group_path` and `steps` from the sealed source, so they are never a
place to restate or improve anything. `bucket` is one of `exp_recipe`, `step_recipe`, `true_gap` (SKILL.md §3); a
case without one of the three is rejected at submission.

## The contract triple and `origin`

- `intent` — verbatim. Normally the case title. If the title is only a label and the real intent sentence is in
  a step line, use that line verbatim and cite it.
- [R25] `verification_method` — verbatim text of *how* one observes, lifted from wherever it lives (usually a step
  line or the expectation line: an observation command, a shell pipeline, a comparison instruction). The value
  still obeys the authored atom boundary. If `verification_method` comes from an unnumbered multi-line
  expectation, copy the whole expectation atom or use JSON null plus a proposal. Never slice out only its
  observation-command line.
- `expectation` — verbatim text of *what* the correct result is.
- `origin` — for each of the three fields, where it came from: `title`, `step:<author number>`,
  `expectation:<label>`, or `spec:<file>:<line>` / `spec:<file>:<start>-<end>`. This is the field that makes the
  output auditable; a contract field without an origin is not acceptable output.

[R26] The scalar `contract.expectation` is the author's own claim: one whole authored expectation atom, verbatim,
with its existing authored origin: `title`, `step:<n>`, or `expectation:<label>`. That same atom must appear in
`expectations_by_step`. An outcome written in a title or step remains an Author declaration; the absence of a
separate expectation child does not make it missing, while a step that only describes an action supplies no
outcome. SPEC lines remain legal material for verification methods, assertion values, `spec_clauses`,
`scenario2`, and proposals — never for this scalar. The contract projector quarantines a case whose primary
expectation origin+text is not a member of the authored step-expectation set.

## `expectations_by_step`

[R51] Every authored expectation sibling, in source order, as `{n, text, origin, assertion}`. `n` is the author's
step number, `text` is verbatim, and `origin` names the expectation node or governing-spec line. When already
available from an identified declaration, `assertion` contains the exact static `{operator, value}` that
implements this expectation: `operator` is an enabled `check_point` F value read from the current Excel function
contract (`cex_lang_query kind=contract`), and `value` is the exact semantic G value stated by the authored intent
or governing SPEC. Source locators such as an authored step number or `[checkN]` stay in `text` and `origin`; they
are not part of G and must not appear in `assertion.value`. Do not infer `value` from device output, a prior
execution, or a precedent. If the source description, observation method, and natural-language expectation are
complete but no typed F/G exists yet, set `assertion` explicitly to `null`, `source_status` to `complete`,
`typed_assertion_status` to `pending`, and keep `scenario2` null; the author stage compiles it and this stage
must not guess a tuple.

Include the primary expectation here too; downstream uses this array instead of collapsing multiple siblings into
the scalar field. When one leaf block contains multiple `[checkN]` atoms, emit one array item per atom in source
order, and never collapse the multi-atom leaf into the scalar. Keep an unresolved executable assertion null
instead of copying prose into a regex. The projector assigns stable IDs and source locators; do not invent either.

## `steps` and `adapted_steps`

[R44] `steps` — the ordered, complete closure of authored action atoms as `{n, text}`. Do not drop, truncate,
reorder, duplicate, or merge an atom. `n` is its authored locator; unnumbered multi-line case-body actions use the
1-based source-line position assigned during splitting.

`adapted_steps` — the same steps after adaptation as `{n, text, basis}`, one per authored step in the same order
(`steps[]` stays sealed). The adaptation rules are in `adaptation.md`; an unchanged step repeats its text with an
empty `basis`.

`step_structure` — one entry per authored step beside it; the contract is in `step-structure.md`.

## `adaptation_notes`

[R45] Complete authored title/step/expectation atoms from the same case that contain environment-specific values
and will need mapping later (concrete IPs, ports, protocol family, device counts). Copy the whole source atom,
including negation, conditions, and locator text; a shortened span can reverse its meaning and is rejected, so
every array item must equal one complete source atom byte-for-byte. Put explanations, typo observations, and
normalization commentary in `proposal` or the report, never in `adaptation_notes`. Do not add, split, or preserve
an expected claim here when it is absent from `expectations_by_step`. **Record, do not resolve or paraphrase.** In
the case-body/leaf-expectation layout, all numbered actions live inside one autoid-node text atom. A split step
line is not a standalone source atom for this field: either copy the entire autoid-node body exactly once or omit
it. Never place the split line fragments in `adaptation_notes`.

## Cases that read alike

[R46] Two cases can carry byte-identical bodies and differ only by the group node they sit under — the author put
the whole distinction in the tree, and the engine fills `group_path` from the sealed source, so it is already
correct and you never restate it anywhere. What you must not do is flatten it: keep each case's own contract, do
not merge them, do not paraphrase one to make it look different, and do not invent a difference the tree does not
carry. When the tree gives no distinction either (same body, same group), emit both as they are — a duplicate the
author wrote is the author's to resolve, not yours to disguise.

## `proposal`

[R6] If a field cannot be filled verbatim from either source, leave it `null` and add a `proposal` entry describing
the missing signed declaration. A proposal may request a new identified `Author`, `Spec`, `Manual`,
`ConfigBinding`, or `CapabilityXml` declaration. Never request an observed device output as the expected value:
device output is `actual` only and cannot sign `expected`. `proposal` is user-facing disclosure, not a terminal
credential. Its JSON shape is an array of non-empty plain strings; never emit proposal objects, nested arrays, or
machine status inside it.

## Two status axes and `scenario2`

[R32] Use two independent status axes for every case:

- `source_status` is `complete` only when description/intent, the complete authored step list, and a
  natural-language expected criterion are present; otherwise it is `incomplete`. The verification method is
  outside this axis.
- `typed_assertion_status` is `ready` when every expectation already has a legal typed F/G and `pending` when the
  complete source still needs author-stage F/G compilation.

Only a `source_status: incomplete` case may emit a structured `scenario2` proof; a complete case has
`"scenario2": null`, even when its typed assertion is pending. An incomplete case emits one `scenario2` object with
exactly `reason_code`, `missing_fields`, `spec_status`, `defect_spec_status`, and `defect_spec_receipt_sha256`.
Never omit those keys or replace JSON null with an empty string.

- `reason_code` is `missing_case_description_steps_or_expectation`.
- `missing_fields` lists only the exact missing source fields from `intent`, `steps`, and `expectation`. Never
  include `assertion`: typed pending is a compiler state, not source incompleteness.
- [R33] `spec_status` is `no_governing_spec` only when `cex_recompose_prepare` reported
  `governing_spec.status = no_governing_spec`; it is `checked_no_static_declaration` only after the bound SPEC
  file was read and supplied no declaration. Copy `ambiguous` unchanged, because that state maps to Absent.
- `defect_spec_status` and `defect_spec_receipt_sha256` are copied exactly from `cex_recompose_prepare`
  (`not_queried`, `no_ticket_reference` or `resolved_absent`; the receipt is null in this client).

The engine recomputes `source_status`, `typed_assertion_status` and the spec identity, never `bucket`. A partial
tuple without a valid structured proof is invalid output, not proof that the sources are incomplete. A valid
Scenario 2 case is not compiled: the compile step reports it to the user as abandoned for an incomplete source.
