# Azure Functions Durable Graph

> Part of the **Azure Functions Python DX Toolkit** — dogfood-tested by [azure-functions-cookbook-python](https://github.com/yeongseon/azure-functions-cookbook-python).


[![PyPI](https://img.shields.io/pypi/v/azure-functions-durable-graph.svg)](https://pypi.org/project/azure-functions-durable-graph/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/azure-functions-durable-graph/)
[![CI](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-durable-graph-python/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-durable-graph-python)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://yeongseon.github.io/azure-functions-durable-graph-python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read this in: [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

> **Alpha Notice** — This package is in early development (`0.1.0a0`). APIs may change without notice between releases. Do not use in production without thorough testing.

Manifest-first graph runtime for **Azure Functions** with **Durable Functions** orchestration.

---

Part of the **Azure Functions Python DX Toolkit**
→ Bring FastAPI-like developer experience to Azure Functions

## Why this exists

Running graph-shaped workflows on Azure Functions is harder than it should be:

- **Orchestrator determinism** — Durable Functions orchestrators must be deterministic; calling LLMs or tools directly inside them breaks replay safety
- **Graph-to-runtime gap** — Translating a node/edge graph design into Durable Functions activities requires repetitive plumbing
- **No standard runtime** — Each team builds its own wiring between graph definitions and Durable Functions primitives

## What it does

- **Manifest-first runtime** — compile graph definitions into a stable, versioned manifest that the orchestrator reads without violating determinism
- **Automatic HTTP API** — `POST /api/graphs/{graph_name}/runs`, `GET /api/runs/{instance_id}`, event injection, cancellation, and health endpoints are registered automatically
- **Deterministic orchestrator loop** — all user logic (node execution, routing, event handling) runs in Durable Functions activities, never inside the orchestrator
- **Conditional routing & external events** — support for branching workflows and human-in-the-loop patterns via `RouteDecision`

## Scope

- Azure Functions Python **v2 programming model**
- Durable Functions orchestration via `azure-functions-durable`
- Pydantic v2-based state models
- Graph topologies: sequential, conditional, and event-driven

This package is independent of LangGraph and has no dependency on it. The name was inspired by LangGraph's node/edge model.

## Features

- `ManifestBuilder` API for declaring graph nodes, routes, and event handlers
- Deterministic Durable Functions orchestrator with configurable execution loop
- Typed state management via Pydantic v2 models
- Built-in HTTP endpoints: start run, get status, send event, cancel, health, OpenAPI
- Graph versioning with manifest-derived hash for safe deployments

## Installation

```bash
pip install azure-functions-durable-graph
```

Your Azure Functions app should also include:

```text
azure-functions
azure-functions-durable
azure-functions-durable-graph
```

For local development:

```bash
git clone https://github.com/yeongseon/azure-functions-durable-graph-python.git
cd azure-functions-durable-graph
pip install -e .[dev]
```

## Quick Start

```python
from pydantic import BaseModel

from azure_functions_durable_graph import DurableGraphApp, ManifestBuilder, RouteDecision


class MyState(BaseModel):
    message: str
    processed: bool = False


def process_message(state: MyState) -> dict:
    return {"processed": True}


def finalize(state: MyState) -> dict:
    return {"message": f"Done: {state.message}"}


builder = ManifestBuilder(graph_name="my_graph", state_model=MyState)
builder.set_entrypoint("process")
builder.add_node("process", process_message, next_node="finalize")
builder.add_node("finalize", finalize, terminal=True)

registration = builder.build()

runtime = DurableGraphApp()
runtime.register_registration(registration)
app = runtime.function_app
```

### What you get

1. `POST /api/graphs/my_graph/runs` — starts a new graph execution
2. `GET /api/runs/{instance_id}` — polls run status
3. `GET /api/health` — lists registered graphs
4. `GET /api/openapi.json` — OpenAPI document

## Durable operational model

A few durable-specific concepts matter before you go to production. Each links to
the full write-up in [Durable Concepts](docs/durable-concepts.md).

1. **Orchestrator lifecycle** — the orchestrator is deterministic and replay-safe:
   it only reads the manifest, calls activities, and waits for events. It pins the
   graph version via `graph_hash` in `OrchestrationInput` and never runs LLM/tool
   code directly.
2. **Manifest → registration → runtime** — `ManifestBuilder.build()` compiles a
   validated, hash-versioned `GraphRegistration`; `register_registration()` stores
   it; a run pins the current `graph_hash` and executes activities against it.
3. **State-merge semantics** — a handler returning a `dict` is **shallow-merged**
   (top-level keys only), a `BaseModel` **replaces** the state, and `None` leaves
   it **unchanged**. Nested dicts are not deep-merged — return the full nested
   object or a full model to update them.
4. **Events & resume** — a route handler can return
   `RouteDecision.wait_for_event(event_name, resume_node)` to pause the run; deliver
   the event with `POST /api/runs/{instance_id}/events/{event_name}` and execution
   resumes at `resume_node` after the event handler merges its payload.
5. **`host.json` is required** — Durable Functions needs the Durable Task extension
   and an extension bundle. See the [Deployment](docs/deployment.md) guide.
6. **Top gotchas** — shallow-merge surprises, forgetting `host.json`, and reusing a
   task hub across environments. See [Troubleshooting](docs/troubleshooting.md).

## When to use

- You need graph-shaped LLM workflows on Azure Functions
- You want deterministic Durable Functions orchestration without manual activity wiring
- You need human-in-the-loop approval patterns (external events)
- You want versioned graph deployments with manifest-derived hashing

## Examples

| Example | Pattern | Key Concepts |
|---------|---------|--------------|
| [Data Pipeline](examples/data_pipeline/) | Sequential | `next_node` chaining, state accumulation — deterministic multi-step orchestration |
| [Content Classifier](examples/content_classifier/) | Conditional routing | `RouteDecision.next()`, fan-in topology — route handlers |
| [Support Agent](examples/support_agent/) | Human-in-the-loop | `wait_for_event` / external events — pause-and-resume approval flow |

## Documentation

- Project docs live under `docs/`
- **New to durable graphs?** Read [Durable Concepts](docs/durable-concepts.md)
- **Deploying to Azure?** See the [Deployment](docs/deployment.md) guide and [Choose a Plan](docs/choose-a-plan.md)
- Smoke-tested examples live under `examples/`
- Product requirements: `PRD.md`
- Design principles: `DESIGN.md`
## Ecosystem

Part of the **Azure Functions Python DX Toolkit**:

| Package | Role |
|---------|------|
| [azure-functions-openapi-python](https://github.com/yeongseon/azure-functions-openapi-python) | OpenAPI spec generation and Swagger UI |
| [azure-functions-validation-python](https://github.com/yeongseon/azure-functions-validation-python) | Request/response validation and serialization |
| [azure-functions-db-python](https://github.com/yeongseon/azure-functions-db-python) | Database bindings for SQL, PostgreSQL, MySQL, SQLite, and Cosmos DB |
| [azure-functions-langgraph-python](https://github.com/yeongseon/azure-functions-langgraph-python) | LangGraph deployment adapter for Azure Functions |
| [azure-functions-scaffold-python](https://github.com/yeongseon/azure-functions-scaffold-python) | Project scaffolding CLI |
| [azure-functions-logging-python](https://github.com/yeongseon/azure-functions-logging-python) | Structured logging and observability |
| [azure-functions-doctor-python](https://github.com/yeongseon/azure-functions-doctor-python) | Pre-deploy diagnostic CLI |
| **azure-functions-durable-graph-python** | Manifest-first graph runtime with Durable Functions *(experimental)* |
| [azure-functions-knowledge-python](https://github.com/yeongseon/azure-functions-knowledge-python) | Knowledge retrieval (RAG) decorators |
| [azure-functions-cookbook-python](https://github.com/yeongseon/azure-functions-cookbook-python) | Dogfood examples — runnable recipes that exercise the full toolkit |

## For AI Coding Assistants

This repository includes `llms.txt` and `llms-full.txt` in the root directory.
These files provide comprehensive package and API information optimized for LLM context windows.

- **`llms.txt`** — Quick reference with core API, installation, and quick-start example
- **`llms-full.txt`** — Complete reference with full signatures, patterns, design principles, and ecosystem context

Use these files to get better context when working with this package in AI-assisted coding environments.

## Disclaimer

This project is an independent community project and is not affiliated with,
endorsed by, or maintained by Microsoft.

Azure and Azure Functions are trademarks of Microsoft Corporation.

## License

MIT
