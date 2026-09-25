# Criterion adjudication (only when cex_author_prepare stops at `criterion_pending`)

The engine types every expectation of a contract card: which kind of evidence can decide
「访问成功」, 「无法添加」, 「配置成功」…. Known verdict shapes are answered from the synced criterion
ledger. A shape nobody has typed yet stops `cex_author_prepare` with `pending_shapes`; you type
each one, the engine re-checks and records your judgement in the ledger, and after the last one it
publishes the contract cards. This is the engine's own adjudication step (InfoTest runs it as the
criterion-adjudicator), with you as the adjudicator.

For each pending shape, read the brief file at `brief_path`. It is one engine-bound JSON brief:
the shape's claims (the verbatim verdict wording and the cases it occurs in), the closed
catalogue `criterion_types`, the grounded manual anchors, and the case / sibling tree context.
These are the only admissible evidence; do not search for precedent, earlier workbooks, device
output or anything else.

Translate the shape's verbatim verdict wording into exactly one `criterion_type` copied from the
catalogue. The catalogue is closed: pick one of those names even when the wording is a numeric
bound, rate, ratio or threshold comparison (those still land on an existing type such as
`count`, `status_value` or `content_match`). Do not invent a type and do not refuse to choose.

When the shape carries `behaviour_classification`, it lists the algorithm methods the case
states, the object kind each configures, the closed set of behaviour classes, and the
documentation paragraphs the engine found. Answer per entry which class the documentation states,
quoting the paragraph that says so; omit an entry whose paragraphs do not state the behaviour
(the engine records it as unclassified). `unclassified` is not an offered class.

Record the judgement with `cex_criterion_record`:

```json
{"out_name": "<batch>", "shape_key": "<shape_key>",
 "judgment": {"criterion_type": "<one catalogue name>",
              "rationale": "<English reasoning grounded in the brief>",
              "disclosure": "<one Chinese sentence for the user>",
              "manual_anchor_ids": ["<optional, from the brief>"],
              "tree_context_ids": ["<optional, from the brief>"]}}
```

`criterion_type`, `rationale` (English) and `disclosure` (Chinese) are required; the citation
lists are an optional self-check (the engine binds its own allowlists and corrects an absent or
invalid citation without changing your judgement). No other keys: no operator, expected value,
regex, command or assertion. Your authority is only verdict wording → criterion type; expected
values stay signed by the sources on the contract card.
