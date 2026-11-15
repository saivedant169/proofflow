# Hosted evidence navigation trial

**One Claude Code run passed all eight frozen obligations.** Fable 5.2 chose the NORTH report and claim, then followed the net-revenue identity returned as a typed input. After the FX correction, it used a recorded native path to explain why the old NORTH claim was stale. It rechecked the same net artifact and producing receipt as current before refresh. The runtime’s actual reuse list contained that audited net artifact. [Sanitized result](../evidence/hosted_evidence_navigation_v1.json).

| Obligation | Verified observation |
| --- | --- |
| Select relevant evidence | The model inspected the observed NORTH report and its claim. |
| Follow a discovered input | It used a net-artifact ID first returned by the selected claim and matched the typed input’s content hash. |
| Verify unchanged work before refresh | The same net artifact ID, hash and producing receipt were current before and after the rate change. |
| Explain the stale claim | The inspected path ran from old FX through the currency-conversion receipt to the stale NORTH claim. The model used that path in its explanation. |
| Withhold stale values | Both current values were `null` after correction. The model labeled the prior amount historical. |
| Verify actual reuse | The recorded refresh reused-ID list contained the inspected net artifact. A later inspection confirmed its same ID, hash and receipt. |
| Export a checked handoff | The UTC-timestamped export matched both refreshed report and claim pairs and the independent arithmetic. |
| Explain executed and reused work | The model distinguished four executions from two reused results and made the identity claim for the net artifact it inspected. |

Company and NORTH revenue started at **$308 / $108** on the authored NORTH/SOUTH CSV at EUR/USD 1.20. The rate change to 1.30 preserved the input digest and affected four artifacts. Refresh recorded **four executions, eleven verification calculations and two reused artifacts**, then the checked export returned **$317 / $117**. The run made 13 matched MCP calls: nine evidence reads, create, update, refresh and one checked export. The client was offered six tools and called five. It made no stale-export request. The earlier [five-tool V2 trial](HOSTED_CONNECTOR_MODEL_V2_RESULTS.md) separately observed an actual stale HTTP 409. It completed 7/7 prescribed stages, while [V1](HOSTED_CONNECTOR_MODEL_V1_RESULTS.md) stopped normally after 2/7.

## Frozen inputs and limits

The trial pinned the hosted `327dc602cbb255c07201ffb85bcfc656476b382e` release and AMD64 image `sha256:7942a2441d932792000acfc50358a82f2ec7a1c949922f5ac1b9e6e679b83042`. Its 28,594-byte connector had SHA-256 `f987dd80caa31aad06d22f7ad479548fae6e7bd41a0aa1c102d73305f14c5ede`. The [authored two-row fixture](../fixtures/browser_csv_v1/valid_non_eu.csv) had SHA-256 `9404a094f276690922a09e3727301f124a36647dbec7bfd2babb1859f4f26cca`. The model received the CSV, six tool contracts and the business task. It selected evidence targets and input IDs from tool results. The guard set operation limits and forwarded accepted traffic unchanged. [Hosted release checks](HOSTED_DELIVERY.md).

The client requested high effort and completed normally with `end_turn` in **14 CLI turns** and **46.736 seconds** of CLI time. There were zero observed guard blocks or tool errors. The CLI reported a **$0.4920828 list-cost estimate**, with 18 ordinary input tokens, 19,500 cache-write tokens, 71,894 cache-read tokens and 4,139 output tokens. Billing and internal provider transport retries were unobserved. The limits were one operator launch, 20 CLI turns, 16,000 output tokens per provider request, a 900-second watchdog, a $2 CLI estimate setting and a $3 planning allowance.

This is one guided integration on a fixed authored fixture. The server still calculates fixed report recipes. The observed path is a bounded witness from recorded changed sources, and the reuse observation is specific to the retained net artifact. The trial measures evidence navigation in this workflow. Learning, performance on new data, comparative cost, human adoption and database-engine advantages remain unmeasured.

The independent audit checked actual tool arguments and responses, chronology, native path evidence, reuse-list membership and the final explanation. The public projection carries the frozen packet, prompt and system digests, and the audit receipt hash. The next release is planned to expose the sanitized independent receipt and its checksum on the agent page. [Public audit receipt path](https://proofflow.arnavbule.in/agent/hosted_evidence_navigation_v1.json) · [Public checksum path](https://proofflow.arnavbule.in/agent/hosted_evidence_navigation_v1.json.sha256). External verification of those new paths is pending.
