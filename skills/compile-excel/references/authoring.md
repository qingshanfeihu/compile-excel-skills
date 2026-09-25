# Authoring mechanical cases (block language)

A mindmap batch compiles through the engine's authoring stage: every case gets a **contract
card** (the author's expectations, each with an engine-adjudicated criterion type), you write one
**mechanical case** per card in the block language, and the engine gates, seals and expands it.
You never write workbook rows for these cases; `cex_author_emit` produces them from the sealed
cases with the engine's own expansion.

```
cex_recompose_seal ─► cex_bed_lease acquire ─► cex_bed_topology ─► cex_author_prepare
      (pending shapes? ─► cex_criterion_record, see criterion.md)
  per case: read the card ─► write blocks ─► cex_author_submit_case ─► fix every violation ─► resubmit
  ─► cex_author_emit ─► cex_scan_destructive ─► scripts/run_device.py
```

## Read the card first

`cex_author_prepare` returns, per case: `title`, `group_path`, `author_steps` (the author's
procedure, verbatim), `step_structure` (the objects each step creates or references), and
`expectations`. Each expectation carries:

| field | meaning |
|---|---|
| `expectation_id`, `semantic_key` | identities you copy byte-for-byte onto the assertion that redeems it |
| `text` | the author's verdict, verbatim (e.g. 访问成功, 无法添加) |
| `criterion_type` | what kind of evidence the engine requires (e.g. `reachability`, `status_value`) |
| `allowed_block_kinds`, `allowed_operators` | the only block kinds / assertion operators that may redeem it |
| `claim_kind` | `Author` for mindmap text; goes into `expectation_binding[].claim_kind` |

Every card expectation must be redeemed by exactly one assertion, and every assertion you write
must redeem a card expectation (the engine checks the bijection). Do not add assertions for things
the card does not claim, and do not drop one because it looks hard.

The prepare result also carries `bed.summary`: the engine's own reading of this bed. Take every
address from it:

- **VIP / listener**: only addresses under ★ (the APV interfaces a trigger host can reach).
- **trigger host** for traffic: the host paired with that VIP under 「触发机配对」, lowercase
  (e.g. `routerb`). The wrong segment never reaches the VIP.
- **real servers**: the backend addresses listed under 后端服务器真实 IP.
- The author's example addresses (e.g. 181.x) are usually unreachable on this bed. Bind them to
  bed addresses and say so in the block's `desc` (「作者地址 X 按本测试床绑定为 Y」); keep the author's
  object names and the number of objects exactly as written.

## The submission body

One JSON object with exactly these keys (no `seal`):

```json
{"schema": "ist.mechanical-case", "autoid": "<18-digit autoid>",
 "description": {"intent_verbatim": "<card title>", "group_path": ["<card group_path>", "..."]},
 "binding": {}, "init_commands": [],
 "blocks": [ ... ],
 "expectation_binding": [ ... ],
 "escape_hatches": []}
```

- `binding` is always `{}`: the engine stamps the contract, mindmap and command-tree identities.
- `init_commands` stays `[]`: create what the case needs inside its own blocks.
- A rejected submission changes nothing; resubmit the **complete** body after fixing **every**
  listed violation (each one names the gate, the locus like `blocks[3]`, and a `legal_form`).

## Block kinds

Hosts: the device under test is `APV_0` (`APV_1` for the second device). Traffic runs from a bed
host (`routera`, `routerb`, `clientc`, …) named exactly as in `bed.summary`.

### CONFIG — device configuration

```json
{"kind": "CONFIG", "host": "APV_0", "cmds": ["slb virtual httplist vs3 addlist1 port1"],
 "desc": "创建HTTP类型LIST虚拟服务vs3", "ref": "manual:10.5.0/cli_cn.md:10868"}
```

`cmds` holds whole commands, one per element; commands in one block share `ref`, so split
blocks whose commands are documented in different places. `ref` is where the command is
documented: `cex_lang_query` with `{"kind": "param", "name": "<command head>"}` prints the
locator (`manual:<version>/cli_cn.md:<line>`) above the command's manual text. Check that every
command exists on this build with `cex_cmd_check` before submitting.

### OBSERVE_EXIT — traffic verdicts (reachability: 访问成功 / 访问失败)

```json
{"kind": "OBSERVE_EXIT", "host": "routerb", "cmd": "curl -s -o /dev/null --max-time 8 http://<VIP>:80/",
 "expect": "success", "answerer": {"kind": "device", "ref": 5},
 "expectation_id": "<from the card>", "semantic_key": "<from the card>",
 "desc": "从routerB访问虚拟服务<VIP>:80，预期访问成功"}
```

- `expect: success` asserts exit status 0 (the probe completed an exchange);
  `expect: failure` asserts one of the probe tool's transport-failure codes (no answer). An
  answered refusal (HTTP error page) is reachability, not failure.
- `cmd` is one direct command whose exit status is not masked: no pipes, `;`, `||`, `&`,
  command substitution. For `expect: failure` the target must be an IP literal.
- `answerer` names who answers: `{"kind": "device", "ref": <index of the CONFIG block that
  creates the answering virtual service>}`.
- HTTPS: `curl -k -s -o /dev/null --max-time 10 https://<VIP>:443/`, and load certificates with
  `SSL_CERT_LOAD` first.
- The engine renders this as a `test_env` row plus an `IST_EXIT_STATUS` check_point; do not
  write those rows yourself.

### OBSERVE_ASSERT — output checks on the device (configuration / display verdicts)

```json
{"kind": "OBSERVE_ASSERT", "host": "APV_0", "cmd": "show slb virtual addrlists addlist1",
 "cmd_ref": "manual:10.5.0/cli_cn.md:10818",
 "asserts": [{"op": "not_found", "pattern": "<the new address, regex-escaped>",
              "expectation_id": "<from the card>", "semantic_key": "<from the card>",
              "ref": "intent:<expectation_id>", "desc": "新地址未被加入"}],
 "desc": "查看地址集合，确认新地址未被加入"}
```

- `op` is one of the card's `allowed_operators` (`found` is a regex, `abs_found` a literal,
  `not_found` its negation).
