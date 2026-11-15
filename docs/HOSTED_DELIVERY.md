# Hosted ProofFlow delivery

[Open ProofFlow](https://proofflow.arnavbule.in) · [Watch the walkthrough](https://proofflow.arnavbule.in/walkthrough.mp4) · [Inspect the public evidence](https://proofflow.arnavbule.in/evidence/) · [Set up the CSV connector](https://proofflow.arnavbule.in/agent/) · [Hosted verification receipt](../evidence/hosted_delivery_v4.json)

On 15 November 2026 UTC, **21 read-only host checks** verified the running source revision `b13f23892405efb856c8d4ca0e6abc94a1eca77c` and Linux AMD64 image ID `sha256:6899dcbe1a3af480c999b0014118befa9ea5d517adf73f1e1816165915220efc`. The deployment replaced only the application container and retained both state volumes. The HydraDB container and its start time were unchanged. Public HTTPS health confirmed the HydraDB backend.

## Current public HTTPS acceptance

On the first attempt, a GitHub-hosted Ubuntu runner passed **11 Chrome steps and 13 guided HTTP checks** using system DNS and normal TLS validation. The served HTML, JavaScript and CSS matched a rebuild of the exact deployed revision. The guided checks covered correction, refresh, missing-source refusal and reset. Chrome played the byte-matched two-minute walkthrough, sought to 75 seconds and continued playing. The media request returned the expected `206` range. [Hosted acceptance workflow, private repository access required](https://github.com/saivedant169/proofflow/actions/runs/43762066168).

Chrome exercised the two-row CSV from **$308 / $108** to **$317 / $117** in four recorded refresh calls and 11 verification calculations. Before the correction and after refresh, **Copy checked report** put the server’s exact snapshot on the browser clipboard, including the UTC check time and both report and claim IDs. An older tab’s copy request returned `409` and left the clipboard sentinel in place. A stale download also returned `409` and produced no file. The retained support result and the separate APAC session stayed current. Controls were checked at 320 px and 390 px.

## Public evidence and connector downloads

The public download job used anonymous HTTPS, system DNS and normal certificate validation. **Ten responses** matched the checkout byte for byte, including the evidence page and stylesheet, both ZIPs and their checksums, and the connector files. Those requests set no cookies. The offline verifiers ran as a non-root user in a separate Linux network namespace. The original model ZIP retained its bytes and its audit verified **346 bundle files**, **152 model-study payloads**, **48 scored cells** and **4,681 source rows**. [Original model ZIP and verification instructions](PUBLIC_EVIDENCE.md).

The separate delivery verifier checked **52 payloads** from the saved `0535ba6`, `fdee9c9` and `92da58c` releases and accompanying studies. These include the January retail CSV run, paired recalculation, interrupted-update recovery, and the original fixed-budget wrapper failures and audited recovered scores. The new hosted clipboard run is recorded in the current receipt. [Delivery ZIP and verification instructions](PUBLIC_DELIVERY_EVIDENCE.md) · [Current hosted receipt](../evidence/hosted_delivery_v4.json).

The connector download launched in an empty directory with a new `uv` cache. A stock MCP 2.3.0 client negotiated protocol `2025-11-25` and discovered all five tools. This check stopped at discovery with **zero tool calls**. An earlier stock-client run exercised the same script against the `fdee9c9` hosted API and passed **21 fixture checks**, including a checked export and stale and cross-session refusal. Both used scripted clients. Model-selected composition was tested separately through the local stdio server. [Connector setup](https://proofflow.arnavbule.in/agent/) · [Local model-client evidence](MCP_AGENT_RESULTS.md).

## CI and local packaging checks

- The deployed revision passed **488 Python tests and nine default Chromium workflows** across 23 successful job steps on the first Linux CI attempt. The one-cent control detected both expected arithmetic differences. [Release CI, private repository access required](https://github.com/saivedant169/proofflow/actions/runs/43761386190).
- The deployed image passed **54 local checks across 26 HTTP responses** under AMD64 emulation with a separate app state volume.

## Historical hosted checks

- The `92da58c` release passed 11 Chrome steps and 13 guided HTTP checks. A separate Chrome run on that release passed all six phases with **642 UCI Online Retail lines** from January 16, 2011. The staged GBP rate correction moved both company and UK totals from **$9,052.58 to $9,414.68**, with stale export refusal and persistence after refresh. [V3 release receipt](../evidence/hosted_delivery_v3.json) · [Retail CSV run, oracle and scope](REAL_PARTITION_RESULTS.md).
- The previous `fdee9c9` deployment passed 11 external Chrome steps and 13 guided HTTP checks, including video playback, stale-tab refusal, a refreshed download and mobile session isolation. [V2 release receipt](../evidence/hosted_delivery_v2.json).
- On `0535ba6`, an application restart passed **87 checks across 12 HTTP responses**, with two transient `502` responses. It restored saved CSV reports and then exercised a correction and refresh. [Initial hosted receipt](../evidence/hosted_delivery_v1.json).

The hosted runs measure automated functional acceptance on one demo host. HydraDB remained running during the current application replacement. Human use, production load and uninterrupted availability remain unmeasured. The source repository is private. Approved judge access and the organizer’s form remain pending. [Submission draft](SUBMISSION_DRAFT.md).
