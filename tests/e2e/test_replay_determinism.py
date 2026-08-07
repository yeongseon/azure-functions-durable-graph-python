"""E2E scenario: deterministic replay of a graph run.

Drives the real ``runtime.orchestrate`` generator twice against the same
registry and initial state, asserting the final output and the ordered activity
history are byte-for-byte identical — the core replay-safety guarantee of the
Durable Functions orchestrator.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from azure_functions_durable_graph import ManifestBuilder, RouteDecision
from azure_functions_durable_graph.registry import GraphRegistry

from ._harness import run_graph


class _CounterState(BaseModel):
    value: int = 0
    steps: int = 0


def _increment(state: _CounterState) -> dict[str, Any]:
    return {"value": state.value + 1, "steps": state.steps + 1}


def _router(state: _CounterState) -> RouteDecision:
    if state.value >= 3:
        return RouteDecision.complete()
    return RouteDecision.next("inc")


def _build_registry() -> tuple[GraphRegistry, Any]:
    builder = ManifestBuilder(graph_name="counter", state_model=_CounterState, version="1")
    builder.set_entrypoint("inc")
    builder.add_node("inc", _increment, route=_router, terminal=False)
    registration = builder.build()

    registry = GraphRegistry()
    registry.register(registration)
    return registry, registration


def test_replay_is_deterministic() -> None:
    registry, registration = _build_registry()
    graph_hash = registration.manifest.graph_hash

    first = run_graph(
        registry,
        graph_name="counter",
        graph_hash=graph_hash,
        initial_state={"value": 0, "steps": 0},
    )
    second = run_graph(
        registry,
        graph_name="counter",
        graph_hash=graph_hash,
        initial_state={"value": 0, "steps": 0},
    )

    # Identical terminal output.
    assert first.output == second.output
    # Identical ordered activity history (replay determinism).
    assert first.history == second.history

    # And the run actually did the expected work.
    assert first.output["final_node"] == "inc"
    assert first.output["state"] == {"value": 3, "steps": 3}
    assert first.history == [
        ("activity", "afdg_execute_node"),
        ("activity", "afdg_resolve_route"),
        ("activity", "afdg_execute_node"),
        ("activity", "afdg_resolve_route"),
        ("activity", "afdg_execute_node"),
        ("activity", "afdg_resolve_route"),
    ]


def test_custom_status_tracks_current_node() -> None:
    registry, registration = _build_registry()
    result = run_graph(
        registry,
        graph_name="counter",
        graph_hash=registration.manifest.graph_hash,
        initial_state={"value": 0, "steps": 0},
    )

    assert result.statuses, "orchestrator should emit at least one custom status"
    for status in result.statuses:
        assert status["graph_name"] == "counter"
        assert status["current_node"] == "inc"
        assert status["graph_hash"] == registration.manifest.graph_hash
