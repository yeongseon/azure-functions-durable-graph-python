# Troubleshooting

This guide covers the most common issues when using
`azure-functions-durable-graph` in Azure Functions Python v2 apps with Durable Functions.

If you are still setting up, read [Installation](installation.md) and
[Quickstart](getting-started.md) first.

## Fast triage checklist

Before deep debugging, confirm:

1. Python 3.10+
2. Pydantic v2 installed
3. `azure-functions` and `azure-functions-durable` installed
4. Azure Functions Python v2 decorator model in use
5. `host.json` includes Durable Functions extension bundle
6. `app = runtime.function_app` is the module-level variable in `function_app.py`

## Import and environment issues

### `ImportError: No module named 'azure_functions_durable_graph'`

Cause:

- package not installed in active environment

Fix:

- reinstall package in the same interpreter used by the function host
- verify environment activation before running host

### `ImportError: No module named 'azure.durable_functions'`

Cause:

- `azure-functions-durable` dependency missing

Fix:

- add `azure-functions-durable` to dependencies
- ensure local and deployment environments both include it

### Pydantic version mismatch

Symptoms:

- attribute errors or model behavior inconsistent with v2

Cause:

- Pydantic v1 installed transitively

Fix:

- pin and install `pydantic>=2,<3`

!!! warning "Version drift"
    If local tests pass but deployed runtime fails, compare the lockfile and the
    deployed package set.

## Graph registration issues

### Problem: `ValueError: graph 'X' is already registered`

Cause:

- calling `register_registration()` twice with the same graph name

Fix:

- ensure each graph name is unique across all registrations

### Problem: `ValueError: entrypoint must be set before building the manifest`

Cause:

- calling `builder.build()` without `builder.set_entrypoint(...)`

Fix:

- call `builder.set_entrypoint("node_name")` before `build()`

### Problem: `ValueError: entrypoint must reference a registered node`

Cause:

- entrypoint name doesn't match any node added via `add_node`

Fix:

- verify node names match exactly (case-sensitive)

### Problem: `ValueError: terminal nodes cannot define next_node or route_handler_name`

Cause:

- `add_node(..., terminal=True, next_node="something")`

Fix:

- terminal nodes should not have `next_node` or `route`

## Runtime issues

### Problem: orchestration fails immediately

Possible causes:

- `host.json` missing Durable Functions extension bundle
- Azure Functions host version incompatibility

Fix:

- ensure `host.json` contains:

```json
{
  "version": "2.0",
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

### Problem: node handler exception causes orchestration failure

Cause:

- unhandled exception in a node or route handler

Fix:

- add error handling in your handlers
- use Durable Functions retry policies for transient failures

### Problem: `KeyError: unknown graph 'X'`

Cause:

- requesting a graph name that was not registered

Fix:

- verify graph name in API request matches `graph_name` in the manifest

### Problem: external event not received

Cause:

- event name mismatch between route decision and HTTP request
- wrong instance ID

Fix:

- verify `event_name` in `RouteDecision.wait_for_event()` matches the URL path
- verify `instance_id` in the URL matches the running orchestration

## State issues

### Problem: state fields not updating

Cause:

- handler returning `None` (state unchanged)
- handler returning wrong key names

Fix:

- return a dict with keys matching the state model field names
- verify dict keys are correct

### Problem: `TypeError: unsupported state merge result`

Cause:

- handler returning an unsupported type (not dict, BaseModel, or None)

Fix:

- return `dict`, `BaseModel` instance, or `None` from handlers

## Testing issues

### Problem: `DurableGraphApp` is `None` in tests

Cause:

- `azure-functions` or `azure-functions-durable` not installed in test environment

Fix:

- install Azure dependencies in dev environment
- or test manifest building and handler logic separately (without `DurableGraphApp`)

### Problem: `RuntimeError: no running event loop` in async tests

Cause:

- async handler test executed in sync-only test context

Fix:

- configure `asyncio_mode = "auto"` in `pyproject.toml` (already configured)
- or use `@pytest.mark.asyncio`

## Still stuck?

- Compare behavior with examples in `examples/`
- Confirm your handler signatures match docs exactly
- Review [Configuration](configuration.md) parameter semantics
- Review [Usage](usage.md) patterns
