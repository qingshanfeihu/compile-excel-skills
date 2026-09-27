# Adaptation and enhancement

Three bed-agnostic side records: `adapted_steps[]`, `concretizations[]`, `rebind_licenses[]`. The sealed fields
(`steps`, the contract triple, `expectations_by_step`) stay verbatim; no bed values; every choice carries its
reasoning, which is disclosed to the user beside the original.

## `adapted_steps`

[R2] **Adaptation lives only in `adapted_steps[]`; the sealed fields stay verbatim.** It rewrites a step into the
equivalent executable form this bed can run and stays inside the authored semantics. What it is for:

- an author-penned deploy literal this bed cannot reach becomes a concrete reachable value of the same address
  family — the same author literal keeps one value everywhere and two distinct author literals never become the
  same value (the submission checks both mechanically for address literals; `load_bearing` literals stay as
  written);
- a role label that stands for an address (a bond-interface IP, an HA floating IP, a system IP) resolves to the
  concrete value the group path and the concretizations/manuals support;
- a protocol or type word is rewritten only where the case's own text leaves one reading standing — the authored
  word is in no command tree at all, or no other authored surface backs it. Where two authored surfaces each back
  a different word (a grouping or title naming one behaviour, a step configuring another, an authored quantity
  that fits only one of them), the evidence is symmetric: which one is the slip is an authority call this stage
  does not hold, and adapting one away hands the engine a value the author never stated. Keep both authored words
  where the author put them and declare the pair under `consistency.authored_conflict`;
- a bare quantifier word standing for a count stops being a value and lets `objects[].count` carry the number;
- a tool-default the author left implicit (the transport a command uses unless told otherwise) is not restated as
  a matching condition.

Never drop a negation, a condition, a stated difference, or a command the author wrote — adaptation may change a
command's arguments, never remove the command — and never add an object or action the author did not write.
`basis` says, per step, why the adaptation preserves the authored scenario. An unchanged step repeats its text with
an empty `basis`.

## `concretizations`

[R9] An executable process slot that the author leaves ambiguous or absent (including a protocol pair or port
choice) must not silently pass through. Choose and record a concrete witness when the command tree/manual supports
at least one value that preserves the authored behavior; multiple equivalent supported witnesses are not a reason
to stop. Use `proposal` only when no supported witness can preserve the test point. This is semantic accounting,
not a keyword gate. A parameter domain establishes accepted syntax, not object coexistence, update behavior, or
operational prerequisites; those claims need their own version-bound source support. Descriptive conditions after
a command head do not become literal argument values. Preserve explicit literal-value and invalid-input test
points when choosing an open slot.

[R7] Each `concretizations[]` item has exactly `{slot, author_text, value, source, reason}`, where `source` is
`command_tree` or `manual` and `author_text` is a span of the authored steps the engine grounds with whitespace
runs normalized. `reason` ties the witness to the expected contrast.

[R10] When the authored expectation contrasts two outcomes (「使用对应协议访问可成功，使用原有协议访问失败」,
「使用原portlist访问失败，使用新port访问成功」), the witness has to let the negative arm fail **because of the authored
difference**, observed the way the compile stage observes it:

- Everything the author did not change stays equal between the two arms (address, port, trigger host, backend);
  only the authored difference varies (the protocol, the portlist, the deleted object). A witness under which the
  negative arm fails for a reason the author did not write fails by construction and verifies nothing: the
  recreated object placed on another port or address although the author changed only its protocol. When the port
  is the authored difference (「使用原portlist访问失败」), the old port going silent is the test point.
- Traffic verdicts — 「访问成功」「访问失败」, including 「使用原有协议访问失败」「使用原portlist访问失败」 — are observed as a
  probe's exit status (OBSERVE_EXIT at the compile stage), also when the contract card types them `status_value`.
  「访问失败」 is a transport-level failure: the engine accepts only the probe tool's documented transport-failure exit
  codes (domain grammar `probe_tools.transport_failure_exit_codes`: curl 7 and 28, wget 4, nc and ncat 1, ping 1,
  dig 9). An answered refusal is reachability: an HTTP error, or an empty reply or TLS alert after a service accepted
  the connection (an HTTP request sent to an HTTPS listener), can never be the failing arm.
- So the witness is a value under which the authored change itself leaves the original request unanswered at the
  transport level, everything else kept (for a protocol change: a replacement type that no longer accepts the
  original transport on that address and port), while the request of the new arm is answered.

A value that makes the negative arm succeed by construction, or fail for a reason other than the authored
difference, still satisfies the command tree while destroying the test point, and the run then reads on-device as
the device contradicting the author (or passes without testing anything). Say in `reason` why the chosen witness
keeps the contrast falsifiable and caused by the authored difference. When no supported witness can do that, record
a `proposal` instead of a witness (R9).

The compile stage receives these witnesses on each contract card (`concretizations`) and builds the mechanical case
with them. Once every dispatched case is recorded, submission closes and a recorded case cannot be replaced, so
choose each witness for its contrast before recording the case.

## `rebind_licenses`

For an author-penned deploy literal whose reachability this stage cannot know, judge only load-bearing-ness. Each
`rebind_licenses[]` item has exactly `{author_literal, verdict, occurrences, constraints, reason}`; `verdict` is
`rebindable|load_bearing`. Quote the author's original bytes in `author_literal`, including the original IP rather
than any later bed substitution; `occurrences` is a list with one step locator per place the literal appears
(`["step:1", "step:3"]`, the same locator twice when a step holds it twice), never a count; `constraints` states
shape and cross-occurrence consistency.

Under the rewrite regime the license is disclosure, not a value channel: a `rebindable` literal is turned into a
concrete reachable value of the same address family inside `adapted_steps` (two distinct author literals never
become the same value). That replacement is the rewrite, not a submission-gate hard reject — leftover rebindable
bytes are not refused at the seal. `load_bearing` keeps the literal in the adapted text too. If the test point is
that the address stay unreachable, keep the literal and state that relation in `constraints`. Never insert a target
slot, role label, or replacement value inside the license itself. These are setup facts, never expected-value
authority. Ports, protocols, request shapes, and object names are process concretizations, never rebind licenses.

[R8] `load_bearing` asks whether the exact authored literal value is itself the test point. A required
equality/inequality pattern does not make the numeric literal load-bearing: when the bytes may change while that
relation must remain, emit `rebindable` and state the relation in `constraints`.
