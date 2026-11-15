# ProofFlow delivery research

Research time: 15 November 2026, approximately 15:00 IST. Read-only research; no deployments, registrations, messages, submissions, or account changes were made.

## Exact event and rules

The requested event is [HydraDB Hackathon, Luma code bqwllms4](https://luma.com/bqwllms4), November 14–16, with the stated end time of November 16 at 09:00 IST.

The earlier parent-agent browser observation directly read the Luma page. Its public description gives two tracks: a graph that improves itself, and an agent context layer using structure. It says both engineering and go-to-market are judged and requires an advantage over a vector store. It links the [event Discord invite](https://discord.com/invite/YPtwenvxY8). This research pass could not reopen Luma with web retrieval; the child-agent IAB browser was unavailable. No new official FAQ was retrieved.

The [organizer's November announcement](https://x.com/hydra_db/status/2121108373022355864) and [exact-event reply](https://x.com/hydra_db/status/2121108375140487637), available as organizer-authored text through a [public mirror](https://www.teapawt.net/hydra_db), corroborate the two tracks and November timing. The mirror is not an independently hosted official FAQ.

### Participant-sourced requirements, not official verification

[TrailMend's event notes at a pinned revision](https://github.com/DrApkFile/TrailMend/blob/c3e55d2a90aeff54601318b9225cf0c7113ba2ef/docs/EVENT.md) explicitly paraphrase organizer Discord messages. They report:

- Self-run HydraDB OSS engine, rather than hosted Hydra platform.
- Track 2 as a live graph of agent skills, tool definitions, and already-resolved entities.
- Equal emphasis on engineering and go-to-market.
- Hosted live app, public/open-source repository, and Loom walkthrough.
- A possible requirement for iterative improvement across both tracks.
- Social posts tagging HydraDB.

The same document calls the submission form location and video length open questions. Its three-seed requirement and several other acceptance gates are the participant's own test plan, not verified organizer requirements. Its prize arithmetic does not account for the full advertised pool. Do not turn those details into confirmed rules.

**Unresolved before final submission:** exact November submission URL; whether continual-learning improvement is mandatory in Track 2; video provider/length requirements; and any formal social-post requirement. These require the organizer's original pinned Discord/FAQ or submission form. Public web search and targeted GitHub search did not locate them. Two narrowly scoped connected-mail searches for HydraDB/event-code emails since November 1 returned no messages.

**Do not use [hackhydra.hydradb.com](https://hackhydra.hydradb.com/) as this event's rulebook or form.** It explicitly describes the separate August 12–20 event, with different tracks, prizes and dates.

## Verified official container route

Use the upstream GitHub Container Registry image, preferably pinned after local inspection:

`ghcr.io/hydra-db/hydradb:0.4.0`

The [official release](https://github.com/hydra-db/hydradb/releases/tag/v0.4.0) was published November 14, 2026 at 02:32:46 UTC. The [official package page](https://github.com/hydra-db/hydradb/pkgs/container/hydradb) currently maps v0.4.0 to `sha-9166374` and exposes:

- Multiarchitecture index: `sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880`
- Linux ARM64: `sha256:64fa5979c940f7b97fa8fdac8131e4adbeec84687dac0686a8342248953ea782`
- Linux AMD64: `sha256:e837db24b4c11eba759001aa6143bd7415a4fe811045831f83b6b03eec8a4bb5`

The [upstream container workflow](https://github.com/hydra-db/hydradb/blob/main/.github/workflows/container.yml) builds ARM64 and AMD64 on native runners, merges their manifests, and verifies both platforms exist. This is the supported path for the Mac ARM Docker host; compiling the Rust engine is unnecessary for the first spike.

The [runtime Dockerfile](https://github.com/hydra-db/hydradb/blob/main/Dockerfile) runs as UID/GID 10001, enters `/usr/local/bin/graph-node`, and also includes `/usr/local/bin/graph-indexer`. Mounted data/cache/token paths need compatible permissions. This pass inspected sources; it did not pull/run the image or independently test durability.

## Runtime facts to preserve in the spike

The [upstream README](https://github.com/hydra-db/hydradb/blob/main/README.md) documents a local persistent directory provider and authenticated HTTP. Important settings include `CLOUD_PROVIDER=local`, an existing `LOCAL_PATH`, `GRAPH_AUTH_TOKEN_FILE`, namespace/graph/cell identity, and `RUST_MIN_STACK=33554432`. For a local-only development listener it documents explicit plaintext mode. Keep public transport TLS and authentication in a hosted deployment.

The HTTP query endpoint is `/v1/graphs/default/query`, with bearer authentication, namespace header, and mandatory `cell_id`. Query service is on port 8443, Bolt on 7687, admin on 9090. Health and readiness use different listeners. [Using HydraDB](https://github.com/hydra-db/hydradb/blob/main/USING-HYDRADB.md) documents the supported query subset and typed response cells; do not assume unrestricted Neo4j syntax.

Use a write → bounded multi-hop reverse traversal → process restart → identical query test. Separately restart the durable database process and verify source/artifact graph state. If state is restored from an application journal, disclose that as graph reconstruction rather than claiming the database persisted it.

Current main README labels the engine ELv2. Older participant compose files call their pinned engine AGPL. Record the actual chosen release and license; do not carry a stale license statement forward.

## Hosting references and warning

The [Railway hydradb template](https://railway.com/deploy/hydradb) exists and describes a persistent single-node deployment, but its visible image is **`xiaosong233/hydradb-railway:latest`**, not the official upstream GHCR image. Its creator is a community account. It should not be called an official HydraDB deployment recipe, nor used as evidence that upstream v0.4 durability works.

A participant's [ToolGraph compose at the audited revision](https://github.com/ivarunchaudhary/toolgraph/blob/057348e0ca7ff78e7d5a1974283c328ffcbc3962/docker-compose.yml) shows a usable reference shape: upstream v0.3.0 node and indexer, local volume, token-init, and volume ownership initialization to UID 10001. It is implementation reference material, not an official guarantee or permission to resubmit competitor code. ProofFlow should keep its own small configuration and verify it.

The preferred route is an upstream pinned image on the host already available to the builder, with persistent storage and a private database listener behind the application. Availability of a paid hosting account, deployment credentials, and submission destination remains to be established by the main agent.
