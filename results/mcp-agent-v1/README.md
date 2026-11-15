# Retained first MCP client attempt

This attempt failed before calling any tool: the v1 launch used `--safe-mode`, which suppressed the explicitly configured MCP server. Fable correctly reported that no tools were available. The summary preserves the failure, zero tool requests, observed model, usage and $0.037144 reported cost.

`configuration_failure.json` is a hash-linked extract of the original initialization and final response. Raw streams and environment-specific configuration remain in the builder’s private archive because initialization can include unrelated account/session metadata. A separately frozen v2 attempt repairs only the CLI isolation configuration; it does not replace this result or change the task prompt.
