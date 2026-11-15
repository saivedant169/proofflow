# Browser CSV acceptance tests

Run these from `frontend/` with this repository's Python dependencies and an existing, reachable HydraDB OSS instance. The default HydraDB URL is `http://127.0.0.1:18443`. Supply credentials through `PROOFFLOW_HYDRA_TOKEN_FILE` (an absolute path to the token file) or `PROOFFLOW_HYDRA_TOKEN`. If Python is not in the checkout's `.venv`, set `PROOFFLOW_E2E_PYTHON` to its executable.

```sh
npm ci
npx playwright install chromium
npm run test:e2e
npm run test:e2e:negative
```

The six acceptance tests run in Chromium against built frontend assets and real HydraDB. Each run starts its own loopback app servers on ports `18780` and `18781` (overridable with `PROOFFLOW_E2E_PORT` and `PROOFFLOW_E2E_FAULT_PORT`) and creates new session state and graph namespaces. The second server injects one failure immediately after a real orders source commit. No app restart or production fault endpoint is involved.

The negative control runs the same FX test in a disposable test server with a deliberately incorrect one-cent conversion. Its command succeeds only if the underlying Playwright run fails at the unchanged rendered values assertion and shows the expected one-cent difference in both reports. An unrelated failure or a passing FX test makes the control command fail.

The runner prints a unique evidence directory under the system temporary directory or an absolute `PROOFFLOW_E2E_OUTPUT_DIR` outside the registered Git worktrees. `results.json` is the Playwright report, `assertions.jsonl` records checks that passed, and `negative-control.json` records the verified deliberate failure. Keep raw traces and session state private: they can include browser session credentials. Neither command writes these artifacts into the checkout or exercises a hosted ProofFlow app.
