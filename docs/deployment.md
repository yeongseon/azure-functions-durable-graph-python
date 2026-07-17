# Deployment

This page covers what you need to run an `azure-functions-durable-graph` app on
Azure: the required `host.json` configuration, extension bundles, the Durable
Functions storage backend, and recommended deployment patterns.

## Prerequisites

- Azure Functions Python **v2 programming model**.
- The Durable Functions extension (via the extension bundle, below).
- An Azure Storage account (or another supported Durable Task backend) for the
  orchestration history and control queues.

## `host.json`

Durable Functions requires the Durable Task extension and an extension bundle.
A minimal `host.json` looks like this:

```json
{
  "version": "2.0",
  "functionTimeout": "00:10:00",
  "extensions": {
    "durableTask": {
      "hubName": "durablegraphhub"
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

Notes:

- **`extensionBundle`** pulls in the Durable Task extension without a manual
  `.csproj`/`extensions.csproj` build. Use the `[4.*, 5.0.0)` range for the Python
  v2 model.
- **`durableTask.hubName`** names the task hub. Give each app (and each
  environment) a distinct hub name so their histories do not collide when they
  share a storage account.
- **`functionTimeout`** applies to the individual activity/HTTP function
  executions, not to the overall orchestration. Long-running graphs that wait on
  external events can run far beyond this timeout because the wait is durable.

## `requirements.txt`

Your function app must ship the durable runtime alongside this package:

```text
azure-functions
azure-functions-durable
azure-functions-durable-graph
```

!!! note "Do not pin `azure-functions-worker`"
    The Python worker is managed by the Azure Functions platform; never add it to
    `requirements.txt`.

## Durable Task storage backend

By default Durable Functions stores orchestration state and queues in Azure
Storage, configured through the `AzureWebJobsStorage` connection string. For
production:

- Use a **dedicated storage account** per app/environment.
- Keep the task hub name stable across deploys so in-flight orchestrations are
  not orphaned.
- Consider the Netherite or MSSQL backends for high-throughput workloads (see the
  official Durable Functions storage-providers documentation).

## Recommended Azure patterns

- **Plan choice** — the graph orchestrator waits durably, so it does not hold a
  worker while idle. The Consumption plan works for bursty workloads; use Premium
  or Dedicated plans when you need VNET integration, no cold starts, or longer
  guaranteed execution. (See [Choose a plan](choose-a-plan.md).)
- **Versioned deploys** — because runs are fenced to their `graph_hash`, you can
  deploy a changed graph while older runs finish on their original topology. Keep
  the task hub name stable so those in-flight runs resume.
- **Observability** — enable Application Insights (`applicationInsights` in
  `host.json`) to trace orchestrations and activities. Run
  `custom_status` surfaces the current node and any `waiting_for_event` state via
  `GET /api/runs/{instance_id}`.
- **Scaling** — activities scale out independently of the orchestrator. Keep node
  handlers idempotent where possible so Durable Functions retries are safe.

## Verifying a deployment

After deploying, confirm the app is healthy:

```bash
GET /api/health            # lists registered graphs
GET /api/openapi.json      # returns the OpenAPI document
```

Then start a run and poll it:

```bash
POST /api/graphs/{graph_name}/runs
GET  /api/runs/{instance_id}
```

## See also

- [Durable Concepts](durable-concepts.md) — determinism, state merge, events.
- [Configuration](configuration.md) — building and registering graphs.
- [Troubleshooting](troubleshooting.md) — common runtime issues.
