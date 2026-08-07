"""E2E scenario: external event lifecycle.

Exercises the ``wait_for_external_event`` branch of the orchestrator end to end:

* a graph that waits for an event resumes and applies the event payload when the
  event is delivered;
* a graph that waits for an event that is never delivered raises a timeout;
* cancelling (closing) the generator mid-wait runs no further activities.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel
import pytest

from azure_functions_durable_graph import ManifestBuilder, RouteDecision, runtime
from azure_functions_durable_graph.registry import GraphRegistry

from ._harness import (
    EventNotDeliveredError,
    RecordingContext,
    _ActivityTask,
    _EventTask,
    run_graph,
)


class _ApprovalState(BaseModel):
    value: int = 0
    approved: bool = False


def _start(state: _ApprovalState) -> dict[str, Any]:
    return {"value": state.value + 1}


def _wait_router(state: _ApprovalState) -> RouteDecision:
    if state.approved:
        return RouteDecision.complete()
    return RouteDecision.wait_for_event(event_name="approval", resume_node="finish")


def _finish(state: _ApprovalState) -> dict[str, Any]:
    return {"value": state.value + 100}


def _finish_router(_state: _ApprovalState) -> RouteDecision:
    return RouteDecision.complete()


def _apply_approval(state: _ApprovalState, payload: Any) -> dict[str, Any]:
    return {"approved": bool(payload.get("approved", False))}


def _build_registry() -> tuple[GraphRegistry, Any]:
    builder = ManifestBuilder(graph_name="approval", state_model=_ApprovalState, version="1")
    builder.set_entrypoint("start")
    builder.add_node("start", _start, route=_wait_router, terminal=False)
    builder.add_node("finish", _finish, route=_finish_router, terminal=False)
    builder.add_event_handler("approval", _apply_approval)
    registration = builder.build()

    registry = GraphRegistry()
    registry.register(registration)
    return registry, registration


def test_delivered_event_resumes_and_completes() -> None:
    registry, registration = _build_registry()

    result = run_graph(
        registry,
        graph_name="approval",
        graph_hash=registration.manifest.graph_hash,
        initial_state={"value": 0, "approved": False},
        events={"approval": {"approved": True}},
    )

    # start (+1) → wait → apply event (approved) → finish (+100) → complete.
    assert result.output["final_node"] == "finish"
    assert result.output["state"]["value"] == 101
    assert result.output["state"]["approved"] is True
    assert ("event", "approval") in result.history
    assert ("activity", "afdg_apply_event") in result.history


def test_missing_event_times_out() -> None:
    registry, registration = _build_registry()

    with pytest.raises(EventNotDeliveredError):
        run_graph(
            registry,
            graph_name="approval",
            graph_hash=registration.manifest.graph_hash,
            initial_state={"value": 0, "approved": False},
            events={},  # never deliver the approval event
        )


def test_cancel_mid_wait_runs_no_further_activities() -> None:
    registry, registration = _build_registry()
    graph_hash = registration.manifest.graph_hash

    context = RecordingContext(
        _input={
            "graph_name": "approval",
            "graph_hash": graph_hash,
            "initial_state": {"value": 0, "approved": False},
            "metadata": {},
        }
    )

    gen = runtime.orchestrate(context, registry)

    # Drive the generator by hand up to the external-event wait, dispatching
    # activities against the real activity functions.
    activities_run: list[str] = []
    send_value: Any = None
    while True:
        task = gen.send(send_value)
        if isinstance(task, _EventTask):
            # Reached the wait_for_external_event point.
            break
        assert isinstance(task, _ActivityTask)
        activities_run.append(task.name)
        activity = {
            runtime.NODE_ACTIVITY_NAME: runtime.execute_node,
            runtime.ROUTE_ACTIVITY_NAME: runtime.resolve_route,
        }[task.name]
        send_value = asyncio.run(activity(registry, task.payload))

    # We paused waiting on the 'approval' event without applying it yet.
    assert task.name == "approval"
    assert runtime.EVENT_ACTIVITY_NAME not in activities_run
    activities_before_cancel = list(activities_run)

    # Cancelling the orchestration must not run any further activities.
    gen.close()
    assert activities_run == activities_before_cancel
