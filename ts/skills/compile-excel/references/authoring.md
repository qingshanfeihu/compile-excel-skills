# Authoring mechanical cases (block language)

A mindmap batch compiles through the engine's authoring stage: every case gets a **contract
card** (the author's expectations, each with an engine-adjudicated criterion type), you write one
**mechanical case** per card in the block language, and the engine gates, seals and expands it.
You never write workbook rows for these cases; `cex_author_emit` produces them from the sealed
cases with the engine's own expansion.

```
cex_recompose_seal ─► cex_bed_lease acquire ─► cex_bed_topology ─► cex_author_prepare
      (pending shapes? ─► cex_criterion_record, see criterion.md)
  per case: read the card ─► write blocks ─► cex_author_submit_case
            ─► fix every violation / resolve or note every advisory ─► resubmit
  ─► cex_author_emit (ok: true) ─► cex_scan_destructive ─► run_device.js
```

## Read the card first

`cex_author_prepare` returns, per case: `title`, `group_path`, `author_steps` (the author's
procedure, verbatim), `adapted_steps`, `step_structure` (the objects each step creates or
references), `concretizations`, and `expectations`. Next to the cases it returns `slot_rule`,
`bed`, `blocks_schema` and `disclosures`. Each expectation carries:

| field | meaning |
|---|---|
| `expectation_id`, `semantic_key` | identities you copy byte-for-byte onto every assertion that redeems it |
| `text` | the author's verdict, verbatim (e.g. 访问成功, 无法添加) |
| `criterion_type` | what kind of evidence the engine requires (e.g. `reachability`, `status_value`) |
| `allowed_slots` | the exact `[block_kind, operator]` pairs the gate accepts for this expectation |
| `claim_kind` | `Author` for mindmap text; goes into `expectation_binding[].claim_kind` |
| `authored_step` | the author's step this verdict belongs to |

A slot is the block an `expectation_binding` entry points at plus its operator: `asserts[i].op`
for an OBSERVE_ASSERT, the `F` of a STEP, `""` for every other kind. Only the listed pairs pass
(`criterion_lowering_mismatch` otherwise). The card is authoritative; today's engine table is:

| `criterion_type` | `allowed_slots` |
|---|---|
| `reachability` | `[OBSERVE_EXIT, ""]`, `[OBSERVE_ASSERT, found]`, `[OBSERVE_ASSERT, abs_found]` |
| `status_value` | `[OBSERVE_ASSERT, found]`, `[OBSERVE_ASSERT, abs_found]`, `[OBSERVE_ASSERT, not_found]`, `[OBSERVE_EXIT, ""]`, `[EXPECT_FROM, ""]` |
| `content_match` | `[OBSERVE_ASSERT, found]`, `[OBSERVE_ASSERT, abs_found]`, `[OBSERVE_MEMBER, ""]` |
| `absence` | `[OBSERVE_ASSERT, not_found]` |
| `count` | `[OBSERVE_ASSERT, found_times]` |
| `distribution` | `[OBSERVE_DIST, ""]` |
| `before_after` | `[CAPTURE_COMPARE, ""]` |

`count` cannot be redeemed today: OBSERVE_ASSERT accepts only `found` / `not_found` / `abs_found`,
and a STEP slot is `[STEP, found_times]`, which is not in the pair list. A card expectation typed
`count` cannot be sealed: say so to the user as an engine-side criterion gap; do not force the
nearest operator.

`concretizations` are the witnesses the recompose stage recorded for slots the author left open
(`slot`, `author_text`, `value`, `source`, `reason`; `step_structure[].free_slots[].ref` points into
this list): the port, the protocol pair, the replacement list type. Build the case with those
values. A recorded recompose case cannot be replaced once every case is recorded, so when the bed
forces a different value, write the value you used and why into the block's `desc` and into your
report.

### Every expectation, every object

Every card expectation must be redeemed, and every assertion must redeem a card expectation (the
engine checks both directions). One expectation may occupy several assertion slots, and it must
when the author's claim covers several objects. 「分别关联不同的vslist」「分别访问不同的vslist」 →
「配置成功」「访问成功」 over three vslists: 「配置成功」 gets one configuration assertion per vslist and
「访问成功」 one OBSERVE_EXIT per vslist and port, each assertion carrying the `expectation_id` and
`semantic_key` of the expectation it redeems. Words such as 分别 / 各 / 每 / 三个 name the objects;
checking one of them "as the representative" does not redeem the claim. Do not add assertions for
things the card does not claim, and do not drop one because it looks hard.

### The bed

The prepare result also carries `bed` (the same view `cex_bed_topology` returns): the engine's
reading of this bed as `listener_ips`, `listener_trigger_pairs`, `service_ips`, `services` and the
`summary` text. Take every address from it:

- **VIP / listener**: only addresses under ★ (`listener_ips`, the APV interfaces a trigger host can
  reach).
- **trigger host** for traffic: the host paired with that VIP under 「触发机配对」
  (`listener_trigger_pairs`), lowercase (e.g. `routerb`). The wrong segment never reaches the VIP.
- **backends**: pick them from `services`, the backend services the operator declared on the
  gateway: `{host, ip, proto, port, note}` with `proto` one of `http`, `https`, `tcp`, `udp`,
  `dns`. Choose an entry whose protocol and port fit the real service you configure.
  `service_ips` (后端服务器真实 IP) only says which addresses are backend servers, not what listens
  on them. When `services` lists nothing for the protocol you need (or is empty), do not guess an
  address or a port: tell the user which service (protocol and port) the case needs and that the
  bed facts declare none.
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
- `status: needs_user_decision` means an `answerer` is `undetermined`: nothing was sealed; ask the
  user who answers that observation (see "Who answers").

## Block kinds

Hosts: the device under test is `APV_0` (`APV_1` for the second device); an observation on it runs
as `cmd_config`. Traffic runs from a bed host (`routera`, `routerb`, `clientc`, …) named exactly as
in `bed.summary`; it renders as a `test_env` row with the host lowercased. Every field of every
kind, its domain and the refusal texts are in the file `blocks_schema` names
(`<engine data root>/knowledge/data/compile_ref/blocks_schema.json`, under
`kinds.<KIND>.fields`): read a kind's entry before you use it the first time.

| kind | what it does | assertion identity |
|---|---|---|
| `CONFIG` | device configuration on `APV_0`/`APV_1`: `cmds` (one whole command per element), `ref`, optional `timeout_s` 1-600 | none |
| `OBSERVE_ASSERT` | one observation (`host`, `cmd`, `cmd_ref`) plus `asserts[]` (`op` found / not_found / abs_found, `pattern`, `ref`) | on each `asserts[]` entry |
| `OBSERVE_EXIT` | a traffic probe on a bed host whose exit status is asserted (`expect` success / failure) | on the block |
| `CAPTURE_COMPARE` | `capture_cmd` (baseline, register allocated by the engine), `cmd` (defaults to the same) and `relation` same / differs | on the block |
| `CAPTURE` | one observation stored under `save_as` (your register name, not `v<N>`) for a later EXPECT_FROM | none |
| `EXPECT_FROM` | one observation asserted with `op` against the earlier CAPTURE register named in `expected_from` | on the block |
| `OBSERVE_DIST` | one observation plus a distribution check: `total`, `field`, `buckets[{anchor, expected, tol?, pattern?}]` | on the block |
| `OBSERVE_MEMBER` | one observation plus a membership check: `ips`, `present` (true / false) | on the block |
| `OBSERVE_ONLY` | an observation nothing asserts (drive traffic, fill a rotation) | none |
| `SLEEP` | `seconds`, 1-300 | none |
| `SSL_CERT_LOAD` | the engine's certificate setup for an HTTPS virtual service, with its own cleanup | none |
| `STEP` | one raw workbook row no combinator expresses; needs an `escape_hatches` entry | only when `E` is `check_point` |

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

### OBSERVE_EXIT — traffic verdicts

```json
{"kind": "OBSERVE_EXIT", "host": "routerb", "cmd": "curl -s -o /dev/null --max-time 8 http://<VIP>:80/",
 "expect": "success", "answerer": {"kind": "device", "ref": 5},
 "expectation_id": "<from the card>", "semantic_key": "<from the card>",
 "desc": "从routerB访问虚拟服务<VIP>:80，预期访问成功"}
```

- Traffic verdicts are redeemed here, from the trigger host paired with the target: 「访问成功」
  「访问失败」 and forms such as 「使用原有协议访问失败」「使用原portlist访问失败」「使用新port访问成功」,
  also when the card types them `status_value` (`[OBSERVE_EXIT, ""]` is one of its slots). A
  configuration assertion does not stand in for a traffic verdict.
- `expect: success` asserts exit status 0: the probe completed an exchange with the target.
- `expect: failure` asserts a transport-level failure: nothing answered. The engine accepts only
  the probe tool's documented transport-failure exit codes (domain grammar
  `probe_tools.transport_failure_exit_codes`); any other tool, and an `&&` chain, is refused:

  | probe | exit codes | meaning |
  |---|---|---|
  | `curl` | 7, 28 | could not connect; operation timed out |
  | `wget` | 4 | network failure (refused, unreachable, timed out) |
  | `nc`, `ncat` | 1 | connection could not be established or timed out |
  | `ping` | 1 | no reply |
  | `dig` | 9 | no reply from server |

