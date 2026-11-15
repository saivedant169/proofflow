# Hosted ProofFlow delivery

[Open the live app](https://proofflow.arnavbule.in) · [Watch the two-minute walkthrough](https://proofflow.arnavbule.in/walkthrough.mp4) · [Machine-readable hosted evidence](../evidence/hosted_delivery_v1.json)

On 15 November 2026, automated checks from the builder network verified the HTTPS demo against real HydraDB. The checks apply to the running app at source revision `0535ba672b4b31c563c13d95df03285a73a4d736` and Linux AMD64 image ID `sha256:6bd0995c0714ed6f326b708c09ac8b680a97dd9f173d82f5af7d5a3223e9b01e`. The running host snapshot matches the build image receipt on both identifiers. That revision identifies the deployed runtime; later documentation changes do not change the tested image.

The custom domain’s authoritative DNS servers, two public resolvers and the server resolver all returned `16.4.117.247`. The builder’s Mac still had a cached negative answer, so the HTTP and Chrome checks mapped that exact hostname to the IP within each process. They kept normal TLS certificate validation and used the custom hostname in requests. The domain returned a `308` HTTP-to-HTTPS redirect, `200` for HydraDB health over trusted HTTPS and `206` with `video/mp4` for the walkthrough range request. All 13 guided HTTP checks passed on the domain. Chrome verified guided correction and refresh, independent value checks and secure session cookie attributes. The domain change did not restart the app or HydraDB.

The following runs tested the original HTTPS IP directly:

| Run | Result | What it covered |
|---|---|---|
| Guided HTTP smoke | 13 checks passed | HydraDB health, built UI and assets, guided correction and refresh, refusal when a source is missing, and reset to a new generation. |
| Chrome acceptance | 8 groups passed | HTTPS and walkthrough, guided workflow, CSV creation and correction, checked downloads, session isolation, and mobile report controls. |
| Application restart over HTTPS | 87 checks passed across 12 HTTP responses | An actual restart of the app on the demo host, followed by a read of saved work and a fresh CSV correction and refresh. |

In Chrome, the guided workflow used a session cookie with `Secure`, `HttpOnly` and `SameSite=Strict`. An authored CSV produced **$308 company / $108 NORTH** and retained its saved reports on reload. One tab corrected EUR→USD from 1.20 to 1.30; the other tab received **HTTP 409** if it tried to export stale figures, and no file downloaded. Four recorded refresh calls produced **$317 / $117** and a current report download. An independent APAC session retained **$163.75 company / $93.75 APAC** throughout and could not read the other session’s evidence. The report controls fit at 320 px and 390 px.

The hosted 120-second MP4 matched the packaged film’s SHA-256 and returned the expected bytes in a `206 Partial Content` response. In Chrome, the video played, sought to 75 seconds and continued playing with audio muted.

In a separate run, the application’s start time changed; the HydraDB service and host boot were unchanged, and the mounts and read-only token file metadata matched before and after. Health returned two `502` responses during the restart and recovered on the third poll. After restart, the same HTTP session read the saved **$308 / $108** figures and artifact identities. A new correction withheld stale amounts through a reload, and the refreshed **$317 / $117** persisted on the final reload. The independent support artifact stayed current.

These are functional acceptance results on one demo host, separate from the local, CI and benchmark evidence. The restart exercised the application only. The runs did not include human trials, adoption measurement, load testing, a separate staging environment, or a zero-downtime test. The source repository stays private; judge access and submission are tracked in the [submission draft](SUBMISSION_DRAFT.md).
