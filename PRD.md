# PRD - azure-functions-durable-graph

## Overview

`azure-functions-durable-graph` is a **manifest-first graph runtime** for the Azure Functions Python v2
programming model with Durable Functions orchestration.

It targets developers who build LLM-powered graph workflows and need a deterministic, type-safe
bridge between graph definitions and Durable Functions primitives — without writing repetitive
orchestration plumbing.

## Problem Statement

Running graph-shaped LLM workflows on Azure Functions hits the same friction every time:

- **Orchestrator determinism** — Durable Functions orchestrators must be deterministic;
  calling LLMs or tools directly inside them breaks replay safety.
- **Graph-to-runtime gap** — translating a LangGraph-style node/edge design into
  Durable Functions activities requires repetitive boilerplate.
- **No standard runtime** — each team builds its own wiring between graph definitions
  and Durable Functions primitives, with no shared conventions.
- **State drift** — without typed state contracts, dict-passing between nodes makes
  bugs hard to trace across the execution graph.

## Goals

- Provide a `ManifestBuilder` API that compiles graph definitions into a stable, versioned manifest.
- Keep the orchestrator deterministic — all user logic runs in Durable Functions activities.
- Automatically register HTTP endpoints (start run, poll status, send event, cancel, health, OpenAPI).
- Support sequential, conditional, and event-driven graph topologies.
- Enforce typed state contracts via Pydantic v2 models.
- Enable graph versioning with manifest-derived hashing for safe deployments.

## Non-Goals

1. Building a full web framework or replacing Azure Functions routing.
2. Automatic LangGraph-to-manifest translation (reserved for a future adapter release).
3. LLM client management, prompt engineering, or model hosting.
4. Authentication and authorization.
5. Data persistence beyond Durable Functions state.
6. Providing global mutable state such as handler registries.

## Primary Users

- Azure Functions Python developers building LLM-powered workflows
- Teams that need human-in-the-loop approval patterns on Azure
- Developers who want typed, versioned graph deployments without manual activity wiring

## Execution Pipeline

A graph execution runs through the following stages:

```
ManifestBuilder
  │
  ▼
GraphManifest (compiled, versioned)
  │
  ▼
GraphRegistry (stored for runtime lookup)
  │
  ▼
DurableGraphApp
  ├── HTTP Endpoints (start, status, event, cancel, health, openapi)
  └── Durable Orchestrator
        │
        loop For each node
        │   ├── execute_node activity (handler invocation + state merge)
        │   ├── resolve_route activity (routing decision)
        │   └── apply_event activity (if wait_for_event)
        │
        ▼
      Final state returned
```

## Key Scenarios

### Sequential graph

Nodes chained with `next_node`. Simplest topology.

### Conditional routing

A route handler inspects state and returns a `RouteDecision` pointing to different
next nodes based on business logic.

### Human-in-the-loop (external events)

A route handler returns `RouteDecision.wait_for_event(...)`. The orchestrator pauses,
waits for an external event, applies the event payload via an event handler activity,
and resumes at a configurable node.

### Multiple graph registration

A single `DurableGraphApp` can host multiple graphs, each with independent manifests,
endpoints, and versioned topologies.

## Success Metrics

- Zero non-deterministic code inside the orchestrator function.
- All graph topologies (sequential, conditional, event-driven) covered by unit tests.
- Coverage threshold ≥ 80%.
- Public APIs fully typed with `py.typed` marker.
- Documentation and examples synchronized with runtime behavior.

## Milestones

| Phase | Scope |
|-------|-------|
| `0.1.x` (current) | Core runtime: ManifestBuilder, orchestrator loop, HTTP endpoints, state management |
| `0.2.x` | Graph composition, multi-graph orchestration improvements, extended routing patterns |
| `0.3.x` | LangGraph adapter boundary (automatic translation from StateGraph) |
| `1.0.0` | Stable API, production-ready, full documentation |

## Compatibility

- Python: `>=3.10, <3.15`
- Runtime: Azure Functions Python v2 programming model
- Orchestration: `azure-functions-durable`
- State models: Pydantic v2

## Related Documents

- [DESIGN.md](DESIGN.md) — architectural boundaries and design principles
- [CONTRIBUTING.md](CONTRIBUTING.md) — development workflow
- [docs/architecture.md](docs/architecture.md) — detailed architecture reference
