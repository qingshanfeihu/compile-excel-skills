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
catalogue. The catalogue is closed: pick one of its names, do not invent a type and do not refuse
to choose. What each type lets the author stage write is fixed by its assertion slots
(`references/authoring.md`, "Read the card first"), so type by what the wording asks to observe.
The labels are the ones the engine shows the user:

| `criterion_type` | engine label | wording it fits |
|---|---|---|
| `reachability` | 能不能连上 | 「访问成功」「访问失败」 |
| `status_value` | 状态对不对 | 「配置成功」「无法添加」「生效」; a numeric bound, rate, ratio or threshold read as a value from an observed line |
| `content_match` | 内容对不对 | text that must appear in an output |
| `absence` | 没有出现 | text that must not appear |
| `count` | 出现几次 | an exact occurrence count (see below) |
| `distribution` | 怎么分布 | how traffic spreads over members |
| `before_after` | 改前改后对不对 | the same observation before and after a change |

`count` (「出现 N 次」) exists in the catalogue, but no mechanical case can redeem it today: its only
slot is `[OBSERVE_ASSERT, found_times]` and OBSERVE_ASSERT accepts only `found` / `not_found` /
`abs_found`. A shape typed `count` blocks every case that carries it. Choose it only when the
wording asks for an exact occurrence count and nothing else fits, and then tell the user those
cases cannot be authored until the engine redeems `count`.

When the shape carries `behaviour_classification`, it lists the algorithm methods the case
states, the object kind each configures, the closed set of behaviour classes, and the
documentation paragraphs the engine found. Answer it in `behaviour_classes`: one row per listed
(method, object kind) whose paragraphs state the behaviour, as
`{"method", "object_kind", "behaviour_class", "source_path", "quote"}`: `method` and `object_kind`
copied from the request (`object_kind` empty when the request has none), `behaviour_class` one
class from the offered set, `source_path` the documentation file of the paragraph you used, and
`quote` that paragraph verbatim. Omit a (method, object kind) whose paragraphs do not state the
behaviour (the engine records it as unclassified); `unclassified` is not an offered class. The
engine checks each row against the closed set and the documentation bytes; a row that does not
check out is recorded as unclassified too.

Record the judgement with `cex_criterion_record`:

```json
{"out_name": "<batch>", "shape_key": "<shape_key>",
 "judgment": {"criterion_type": "<one catalogue name>",
              "rationale": "<English reasoning grounded in the brief>",
              "disclosure": "<one Chinese sentence for the user>",
              "manual_anchor_ids": ["<optional, from the brief>"],
              "tree_context_ids": ["<optional, from the brief>"],
              "behaviour_classes": [{"method": "<from the request>", "object_kind": "<from the request>",
                                     "behaviour_class": "<one offered class>",
                                     "source_path": "<documentation file>",
                                     "quote": "<the paragraph, verbatim>"}]}}
```

`criterion_type`, `rationale` (English) and `disclosure` (Chinese) are required;
`manual_anchor_ids` and `tree_context_ids` are an optional self-check (the engine binds its own
allowlists and corrects an absent or invalid citation without changing your judgement), and
`behaviour_classes` is only for a shape that asks for it. Those six are the only judgement keys:
no operator, expected value, regex, command or assertion; any other key is rejected (the brief's
own identity keys `schema`, `brief_sha256`, `shape_key`, `version_family` are ignored). Your
authority is only verdict wording → criterion type; expected values stay signed by the sources on
the contract card.

The disclosures written to `author_disclosures.json` say how each verdict was typed, including the
criteria typed from the shared ledger. No tool in this client vetoes or re-adjudicates a recorded
criterion. When the user disagrees with one, keep authoring against the card as it is, and put the
objection in your report: the case, the expectation, the criterion type and the reason the user
gave.