- **An answered refusal is reachability, not failure.** An HTTP error status, an empty reply or a
  TLS alert after the connection was accepted (an HTTP request sent to an HTTPS listener, say): a
  service listened and answered. Whatever exit code such a probe returns is not in the table, and
  under the engine's reading (「访问成功」 = reachable, 「访问失败」 = unreachable) it cannot redeem
  「访问失败」.
- **The failure must be caused by the authored difference.** Everything the author did not change
  stays equal between the failing probe and its success arm (address, port, trigger host,
  backend); only what the author changed varies (the protocol, the portlist, the deleted object).
  A probe that fails for a reason the author did not write passes by construction and verifies
  nothing: the recreated object moved to another port although the author changed only its
  protocol, a different VIP, a backend that serves nothing. (When the port is the authored
  difference, as in 「使用原portlist访问失败」, the old port going silent is the test point.) If no
  construction on this bed lets the authored difference itself produce a transport failure while
  the success arm succeeds, stop and tell the user why; do not fall back to a configuration
  assertion and do not move the port.
- `cmd` is one direct command whose exit status is not masked: no pipes, `;`, `||`, background
  `&`, newlines or command substitution (`&&` only with `expect: success`, when every command must
  succeed). For `expect: failure` the target must be an IP literal
  (`negative_probe_target_not_ip_literal`), and the trigger host needs a declared path to it
  (`negative_probe_path_undeclared`).
