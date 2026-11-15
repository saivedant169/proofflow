# Hosted ProofFlow delivery

[Open ProofFlow](https://proofflow.arnavbule.in) · [Watch the walkthrough](https://proofflow.arnavbule.in/walkthrough.mp4) · [Inspect the public evidence](https://proofflow.arnavbule.in/evidence/) · [Set up the CSV connector](https://proofflow.arnavbule.in/agent/) · [Hosted verification receipt](../evidence/hosted_delivery_v3.json)

On 15 November 2026 UTC, **21 read-only host checks** verified the running source revision `92da58c806a07d2577aef27bf5c967e7751325a0` and Linux AMD64 image ID `sha256:b7cc8d19136ed25caa573ffc05446a6ea93cfb40a4013f5c6f6bd45644c6e958`. The deployment replaced only the application container and retained both state volumes. The HydraDB container and its start time were unchanged. Public HTTPS health confirmed the HydraDB backend.

## Current public HTTPS acceptance

On the first attempt, a GitHub-hosted Ubuntu runner passed **11 Chrome steps and 13 guided HTTP checks** using system DNS and normal TLS validation. It verified files served by the `92da58c` image against checkout `f0173e70337fc87972a7eda77ae55475be43649c`, which has the same frontend and application runtime bytes. The served frontend also matched the rebuilt HTML, JavaScript and CSS. The guided checks covered correction, refresh, missing-source refusal and reset. Chrome played the byte-matched two-minute walkthrough, sought to 75 seconds and continued playing. The media request returned the expected `206` range. [Hosted acceptance workflow, private repository access required](https://github.com/saivedant169/proofflow/actions/runs/43758170089).

Chrome exercised the two-row CSV from **$308 / $108** to **$317 / $117** in four recorded refresh calls and 11 verification calculations. The old tab got `409` and no download after the correction. The refreshed export matched the new report and claim IDs. The independent support result and the separate APAC session were preserved. Controls were checked at 320 px and 390 px.

A separate GitHub-hosted Chrome run passed all six planned phases against the same deployed image, using **642 UCI Online Retail lines** from January 16, 2011. The authored GBP correction moved both company and UK totals from **$9,052.58 to $9,414.68**. It withheld the old amounts and refused the stale-tab export with `409`, then preserved the refreshed figures on reload. The dataset is a single-country positive-sales extract. [Run, oracle and scope](REAL_PARTITION_RESULTS.md).

The public download job used anonymous HTTPS, system DNS and normal certificate validation. **Eight responses** matched the checkout byte for byte, including the evidence page, stylesheet, ZIP and checksum, plus the connector page at two paths, the script and its checksum. Those requests set no cookies. The offline verifier ran as a non-root user in a separate Linux network namespace. It verified **346 bundle files**, audited **152 model-study payloads and 48 scored cells**, and reconstructed **4,681 source rows**. The **5,664,791-byte ZIP** includes the earlier fixed-budget shortfall and failed development gate. [Public evidence download](https://proofflow.arnavbule.in/evidence/) · [Offline verification instructions](PUBLIC_EVIDENCE.md).

The connector download launched in an empty directory with a new `uv` cache. A stock MCP 2.3.0 client negotiated protocol `2025-11-25` and discovered all five tools. This check stopped at discovery with **zero tool calls**. An earlier stock-client run exercised the same script against the `fdee9c9` hosted API and passed **21 fixture checks**, including a checked export and stale and cross-session refusal. Both used scripted clients. Model-selected composition was tested separately through the local stdio server. [Connector setup](https://proofflow.arnavbule.in/agent/) · [Local model-client evidence](MCP_AGENT_RESULTS.md).

## CI and local packaging checks

- The deployed revision passed **473 Python tests and nine default Chromium workflows** across 22 successful job steps on the first Linux CI attempt. The one-cent control detected both expected arithmetic differences. [Release CI, private repository access required](https://github.com/saivedant169/proofflow/actions/runs/43757568426).
- The deployed image passed **52 local checks across 24 HTTP responses** under AMD64 emulation with a separate app state volume.

## Historical hosted checks

- The previous `fdee9c9` deployment passed 11 external Chrome steps and 13 guided HTTP checks, including video playback, stale-tab refusal, a refreshed download and mobile session isolation. [V2 release receipt](../evidence/hosted_delivery_v2.json).
- On `0535ba6`, an application restart passed **87 checks across 12 HTTP responses**, with two transient `502` responses. It restored saved CSV reports and then exercised a correction and refresh. [Initial hosted receipt](../evidence/hosted_delivery_v1.json).

The hosted runs measure automated functional acceptance on one demo host. HydraDB remained running during the current application replacement. Human use, production load and uninterrupted availability remain unmeasured. The source repository is private. Approved judge access and the organizer’s form remain pending. [Submission draft](SUBMISSION_DRAFT.md).
