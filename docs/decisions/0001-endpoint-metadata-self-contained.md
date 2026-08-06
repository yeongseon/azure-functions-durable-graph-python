# ADR-0001: Endpoint metadata namespace — remain self-contained

- **Status:** Accepted
- **Date:** 2026-08-07
- **Issue:** [azure-functions-durable-graph#111](https://github.com/yeongseon/azure-functions-durable-graph/issues/111)
- **Umbrella:** [azure-functions-validation#270](https://github.com/yeongseon/azure-functions-validation-python/issues/270)

## Context

The DX Toolkit convergence umbrella defines a shared `endpoint` metadata
namespace so that Azure Functions apps can expose their request/response
schemas for cross-package OpenAPI discovery. Producer packages
(`azure-functions-validation`, `azure-functions-langgraph`) write a payload —
`{version, request_body, request_body_required, parameters, responses}` — onto
each route handler under the `_azure_functions_metadata["endpoint"]` attribute,
and the consumer (`azure-functions-openapi`) reads it **without importing the
producer** to synthesise an OpenAPI document.

`azure-functions-durable-graph` was evaluated (issue #111) for whether it should
also emit this namespace, or explicitly remain self-contained.

## Decision

`azure-functions-durable-graph` does **not** emit the shared `endpoint`
metadata namespace. It keeps deriving its own OpenAPI document from the durable
blueprint (`build_openapi`).

## Rationale

1. **Standalone app, not a route-decorator library.** `DurableGraphApp`
   instantiates its own `func.FunctionApp()`, registers a fixed set of runtime
   routes, and serves its own `/api/openapi.json`. The `endpoint` namespace
   exists to enable *discovery by an external consumer that scans a shared
   `FunctionApp`* alongside other decorated routes. Durable-graph handlers are
   never mounted into such a host app, so there is no discovery problem for the
   namespace to solve.
2. **Fixed contracts, not per-graph schemas.** The namespace delivers the most
   value where each registered entity produces *distinct* request/response
   models (as in `azure-functions-langgraph`, where every graph has its own
   models). Durable-graph exposes exactly six framework endpoints whose HTTP
   contracts are identical for every registered graph. Per-user state lives
   inside `OrchestrationInput.initial_state` as free-form JSON, not as a
   distinct request/response body.
3. **The 202 check-status response is owned by the durable SDK.**
   `start_graph_run` returns `client.create_check_status_response(...)`, a
   durable-functions SDK object rather than a Pydantic model. Forcing it into a
   namespace `responses` entry would require a synthetic, drift-prone schema
   that does not correspond to a real model.
4. **Spec equivalence is achievable without the namespace.** Cross-package
   OpenAPI spec equivalence (the umbrella's end goal, tracked by
   `azure-functions-cookbook#119`) can be reached by enhancing `build_openapi`
   to emit `requestBody`/`responses` directly from the fixed contracts in
   `contracts.py` — no namespace indirection required.

## Consequences

- Durable-graph gains no runtime dependency on `azure-functions-validation` or
  `azure-functions-openapi`.
- A regression test (`tests/test_endpoint_metadata_decision.py`) asserts that no
  runtime handler carries the `_azure_functions_metadata["endpoint"]` attribute,
  so accidental convergence is caught in review.
- Producing full `requestBody`/`responses` schemas in `build_openapi` (for
  cookbook#119 spec equivalence) is tracked separately as a follow-up
  enhancement.
- **Revisit trigger:** if durable-graph ever supports mounting its routes into
  an external `FunctionApp` (plugin/compose mode) that is scanned by
  `azure-functions-openapi`, this decision must be re-evaluated.