- HTTPS: `curl -k -s -o /dev/null --max-time 10 https://<VIP>:443/`, and load certificates with
  `SSL_CERT_LOAD` first. DNS: `dig @<VIP> -p <port> <name> <type> +time=<s> +tries=<n>`.
- The engine renders this as a `test_env` row plus an `IST_EXIT_STATUS` check_point; do not
  write those rows yourself.

### OBSERVE_ASSERT — output checks (configuration / display verdicts)

```json
{"kind": "OBSERVE_ASSERT", "host": "APV_0", "cmd": "show slb virtual addrlists addlist1",
 "cmd_ref": "manual:10.5.0/cli_cn.md:10818",
 "asserts": [{"op": "not_found", "pattern": "<the new address, regex-escaped>",
              "expectation_id": "<from the card>", "semantic_key": "<from the card>",
              "ref": "intent:<expectation_id>", "desc": "新地址未被加入"}],
 "desc": "查看地址集合，确认新地址未被加入"}
```

- `[OBSERVE_ASSERT, <op>]` must be one of the expectation's `allowed_slots` (`found` is a regex,
  `abs_found` a literal, `not_found` a regex that must not match).
- `ref: "intent:<expectation_id>"` cites the author's claim as the expected-value source.
- The pattern must match only a data line, never the command echo itself.
- **`status_value` is tied to the latest configuration step.** When `cmd` is a query (show / get,
  or a probe), the pattern has to match one of the commands of the nearest CONFIG block before
  this observation (`abs_found` as a substring, `found` / `not_found` as a regex); otherwise
  `criterion_status_target_unbound`. Put the observation right after the configuration it checks.
  When the value is a runtime outcome no configuration line carries, declare the cause on this
  expectation's `expectation_binding` entry: `state_change_step` = the index of that CONFIG block
  (a device-configuration block before the observation) and `binding_disclosure` = one Chinese
  sentence saying why the command line cannot carry the value and how that step causes it. The
  gate then records it (advisory `criterion_binding_declared`) instead of refusing, unless the
  declared step is the teardown of the asserted state (`criterion_state_change_step_self_satisfying`).
  The author's claim sentence itself is never a pattern (`criterion_status_claim_literalized`).

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

## Who answers (`answerer`)

Every OBSERVE_ASSERT and OBSERVE_EXIT whose `host` is not `APV_0`/`APV_1` names who answers it
(`answerer_statement_missing` otherwise). The gate checks that it is present and that `ref`
resolves, not that it is right:

| `answerer` | use it when | `ref` / `note` |
|---|---|---|
| `{"kind": "device", "ref": <i>}` | the device under test answers with configuration this case sets up | `blocks[i]` is the CONFIG block (or a STEP writing device configuration) that establishes it |
| `{"kind": "fixture", "ref": <i>}` | a fixture this case sets up answers | `blocks[i]` is the block that sets it up |
| `{"kind": "bed_service", "ref": "<device name>"}` | a service the bed itself provides answers (a `services` entry) | a device name from the bed topology (the device list in `bed.summary`) |
| `{"kind": "undetermined", "note": "<one Chinese line>"}` | no source says who answers | nothing is sealed: `cex_author_submit_case` returns `status: needs_user_decision`; ask the user |

For `expect: failure`, name the configuration the probe is aimed at (the device is still the party
whose behaviour is judged).

## Expectation binding

One entry per assertion slot, pointing at the assertion it is:

