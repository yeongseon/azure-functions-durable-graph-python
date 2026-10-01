# Azure Functions Durable Graph

Manifest-first graph runtime for Azure Functions with Durable Functions orchestration.

`azure-functions-durable-graph` compiles graph-shaped workflows into Azure Functions
applications that run on Durable Functions without violating orchestrator determinism.
All user logic (LLM calls, tool invocations, routing decisions) executes in activities,
keeping the orchestrator replay-safe.

!!! tip "5-second rule"
    Define your graph with `ManifestBuilder`, register it with `DurableGraphApp`,
    and get a full HTTP API for starting runs, polling status, and injecting events.

## Quick Copy-Paste Example

```python
from pydantic import BaseModel

from azure_functions_durable_graph import DurableGraphApp, ManifestBuilder


class MyState(BaseModel):
    message: str
    processed: bool = False


def process(state: MyState) -> dict:
    return {"processed": True}


def finalize(state: MyState) -> dict:
    return {"message": f"Done: {state.message}"}


builder = ManifestBuilder(graph_name="my_graph", state_model=MyState)
builder.set_entrypoint("process")
builder.add_node("process", process, next_node="finalize")
builder.add_node("finalize", finalize, terminal=True)

runtime = DurableGraphApp()
runtime.register_registration(builder.build())
app = runtime.function_app
```

### What you get

1. `POST /api/graphs/my_graph/runs` starts a Durable Functions orchestration.
2. `GET /api/runs/{instance_id}` polls run status and final state.
3. `GET /api/health` lists registered graphs.
4. `GET /api/openapi.json` returns an OpenAPI document.

!!! note "Determinism guarantee"
    The orchestrator only reads the manifest, calls activities, and waits for events.
    It never calls LLMs, tools, or performs network I/O.

## Why teams use this package

- **No plumbing**: graph-to-Durable-Functions wiring is handled automatically.
- **Replay-safe**: orchestrator determinism is enforced by architecture, not discipline.
- **Typed state**: Pydantic v2 models for graph state with merge semantics.
- **Human-in-the-loop**: external event support for approval workflows.
- **Versioned graphs**: manifest-derived hash for safe deployments.

## Feature Snapshot

### Runtime capabilities

- Sequential node execution with automatic state merging.
- Conditional routing via `RouteDecision`.
- External event injection and resume (`wait_for_event`).
- Graph cancellation via HTTP endpoint.
- Minimal OpenAPI document generation.

### Developer experience

- `ManifestBuilder` fluent API for declaring graphs.
- `GraphManifest` with version and manifest-derived hash.
- `DurableGraphApp` wires everything into Azure Functions automatically.

## Where to go next

- Start with [Quickstart](getting-started.md).
- Understand the runtime model in [Durable Concepts](durable-concepts.md).
- Learn the manifest builder in [Configuration](configuration.md).
- See full patterns in [Usage](usage.md).
- Ship to Azure with the [Deployment](deployment.md) guide and [Choose a Plan](choose-a-plan.md).
- Browse the support agent example in [Examples](examples/support_agent.md).
- Explore public APIs in [API Reference](api.md).

## Compatibility

- Python 3.10+
- Azure Functions Python v2 programming model
- Azure Durable Functions
- Pydantic v2

For dependency setup details, see [Installation](installation.md).

## Need help?

- Common fixes: [Troubleshooting](troubleshooting.md)
- Frequent questions: [FAQ](faq.md)
- Contribution workflow: [Guidelines](contributing.md)
