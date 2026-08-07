"""In-process durable-orchestration replay harness for e2e scenarios.

These "e2e" tests do **not** require a live Azure Functions host or Azurite.
Instead they drive the real :func:`runtime.orchestrate` generator against real
activity functions and a real :class:`GraphRegistry`, faking only the Durable
``DurableOrchestrationContext`` surface that the orchestrator touches.

This exercises the full graph lifecycle — node execution, routing, external
event waits, replay determinism, and hash-fencing across redeploys — end to end
through the public runtime, while still running in ordinary CI (no I/O).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from azure_functions_durable_graph import runtime
from azure_functions_durable_graph.registry import GraphRegistry


class EventNotDeliveredError(TimeoutError):
    """Raised when the orchestrator waits for an event that was never supplied.

    Subclasses :class:`TimeoutError` to mirror the real Durable Functions
    behaviour, where an unfulfilled ``wait_for_external_event`` eventually times
    out rather than resolving.
    """


@dataclass
class _ActivityTask:
    name: str
    payload: dict[str, Any]


@dataclass
class _EventTask:
    name: str


@dataclass
class RecordingContext:
    """Minimal fake ``DurableOrchestrationContext`` for in-process replay.

    Only the members that :func:`runtime.orchestrate` actually calls are
    implemented: ``get_input``, ``set_custom_status``, ``call_activity`` and
    ``wait_for_external_event``. Each ``call_activity`` / ``wait_for_external_event``
    returns a lightweight task marker that the driver interprets.
    """

    _input: dict[str, Any]
    statuses: list[dict[str, Any]] = field(default_factory=list)

    def get_input(self) -> dict[str, Any]:
        return self._input

    def set_custom_status(self, payload: dict[str, Any]) -> None:
        self.statuses.append(payload)

    def call_activity(self, name: str, payload: dict[str, Any]) -> _ActivityTask:
        return _ActivityTask(name=name, payload=payload)

    def wait_for_external_event(self, name: str) -> _EventTask:
        return _EventTask(name=name)


@dataclass
class RunResult:
    """Outcome of a harness run."""

    output: dict[str, Any]
    history: list[tuple[str, str]]
    statuses: list[dict[str, Any]]


_ACTIVITY_DISPATCH = {
    runtime.NODE_ACTIVITY_NAME: runtime.execute_node,
    runtime.ROUTE_ACTIVITY_NAME: runtime.resolve_route,
    runtime.EVENT_ACTIVITY_NAME: runtime.apply_event,
}


def run_graph(
    registry: GraphRegistry,
    *,
    graph_name: str,
    graph_hash: str,
    initial_state: dict[str, Any],
    events: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    max_steps: int = 200,
) -> RunResult:
    """Drive ``runtime.orchestrate`` to completion in-process.

    Activity markers are dispatched to the real async activity functions
    (via :func:`asyncio.run`). ``wait_for_external_event`` markers are resolved
    from *events* (keyed by event name); a missing event raises
    :class:`EventNotDeliveredError`, mirroring a Durable Functions timeout.

    Returns a :class:`RunResult` capturing the final orchestrator output plus an
    ordered ``history`` of ``("activity", name)`` / ``("event", name)`` entries,
    enabling deterministic-replay assertions.
    """
    remaining_events = dict(events or {})
    context = RecordingContext(
        _input={
            "graph_name": graph_name,
            "graph_hash": graph_hash,
            "initial_state": initial_state,
            "metadata": metadata or {},
        }
    )

    gen = runtime.orchestrate(context, registry)
    history: list[tuple[str, str]] = []
    send_value: Any = None
    steps = 0

    while True:
        steps += 1
        if steps > max_steps:  # pragma: no cover - guards against runaway graphs
            gen.close()
            raise RuntimeError(f"orchestration exceeded max_steps={max_steps}")
        try:
            task = gen.send(send_value)
        except StopIteration as done:
            return RunResult(
                output=done.value,
                history=history,
                statuses=context.statuses,
            )

        if isinstance(task, _ActivityTask):
            history.append(("activity", task.name))
            activity = _ACTIVITY_DISPATCH[task.name]
            send_value = asyncio.run(activity(registry, task.payload))
        elif isinstance(task, _EventTask):
            history.append(("event", task.name))
            if task.name not in remaining_events:
                gen.close()
                raise EventNotDeliveredError(
                    f"orchestration waited for external event '{task.name}' "
                    "but it was never delivered"
                )
            send_value = remaining_events.pop(task.name)
        else:  # pragma: no cover - defensive; runtime only yields the two kinds
            raise TypeError(f"unexpected yielded task: {task!r}")
