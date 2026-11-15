# Hosted ProofFlow delivery

[Open ProofFlow](https://proofflow.arnavbule.in) · [Watch the walkthrough](https://proofflow.arnavbule.in/walkthrough.mp4) · [Inspect the public evidence](https://proofflow.arnavbule.in/evidence/) · [Hosted verification receipt](../evidence/hosted_delivery_v2.json)

On 15 November 2026 UTC, the hosted app was verified at source revision `fdee9c999a1a5c62de4cf624f9bcc42ba6c124a6` and Linux AMD64 image ID `sha256:f94ddef84a8a1b204a123cd16839af317337731ca999989b32b469215065677c`. The deployment replaced only the application container. **21 read-only host checks** matched the running image and revision to the release, confirmed healthy HydraDB-backed requests over HTTPS, and verified that both state volumes were retained and that the HydraDB container and its start time were unchanged.

## Public HTTPS acceptance

A GitHub-hosted Ubuntu runner used system DNS and normal TLS certificate validation. The served HTML, JavaScript and CSS matched the frontend rebuilt from the exact checkout. **11 Chrome acceptance steps and 13 guided HTTP checks passed** on the first workflow attempt. The guided checks covered source correction, refresh, missing-source refusal and reset. The full two-minute MP4 matched the packaged bytes, its range request returned the expected `206` response, and Chrome played it and continued after seeking to 75 seconds. [Hosted acceptance workflow, private repository access required](https://github.com/saivedant169/proofflow/actions/runs/43753250552).

The Chrome run created company and NORTH reports from the two-row CSV at **$308.00 / $108.00**, reloaded their saved artifacts, and downloaded the checked figures. A second tab corrected EUR→USD from 1.20 to 1.30. The original tab’s next download attempt returned **HTTP 409** and produced no file. Refresh yielded **$317.00 / $117.00** in four recorded tool calls and 11 verification calculations, preserving the independent support artifact. The refreshed download matched the new report and claim IDs. A separate APAC browser context retained **$163.75 / $93.75** and received `404` when requesting evidence owned by the NORTH session. Controls were checked at 320 px and 390 px.

## Public results package

Separate HTTPS checks from the builder network matched four served files to the release bytes: the evidence page, stylesheet, **5,664,791-byte ZIP** and checksum. The bare `/evidence` route redirected to `/evidence/`, a missing evidence file returned `404`, and none of these requests set a session cookie. The offline verifier checked **346 bundle files**, including a model audit of **152 payloads and 48 scored cells**, and reconstructed **4,681 source rows**. It checks the inventory and listed hashes and reports the earlier fixed-budget shortfall and failed development gate alongside the saved model results. [Public download](https://proofflow.arnavbule.in/evidence/) · [Verification instructions](PUBLIC_EVIDENCE.md).

## Separate CI, local and historical checks

- The exact release passed **465 Python tests, nine Chromium workflows under the checked-in default settings and 22 successful job steps** on the first CI attempt. The one-cent negative control detected both expected arithmetic differences. [Release CI, private repository access required](https://github.com/saivedant169/proofflow/actions/runs/43752499925).
- The exact release image passed **45 local checks across 18 HTTP responses** under AMD64 emulation with separate app state. An earlier packaging attempt failed locally because extraction removed required file permissions. Preserving the archived modes corrected the packaging before host transfer.
- On the earlier `0535ba6` deployment, an application restart passed **87 checks across 12 HTTP responses**, with two transient `502` responses. It restored the saved CSV reports and then exercised a new correction and refresh. [Historical host receipt](../evidence/hosted_delivery_v1.json).

The hosted runs measure automated functional acceptance on one demo host. HydraDB remained running during the current application replacement. Human use, production load and uninterrupted availability remain unmeasured. The source repository is private. Approved judge access and the organizer’s form remain pending. [Submission draft](SUBMISSION_DRAFT.md).
