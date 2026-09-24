# `step_structure`

[R27] Every authored step carries one `step_structure` entry beside it — `{n, objects, operations,
stated_conditions, free_slots}` — and the verbatim step stays the authority for what the author wrote. The entry
is that step's structure, stated once here where the source and the specification are both in front of you, so
the compile and fidelity stages read a structure instead of rebuilding one from prose. A step whose structure you
cannot state still carries its entry with empty arrays, which makes the gap visible rather than silent.

- [R28] `objects[]` is `{kind, role, count}` for what the step brings into being, configures, watches, deletes, or
  only names. `kind` is the command-tree path of the head that creates or configures that object, with the
  leading operator word and the trailing action segment dropped: a head recorded at `global/<a>/<b>/<leaf>` gives
  `<a>/<b>`. `role` is one of created, configured, observed, deleted, referenced. `count` is the number the step
  states, or JSON null where it states none. A step that only watches, or that removes something and then samples,
  is the step an observation belongs to; a step that builds or configures is not.
- [R29] `operations[]` is `{head, ref}`, and `head` must already appear in this case's `command_check`. An
  ungrounded head inside the structure is a command nobody checked, so the engine matches normalized and rejects
  one that is not there. `ref` names where the operation comes from, in the same locator form as `origin`.
- [R30] `stated_conditions[]` is `{text, kind, value, author_text}` for each constraint that step states after
  adaptation: the algorithm, the record or protocol type, an attribute, a count, an ordering, the bucket weights.
  `text` is stated out of that step's own adapted text (`adapted_steps[n].text`; the authored text when the case
  carries no adaptation), `kind` is one of algorithm, type, attribute, count, order, weight, other, and `value` is
  the literal the adaptation states. `author_text` names the span of the author's original words this condition
  corresponds to: the engine grounds it against the sealed `steps[n].text` with whitespace runs normalized, so
  small whitespace differences are corrected rather than rejected — point at the author's actual words and never
  retell them; for a step you did not adapt, omit `author_text` (the engine takes `text`, which already is the
  author's words). `weight` is the kind for the per-bucket shares a weighted algorithm distributes by, `count`
  for how many of something the step states; the engine reads a single integer as a count and the weight kind as
  the bucket shares, and never infers one from the other. A bare quantifier word standing for a count is not a
  value: let `objects[].count` carry the number instead of restating it as a condition, and a default a tool
  already satisfies (the transport a command uses unless told otherwise) needs no condition at all.
- [R31] `free_slots[]` is `{slot, ref}` for a quantity the author left open. The value lives once, at the target of
  `ref`: `concretizations[<i>]` for a witness you chose. When a step changes which buckets remain — the author
  removes one of the weighted pools, say — the weights in force after it are not a literal anywhere in the source,
  so they cannot be a stated condition: record them as a concretization with `slot` `effective_weights`, its value
  the remaining shares, its reason saying which step changed them, and point that step's free slot at it. After
  your submission passes, the engine appends its own rule-derived records under `engine_slots`, one per
  distribution criterion, and points a slot at them; never propose that one yourself. A value the author did
  write is a stated condition, not a free slot.

Which objects and conditions a step has is your judgement. The three closed sets, the byte-for-byte condition
text, and the head-already-grounded rule are not: a rejection names the entry, the field and the legal form, and
you repair that case and submit it again.

When the command tree is unavailable in this workspace (see `command-grounding.md`), the engine cannot check
`objects[].kind` against the tree and accepts any non-empty path; state the path from the command head you
grounded with `cex_cmd_check`, and leave `operations[]` to heads recorded in `command_check`.
