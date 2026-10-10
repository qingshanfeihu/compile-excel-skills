# Grounding authored commands against the product command tree

[R21] `command_check` is diagnostic output only; the engine independently recomputes command existence from the
current vendor projection — never treat this field as an authority receipt. This diagnostic closure is never
authority over Author, Spec, DefectSpec, Manual, ConfigBinding, or CapabilityXml claims.

## Tools

- `cex_lang_query` with `out_name` — the build-bound supply the compile engine uses. `kind=param name=<head>` returns
  the per-argument XML contract with the manual explanation beside it; `kind=complete name=<partial head>` lists a
  bounded set of matching heads; `kind=docs query=vendor_manual` names the versioned CLI/app manuals. File paths in
  its `result` are relative to the `data_root` it returns. Passing `out_name` records the lookups for that batch.
- `cex_cmd_check commands=[...]` — whether each command exists on this build and whether its arguments fit the
  recorded contract, read straight from the synced projection with the engine's own judgment. Each result carries
  the resolved `head` and its command-tree path `src` (`vendor_xml:<build>:global/<a>/<b>/<leaf>`), which is also
  what `step_structure` object kinds are derived from.

The command tree needs its source XML beside the projection before the engine will read it through
`cex_lang_query`. When a `cex_lang_query` answer says the vendor command-tree projection "could not be loaded", the
synced bundle carries the projection without that XML: do not retry the query. Ground existence and arguments with
`cex_cmd_check`, read the wording in the current build's locally synced manual files (`kind=docs` still names them) or search them with `cex_docs_query` (server document hits are marked separately and have no manual ref), and
say in the report that per-argument contracts were unavailable.

## Procedure

[R16] When the source already gives an exact command head, call `kind=param` directly: that result already reports
exact-tree resolution and the per-argument/manual claims. Do not call `kind=complete` before `kind=param` for the
same exact head. Use the bounded `kind=complete` result only when the authored head is partial or ambiguous. Before
every query, reuse an identical `(kind, name, domain, query)` result already present in this run, and record every
result used for a case in that case's `command_check` before recording the case. `cex_cmd_check` takes the whole
list of a case's commands in one call.

[R19] A command line is `<head> <args…>` and you do not know where the head ends, so try the **longest prefix first**,
dropping one trailing word per attempt until a head resolves; the words you dropped are the author's arguments
(`cex_cmd_check` does this resolution itself and returns the head it found). If no prefix resolves, the command is
not in the tree — a real finding, not a failed search; some such lines are not product CLI at all but backend shell
utilities, so say which it looks like and why.

[R17] When a case creates or changes a typed service path, ground the type relation across endpoint, intermediary
group/policy, and real/backend declarations from XML/manual; head existence and arity alone do not prove whole-path
compatibility.

[R18] When the author wrote a product action in prose (no exact head), do not invent a verb and feed it to
`kind=complete`. Once per run, `cex_lang_query(kind="docs", query="vendor_manual")` names the versioned CLI/app
manuals; grep the author's object words for the signature line (`**cmd**`), read a window around that hit (do not
page the whole manual), then `kind=param` or `cex_cmd_check` on the documented head. Grep prints hits as
`path:line: content` — the space after the line number is grep's own decoration, not a file byte: anchoring `^` at
it matches nothing, so anchor at the command's literal `**` or skip the anchor. The manual is what the product is
documented to do; the command tree decides existence and spelling for this build. If they disagree, report the
disagreement and keep the tree spelling. A truncated `complete` inventory is also tree fact, not a ranking — pick a
documented token from it rather than minting a new English verb. One complete (only while the head is still
partial) + one manual grep + one param per concept is enough; a miss is `in_vendor_tree: false`, not a reason to
guess another verb.

## `command_check`

[R52] For each distinct command referenced anywhere in the case (steps and verification method), record:

- `command` — the head you resolved, verbatim from the mindmap;
- `in_vendor_tree` — true/false (from `cex_lang_query kind=param`, or `cex_cmd_check` returning a non-empty `head`);
- `in_manual_only` — true only when the tree lacks the head while the manual carries it;
- `arg_count_ok` — the author's argument count against the per-argument contract, or `null` when no head resolved.
  A `cex_cmd_check` result with `reason_code: parameter_contract_violation` fails the contract; its
  `parameter_error` says whether that is the count or a type/value-domain problem — record `false` for a count
  problem and name any other problem in `note`;
- `note` — one short sentence when something is off, including which tool the answer came from when
  `cex_lang_query` was unavailable.

[R20] **Do not repair anything.** When the author wrote an abbreviated head and the tree only carries the spelled-out
one, record `in_vendor_tree: false` plus a note naming the near head. You do **not** rewrite the contract to the long
form — that is the author's call, and silently "fixing" it is exactly the invention this skill forbids. Same for
argument counts: report the mismatch, keep the text.

If neither tool can answer (no command-tree projection in the synced bundle), emit an empty `command_check` array and
report that grounding was deferred. Do not turn that missing diagnostic into a case gap or a proposal: the contract
comes from Author/SPEC text, while command existence is judged again before compiling.