```json
{"expectation_id": "<card>", "semantic_key": "<card>", "claim_kind": "Author",
 "block_index": 9, "assert_index": null, "scope_ref": null,
 "state_change_step": null, "binding_disclosure": null}
```

- Every assertion slot has exactly one entry: each `asserts[]` entry of an OBSERVE_ASSERT
  (`assert_index` = its index), and each OBSERVE_EXIT, CAPTURE_COMPARE, EXPECT_FROM, OBSERVE_DIST,
  OBSERVE_MEMBER block and each STEP with `E` = `check_point` (`assert_index: null`).
- Every card expectation appears in at least one entry. Several entries carry the same
  `expectation_id` / `semantic_key` when one expectation occupies several slots (one per object);
  one slot never redeems two expectations.
- When several expectations share one `semantic_key`, the gate may ask for `scope_ref`; copy it
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

## Advisories

A submission can be sealed and still return `advisories` (`{gate, code, locus, detail}`); a
rejection returns them too. An advisory is a limitation the gate did not decide, not a pass.
**Resolve every advisory** (rewrite the blocks and resubmit) **or disclose it in your report with
the reason it stays.** The ones that come up most:

| code | what it says | what to do |
|---|---|---|
| `config_existence_only` | the assertion only shows that a configuration you wrote is present in a read-only query; it shows no behaviour | keep it only when the claim is about configuration being accepted (「配置成功」「无法添加」); a behaviour claim needs behaviour evidence (traffic through OBSERVE_EXIT, runtime state) |
| `ambiguous_observation_binding` | the assertion reads only the last of several consecutive observation rows (single-command CONFIG blocks render as `cmd_config` rows and count as observations) | make sure the assertion reads the observation the claim is about; a traffic claim is an OBSERVE_EXIT, not an assertion on an echo |
| `author_sourced_unreachable_setup`, `author_sourced_trigger_target`, `author_sourced_driver_target` | the author's own addresses are not usable on this bed | bind them to bed addresses and disclose the binding |
| `scope_ref_absent` | several claims share one `semantic_key` without `scope_ref` | add the `scope_ref` the detail names |
| `criterion_binding_declared` | your `state_change_step` declaration was recorded | report its `binding_disclosure` |
| `adaptation_dropped_authored_command` | the adapted steps run an authored command head fewer times than the author wrote it | the missing occurrences stay obligations: write them |
| `residual_config_disclosed` | the teardown atlas classifies some configuration writes as residual | report it |

## Reading a rejection

Fix the locus the violation names, keep everything else, resubmit the whole body. Common ones:

| code | fix |
|---|---|
| `trigger_reachability_invalid` | VIP not in ★, or the trigger host is not the one paired with it |
| `environment_unreachable_ip` | an address that is not on this bed; take one from `bed` |
| `expectation_bijection_failed` | a card expectation has no assertion, or an assertion redeems none |
| `document_inconsistent` | the body does not validate, e.g. an assertion slot without its `expectation_binding` entry |
| `criterion_binding_missing` / `criterion_lowering_mismatch` | the redeeming (block kind, operator) is not one of the expectation's `allowed_slots` |
| `criterion_status_target_unbound` | a `status_value` pattern not grounded by the nearest CONFIG block (see OBSERVE_ASSERT) |
| `answerer_statement_missing` / `answerer_ref_unresolved` | name who answers a bed-host observation (see "Who answers") |
| `negative_probe_target_not_ip_literal` / `negative_probe_path_undeclared` | an `expect: failure` probe needs an IP literal the trigger host has a declared path to |
| `missing_teardown` | add the paired `no …` restore for every object the case created |
| `authored_command_occurrence_missing` | an author step's command is missing from the blocks |
| `https_certificate_setup_missing` | add `SSL_CERT_LOAD` for the HTTPS virtual service |
| `provenance_source_unresolved` | a `ref` / `cmd_ref` does not resolve; take it from `cex_lang_query` |
| `consistency_stage_unavailable` | the batch is bound to a governing spec, which this client cannot author against; tell the user (mindmap-recompose, `governing_spec`) |
| `contracts_republished` | `cex_author_prepare` re-published the cards meanwhile; read the new card and resubmit |

The same rejection code twice in a row on an unchanged shape means your model of the rule is
wrong: re-read the violation's `detail` and `legal_form` instead of resubmitting.

## After a failed run

Rework only the failed cases, and only in their mechanical cases: fix the blocks, resubmit with
`cex_author_submit_case`, `cex_author_emit`, then `rework_gate.js` on the emitted
`compile_outputs/<batch>/cases.json`, `cex_scan_destructive`, and the run (SKILL.md §9). Never
edit the emitted `cases.json`: the next emit overwrites it, and `compile_excel.js` refuses it.
