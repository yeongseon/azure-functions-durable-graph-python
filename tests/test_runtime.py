"""Direct unit tests for the module-level runtime functions.

These exercise ``runtime.orchestrate`` / ``execute_node`` / ``resolve_route`` /
``apply_event`` without going through the blueprint layer — the whole point of
extracting them out of ``app.py`` closures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pydantic import BaseModel
import pytest

from azure_functions_durable_graph import ManifestBuilder, RouteDecision, runtime
from azure_functions_durable_graph.contracts import (
    EventApplyRequest,
    NodeExecutionRequest,
    RouteResolutionRequest,
)
from azure_functions_durable_graph.registry import GraphRegistry


class _State(BaseModel):
    value: int = 0


def _increment(state: _State) -> dict[str, Any]:
    return {"value": state.value + 1}


def _router(state: _State) -> RouteDecision:
    if state.value >= 3:
        return RouteDecision.complete()
    return RouteDecision.next("inc")


def _event_handler(state: _State, payload: Any) -> dict[str, Any]:
    return {"value": state.value + payload["delta"]}


def _registration() -> Any:
    builder = ManifestBuilder(graph_name="demo", state_model=_State, version="1")
    builder.set_entrypoint("inc")
    builder.add_node("inc", _increment, route=_router, terminal=False)
    builder.add_event_handler("delta", _event_handler)
    return builder.build()


def _registry() -> tuple[GraphRegistry, Any]:
    reg = GraphRegistry()
    registration = _registration()
    reg.register(registration)
    return reg, registration


def _context(registration: Any, *, side_effect: list[Any]) -> MagicMock:
    context = MagicMock()
    context.get_input.return_value = {
        "graph_name": "demo",
        "graph_hash": registration.manifest.graph_hash,
        "initial_state": {"value": 0},
        "metadata": {},
    }
    context.call_activity.side_effect = side_effect
    return context


class TestOrchestrate:
    def test_complete_path_returns_final_state(self) -> None:
        registry, registration = _registry()
        context = _context(registration, side_effect=["exec-call", "route-call"])

        gen = runtime.orchestrate(context, registry)
        assert next(gen) == "exec-call"
        assert gen.send({"value": 1}) == "route-call"
        with pytest.raises(StopIteration) as done:
            gen.send({"action": "complete"})

        output = done.value.value
        assert output["final_node"] == "inc"
        assert output["state"] == {"value": 1}

    def test_next_path_loops(self) -> None:
        registry, registration = _registry()
        context = _context(registration, side_effect=["exec-1", "route-1", "exec-2"])

        gen = runtime.orchestrate(context, registry)
        assert next(gen) == "exec-1"
        assert gen.send({"value": 1}) == "route-1"
        assert gen.send({"action": "next", "next_node": "inc"}) == "exec-2"

    def test_wait_for_event_path(self) -> None:
        registry, registration = _registry()
        context = _context(registration, side_effect=["exec-1", "route-1", "event-apply", "exec-2"])
        context.wait_for_external_event.return_value = "wait-event"

        gen = runtime.orchestrate(context, registry)
        assert next(gen) == "exec-1"
        assert gen.send({"value": 1}) == "route-1"
        assert (
            gen.send({"action": "wait_for_event", "event_name": "approval", "resume_node": "inc"})
            == "wait-event"
        )
        assert gen.send({"approved": True}) == "event-apply"
        assert gen.send({"value": 2}) == "exec-2"



class TestActivities:
    @pytest.mark.asyncio
    async def test_execute_node(self) -> None:
        registry, registration = _registry()
        payload = NodeExecutionRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            node_name="inc",
            state={"value": 4},
        ).model_dump(mode="python")
        result = await runtime.execute_node(registry, payload)
        assert result["value"] == 5

    @pytest.mark.asyncio
    async def test_resolve_route(self) -> None:
        registry, registration = _registry()
        payload = RouteResolutionRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            node_name="inc",
            state={"value": 5},
        ).model_dump(mode="python")
        result = await runtime.resolve_route(registry, payload)
        assert result["action"] == "complete"

    @pytest.mark.asyncio
    async def test_apply_event(self) -> None:
        registry, registration = _registry()
        payload = EventApplyRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            event_name="delta",
            state={"value": 5},
            event_payload={"delta": 2},
        ).model_dump(mode="python")
        result = await runtime.apply_event(registry, payload)
        assert result["value"] == 7

    @pytest.mark.asyncio
    async def test_execute_node_logs_and_reraises(self) -> None:
        registry, registration = _registry()
        payload = NodeExecutionRequest(
            graph_name="demo",
            graph_hash="deadbeefdeadbeef",  # unknown hash → registry raises
            node_name="inc",
            state={"value": 0},
        ).model_dump(mode="python")
        with pytest.raises(KeyError):
            await runtime.execute_node(registry, payload)


def test_status_payload_includes_extra() -> None:
    payload = runtime.build_status_payload(
        "demo", "1", "abc123", "inc", waiting_for_event="approval"
    )
    assert payload["graph_name"] == "demo"
    assert payload["current_node"] == "inc"
    assert payload["waiting_for_event"] == "approval"
