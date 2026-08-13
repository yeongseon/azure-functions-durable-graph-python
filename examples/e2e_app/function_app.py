"""E2E certification Function App for azure-functions-durable-graph.

Deployed to a real Azure Functions Consumption (Y1) host by the e2e-azure
workflow. Registers a single deterministic, terminal durable graph
(`e2e_pipeline`) and exposes the native Durable HTTP routes:

    GET  /api/health
    POST /api/graphs/e2e_pipeline/runs
    GET  /api/runs/{instance_id}

Anonymous auth so the certification suite can drive it without a function key;
this is a throwaway single-release host with no sensitive data.
"""

from graph import registration

from azure_functions_durable_graph import DurableGraphApp

runtime = DurableGraphApp()
runtime.register_registration(registration)

app = runtime.function_app
