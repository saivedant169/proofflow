# Actual Claude MCP client result

**PASS: 32/32 checks**—26 execution/data checks and six client checks—on the frozen `7f110c61801332e30bb16b2aa9dc8f9ff3f58568` implementation. Claude Code used **Fable 5.2, high effort**, made **nine successful MCP requests across ten CLI turns**, and completed two report compositions followed by an FX correction. This is one authored two-row integration demonstration, not a broad agent-performance benchmark. [Result and usage](../results/mcp-agent-v2/summary.json)

The client received the CSV, requested report contents, and FX rates. It discovered typed tool contracts through `prepare` and supplied both executable plans itself. The prompt contains neither the seven-step calculation route nor the expected numeric answers. The first composition used seven registered calculations; the second composed a new report using artifacts from the first run. The MCP server invoked **zero models**; the external Claude client made the paid model requests. [Task prompt](../results/mcp-agent-v2/prompt.txt) · [Client tool requests and responses](../results/mcp-agent-v2/tool-transcript.json)

## Verified behavior

| Stage | Observed result | Recorded runtime calls |
|---|---|---:|
| Initial company report | Client chose and executed a complete plan | 7 |
| Separate NORTH brief | Client reused existing calculation artifacts | 1 |
| EUR rate correction, 1.20 → 1.30 | Only FX changed; native Hydra impact found four artifacts, including both reports | 0 |
| Inspect, refresh, inspect | Stale revenue claims withheld; support remained current; both replacement reports became current | 4 |

| Claim, present in both reports | Before correction | After refresh |
|---|---:|---:|
| Company net revenue, USD cents | 30,800 | 31,700 |
| NORTH net revenue, USD cents | 10,800 | 11,700 |
| NORTH support tickets | 3 | 3 |

All **12 recorded runtime calls succeeded**. CSV loading additionally performed **16 arithmetic preflight calculations**—eight per load—which are excluded from the recorded-call count. This is not a zero-compute reuse claim. No tool failure, permission denial, silent fallback, or automatic retry occurred within v2. [Independent execution audit](../results/mcp-agent-v2/independent-audit.json)

A separate read-only review recomputed these amounts from hash-checked durable source blobs, reopened both replacement reports as current, and re-queried native Hydra impact. All 26 frozen code-file hashes still matched after the trajectory. Every submitted tool request and response matched the retained private raw transcript.

## Both paid attempts are retained

| Attempt | Outcome | Provider-reported list cost |
|---|---|---:|
| v1 | Infrastructure failure: `--safe-mode` suppressed MCP; zero tool requests and no source/artifact writes | $0.037144 |
| v2 | Successful trajectory after an explicitly recorded configuration repair | $0.809898 |
| **Total: two attempts** | One failed, one successful | **$0.847042** |

V2 retained the same task and system prompt as v1, apart from the workspace nonce. It replaced safe mode with restricted mode and frozen per-run isolation settings. A control-only preflight verified exactly one connected ProofFlow server and its five tools before any paid request. Builtin tools were disabled; permissions remained `dontAsk` with an exact MCP allowlist. Managed policy remained authoritative. [Retained v1 result](../results/mcp-agent-v1/summary.json) · [V2 protocol and correction record](../results/mcp-agent-v2/prepared.json) · [No-model connection preflight](../results/mcp-agent-v2/preflight.json)

Costs include provider cache accounting and are list estimates, not a subscription billing statement or a cost-comparison claim. Raw initialization, local plugin identifiers, account metadata, stderr, and environment-specific settings remain outside submitted evidence. Curated traces preserve tool payloads and usage while removing unrelated initialization metadata; hashes bind the retained originals. [Curated event stream](../results/mcp-agent-v2/client-events.jsonl)

## Independent reproduction

Use a clean, separate checkout of `7f110c6`, the project's MCP dependencies, local HydraDB at port 18443 with the ignored `.state/hydra-token` file, and an existing Claude Code login. Follow the repository setup in [README](../README.md), then choose a new output directory:

```bash
.venv/bin/python scripts/mcp_agent_probe.py prepare --output results/mcp-agent-reproduction
.venv/bin/python scripts/mcp_agent_probe.py run --prepared results/mcp-agent-reproduction
```

Preparation makes no model request and verifies connectivity in separate empty state. `run` makes a paid trajectory with a configured **$4 budget and 600-second timeout**. It creates a fresh workspace, preserves failures, and refuses to overwrite an attempt. Model behavior can vary; report every reproduction outcome rather than retrying until success. This demonstration is separate from the [retrieval comparison](AGENT_RESULTS.md).
