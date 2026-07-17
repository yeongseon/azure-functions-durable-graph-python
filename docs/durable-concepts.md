# Durable Concepts

This page consolidates the durable-specific knowledge you need to build correct
graphs on `azure-functions-durable-graph`. It complements the
[Architecture](architecture.md) and [Usage](usage.md) pages by focusing on the
runtime semantics that are unique to running a graph as an Azure **Durable
Functions** orchestration.

## Orchestrator determinism and replay safety

Azure Durable Functions re-executes ("replays") the orchestrator function every
time the orchestration makes progress. For replay to produce a consistent
history, the orchestrator body must be **deterministic**: it may not call LLMs,
perform network or database I/O, read the clock, or generate random values
directly.

This package enforces determinism by architecture rather than by discipline. The
orchestrator (`afdg_orchestrator`) only ever:

1. reads the compiled manifest for the pinned `graph_hash`,
2. yields `context.call_activity(...)` to run your code in an **activity**, and
3. yields `context.wait_for_external_event(...)` to pause for human input.

All side-effecting logic — node execution, route resolution, and event
application — runs inside activity functions (`afdg_execute_node`,
`afdg_resolve_route`, `afdg_apply_event`). Activities are executed exactly once
and their results are recorded in the orchestration history, so replay never
re-runs your LLM calls or tool invocations.

!!! warning "Keep node/route/event handlers in activities"
    Never call an LLM, HTTP API, or database from code that runs inside the
    orchestrator. In this package that is impossible by design: your handlers are
    only ever invoked from activity triggers. If you extend the runtime, preserve
    that boundary.

## Manifest → registration → runtime flow

1. **Author** — declare nodes, routes, and event handlers with
   [`ManifestBuilder`](api.md).
2. **Compile** — `builder.build()` produces a `GraphRegistration` wrapping an
   immutable `GraphManifest`. The manifest is validated at build time (duplicate
   node detection, terminal-node constraints, `next_node` reference checks, and
   BFS reachability from the entrypoint).
3. **Version** — the manifest is serialized to canonical JSON and hashed
   (`sha256`, truncated) into `graph_hash`. This hash identifies the exact graph
   topology.
4. **Register** — `DurableGraphApp.register_registration(...)` stores the
   registration in the in-memory `GraphRegistry`, keyed both by `graph_name`
   (latest) and by the composite `graph_name:graph_hash` (every version).
5. **Run** — an incoming `POST /api/graphs/{graph_name}/runs` reads the current
   manifest, pins its `graph_hash` into the `OrchestrationInput`, and starts the
   orchestration. Every subsequent activity call carries that same `graph_hash`,
   so an in-flight run always executes against the graph version it started with —
   even if the app is redeployed with a changed graph mid-run.

## State-merge semantics

After a node or event handler runs, its return value is merged into the current
state by `_merge_state`. The merge rule depends on the return type:

| Handler returns        | Merge behavior                                              |
|------------------------|-------------------------------------------------------------|
| `dict`                 | **Shallow merge** — top-level keys overwrite current state.  |
| `BaseModel` (Pydantic) | **Replace** — the returned model becomes the new state.     |
| `None`                 | **No change** — current state is preserved.                 |

Any other return type raises `TypeError`.

!!! caution "Shallow merge only"
    A returned `dict` is merged one level deep (`state.update(result)`). Nested
    dictionaries are replaced wholesale, not deep-merged. To update a nested
    field, read the current value, modify a copy, and return the full nested
    object — or return a full `BaseModel` to replace the state entirely.

## Events, `wait_for_event`, and resume

Graphs support human-in-the-loop and long-running-wait patterns through external
events. A route handler requests a pause by returning a
`RouteDecision.wait_for_event(event_name=..., resume_node=...)`.

When the orchestrator receives that decision it:

1. records `waiting_for_event` and `resume_node` in the run's `custom_status`,
2. yields `context.wait_for_external_event(event_name)` and suspends,
3. on delivery, calls `afdg_apply_event` to run your `event_handler(state,
   payload)` and merge its result into state, then
4. continues execution at `resume_node`.

Deliver an event from a client with:

```bash
POST /api/runs/{instance_id}/events/{event_name}
Content-Type: application/json

{ "approved": true }
```

The endpoint accepts any JSON payload (object, array, scalar, or `null`) and
returns `202 Accepted`. The payload is passed verbatim to the matching event
handler.

## `graph_hash` versioning

`graph_hash` is derived from the manifest contents, so any change to nodes,
routing, or event wiring produces a new hash. Because runs are fenced to the hash
they started with, you can deploy a changed graph while older runs are still in
flight and they will continue to completion on their original topology. Re-running
`register_registration` for the *same* `graph_name` and `graph_hash` raises
`ValueError` (duplicate registration).

## Running LLM and tool work in activities

Put all expensive or non-deterministic work — model calls, retrieval, database
access — inside your **node** and **event** handlers. Those handlers only run
from activity triggers, so:

- they may be `async` (the runtime awaits them via `_maybe_await`),
- their results are durably recorded and never re-executed on replay, and
- failures are logged with graph/hash/node context and re-raised so Durable
  Functions applies its retry/failure semantics.

## See also

- [Architecture](architecture.md) — module and sequence diagrams.
- [Usage](usage.md) — end-to-end patterns and code.
- [Deployment](deployment.md) — `host.json`, extension bundles, and Azure setup.
- [Troubleshooting](troubleshooting.md) — common runtime issues.
