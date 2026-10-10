# Case object shape

One element of the `cases` array passed to `cex_recompose_submit_cases`. Do not print it as the reply; only the
tools record it. Top-level artifact fields (`schema`, `source`, `governing_spec`, `defect_spec_status`,
`defect_spec_receipt_sha256`, `case_count`) are filled by `cex_recompose_seal` from the prepared dispatch.

```json
{
  "autoid": "202609240000000001",
  "group_path": ["<root title>", "<group title>"],
  "title": "<verbatim>", "bucket": "step_recipe",
  "source_status": "complete", "typed_assertion_status": "pending",
  "contract": {"intent": "<verbatim or null>", "verification_method": "<verbatim or null>",
               "expectation": "<verbatim or null>"},
  "origin": {"intent": "title", "verification_method": "expectation:1", "expectation": "expectation:1"},
  "steps": [{"n": "1", "text": "<verbatim>"}],
  "adapted_steps": [{"n": "1", "text": "<the adapted step text; equals steps[1].text when nothing needed adaptation>",
                     "basis": "<why the adaptation preserves the authored scenario; empty when unchanged>"}],
  "step_structure": [{"n": "1",
                      "objects": [{"kind": "<command-tree object path>", "role": "created", "count": 3}],
                      "operations": [{"head": "<head already in command_check>", "ref": "step:1"}],
                      "stated_conditions": [{"text": "<substring of adapted_steps[1].text>",
                                             "kind": "algorithm|weight|count|type|attribute|order|other",
                                             "value": "<the literal the adaptation states>",
                                             "author_text": "<span of steps[1].text this condition corresponds to>"}],
                      "free_slots": [{"slot": "<name>", "ref": "concretizations[0]"}]}],
  "expectations_by_step": [{"n": "1", "text": "<verbatim expectation>", "origin": "expectation:1",
                            "assertion": null}],
  "command_check": [
    {"command": "<head verbatim from the mindmap>", "in_vendor_tree": true, "in_manual_only": false,
     "arg_count_ok": true, "note": ""},
    {"command": "<another head, this one absent>", "in_vendor_tree": false, "in_manual_only": false,
     "arg_count_ok": null, "note": "The head is absent; a near head exists, but the source text was not rewritten."}
  ],
  "depends_on": null, "rebind_licenses": [], "concretizations": [],
  "adaptation_notes": ["<complete authored atom containing values that need mapping>"],
  "proposal": [], "scenario2": null, "consistency": null
}
```

An incomplete case carries a `scenario2` object instead of `null` (`case-fields.md`):

```json
{"reason_code": "missing_case_description_steps_or_expectation", "missing_fields": ["expectation"],
 "spec_status": "no_governing_spec", "defect_spec_status": "no_ticket_reference",
 "defect_spec_receipt_sha256": null}
```

A judged case carries an `ist.recompose-consistency` object instead of `null` (`consistency.md`).