- `ref: "intent:<expectation_id>"` cites the author's claim as the expected-value source.
- The pattern must match only a data line, never the command echo itself.
- A value that cannot appear in the command line that caused it (a state change) needs
  `expectation_binding[i].state_change_step` + `binding_disclosure` (see the gate's legal form).

### SSL_CERT_LOAD — certificates for an HTTPS virtual service

```json
{"kind": "SSL_CERT_LOAD", "host": "APV_0", "vhost": "<ssl host name>", "vhost_role": "virtual",
 "bound_object": "<the httpslist virtual service name>"}
```

Put it after the block that creates the virtual service and before the first HTTPS
observation. Leave every certificate field out: the engine binds the certified release fixture,
creates the SSL host, imports root CA / key / certificate, starts the host, and schedules its
own cleanup after your last assertion. It emits no assertion and cannot be the target of an
`expectation_binding` or `answerer.ref`.

### SLEEP — wait for a change to take effect

```json
{"kind": "SLEEP", "seconds": 3}
```

### STEP — a raw workbook row no combinator expresses

`{"kind": "STEP", "E": "<object>", "F": "<method>", "G": "<data>", "desc": "…", "ref": "…"}`, with
E/F from the Excel function contract. Every STEP needs an `escape_hatches` entry:
`{"block_index": <i>, "capabilities_touched": ["<F>"], "reason": "<why no combinator fits>"}`.
Prefer the combinators above; a STEP is the exception you have to justify.

## Expectation binding

One entry per card expectation, pointing at the assertion that redeems it:

```json
{"expectation_id": "<card>", "semantic_key": "<card>", "claim_kind": "Author",
 "block_index": 9, "assert_index": null, "scope_ref": null,
 "state_change_step": null, "binding_disclosure": null}
```

`assert_index` is the index inside `asserts[]` for OBSERVE_ASSERT, `null` for OBSERVE_EXIT.
When several expectations share one `semantic_key`, the gate may ask for `scope_ref`; copy it
from the source it names.

## Order and teardown

1. Configure what the author's steps configure, in the author's order, with the author's object
   names (the gate counts every authored command occurrence: `authored_command_occurrence_missing`
   means an author step never ran).
2. Observe and assert after the action that produces the result.
3. Restore: after the last assertion, undo every object the case created with the build's paired
   inverse (`no slb policy default …`, `no slb virtual httplist …`, `no slb group member …`,
   `no slb group method …`, `no slb real …`, `no slb virtual portlists …`,
   `no slb virtual addrlists …`), dependents first. `missing_teardown` names the ones you left.
   SSL_CERT_LOAD cleans up after itself.

## Reading a rejection

Fix the locus the violation names, keep everything else, resubmit the whole body. Common ones:

| code | fix |
|---|---|
| `trigger_reachability_invalid` | VIP not in ★, or the trigger host is not the one paired with it |
| `environment_unreachable_ip` | an address that is not on this bed; take one from `bed.summary` |
| `expectation_bijection_failed` | a card expectation has no assertion, or an assertion redeems none |
| `criterion_binding_missing` / `criterion_lowering_mismatch` | the redeeming block kind / operator is not in the card's allowed list |
| `missing_teardown` | add the paired `no …` restore for every object the case created |
| `authored_command_occurrence_missing` | an author step's command is missing from the blocks |
| `https_certificate_setup_missing` | add `SSL_CERT_LOAD` for the HTTPS virtual service |
| `provenance_source_unresolved` | a `ref` / `cmd_ref` does not resolve; take it from `cex_lang_query` |

The same rejection code twice in a row on an unchanged shape means your model of the rule is
wrong: re-read the violation's `detail` and `legal_form` instead of resubmitting.
