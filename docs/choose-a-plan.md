# Choose a Plan

Which Azure Functions hosting plan should you use for an
`azure-functions-durable-graph` app? Because the graph orchestrator waits
**durably** — it releases its worker while paused on `wait_for_external_event`
and between activity calls — plan choice is mostly about cold-start tolerance,
networking, and execution-time guarantees rather than about keeping a process
alive for the life of a run.

| Plan | Good fit when | Trade-offs |
|------|---------------|-----------|
| **Consumption** | Bursty or low-volume workloads; you want pay-per-execution and automatic scale-to-zero. | Cold starts; per-execution timeout limits apply to individual activities/HTTP calls (not to the durable wait). |
| **Flex Consumption / Premium** | You need no cold starts, VNET integration, or longer guaranteed per-execution time. | Higher baseline cost; pre-warmed instances. |
| **Dedicated (App Service)** | You already run an App Service Plan and want to co-locate the app, or need "always on". | You manage scaling; no scale-to-zero. |

## Guidance

- **Long human-in-the-loop waits are fine on any plan.** A graph paused on an
  external event is not consuming a worker, so a run can span hours or days even
  on Consumption.
- **Individual activities must fit the per-execution timeout.** Keep node and
  event handlers below your plan's `functionTimeout`. Split very long work into
  multiple nodes.
- **Choose Premium/Dedicated for VNET or no-cold-start requirements**, e.g. when
  node handlers call private endpoints (databases, private model gateways).

For authoritative, up-to-date limits, see the official Azure Functions hosting
plans documentation. For `host.json`, storage, and extension-bundle setup, see
[Deployment](deployment.md).
