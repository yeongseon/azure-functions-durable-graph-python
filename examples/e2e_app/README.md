# e2e_app — real-Azure certification app

This app exists **only** for the release gate. The `e2e-azure` GitHub workflow
deploys it to a temporary Azure Functions Consumption (Y1) host, runs
`tests/e2e` against it, records an `azure-cert` artifact, then deletes the
resource group.

It differs from the user-facing `examples/data_pipeline` in two ways:

1. **Candidate under test.** `requirements.txt` does not pin
   `azure-functions-durable-graph`. The workflow builds a wheel from the release
   commit, drops it in `wheels/`, and appends the local wheel path so the
   deployed host runs the exact source being certified (not the PyPI release).
2. **Dedicated deterministic graph.** It registers a single terminal graph
   (`e2e_pipeline`: extract → transform → load, no external events, no LLM) so
   the live orchestration assertion is deterministic.

To reproduce locally you must first place a built wheel in `wheels/` and add it
to `requirements.txt`, then `func start`.
