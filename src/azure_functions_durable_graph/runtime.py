"""Testable, module-level orchestrator and activity implementations.

The Durable Functions runtime logic lives here as plain functions so it can be
unit-tested directly with a mocked ``DurableOrchestrationContext`` and a real
:class:`~azure_functions_durable_graph.registry.GraphRegistry`, instead of being
trapped inside blueprint closures. ``app.py`` registers thin wrappers that
forward to these functions.
"""

from __future__ import annotations

from collections.abc import Generator
import logging
from typing import Any

from .contracts import (
    EventApplyRequest,
    NodeExecutionRequest,
    OrchestrationInput,
    RouteAction,
    RouteDecision,
    RouteResolutionRequest,
)
from .registry import GraphRegistry

# Durable Functions trigger names shared between the orchestrator and the
# blueprint registration in ``app.py``. Kept here as the single source of truth.
ORCHESTRATOR_NAME = "afdg_orchestrator"
NODE_ACTIVITY_NAME = "afdg_execute_node"
ROUTE_ACTIVITY_NAME = "afdg_resolve_route"
EVENT_ACTIVITY_NAME = "afdg_apply_event"


def build_status_payload(
    graph_name: str,
    graph_version: str,
    graph_hash: str,
    current_node: str,
    **extra: Any,
) -> dict[str, Any]:
    """Build the orchestration custom-status payload (single source of truth)."""
    payload: dict[str, Any] = {
        "graph_name": graph_name,
        "graph_version": graph_version,
        "graph_hash": graph_hash,
        "current_node": current_node,
    }
    payload.update(extra)
    return payload


def orchestrate(
    context: Any,
    registry: GraphRegistry,
) -> Generator[Any, Any, dict[str, Any]]:
    """Drive a graph run as a Durable Functions orchestration.

    A generator that only yields ``call_activity`` / ``wait_for_external_event``
    tasks — all side-effecting logic runs in activity functions — so it stays
    replay-safe. ``context`` is typed ``Any`` to keep the module importable
    (and unit-testable with a mock) without a hard dependency on the concrete
    ``DurableOrchestrationContext`` type at call sites.
    """
    request = OrchestrationInput.model_validate(context.get_input())
    registration = registry.registration_by_hash(
        request.graph_name,
        request.graph_hash,
    )
    manifest = registration.manifest

    current_node = request.current_node or manifest.entrypoint
    state: dict[str, Any] = request.initial_state

    while True:
        context.set_custom_status(
            build_status_payload(
                request.graph_name,
                manifest.version,
                manifest.graph_hash,
                current_node,
            )
        )

        state = yield context.call_activity(
            NODE_ACTIVITY_NAME,
            NodeExecutionRequest(
                graph_name=request.graph_name,
                graph_hash=request.graph_hash,
                node_name=current_node,
                state=state,
            ).model_dump(mode="python"),
        )

        decision_payload = yield context.call_activity(
            ROUTE_ACTIVITY_NAME,
            RouteResolutionRequest(
                graph_name=request.graph_name,
                graph_hash=request.graph_hash,
                node_name=current_node,
                state=state,
            ).model_dump(mode="python"),
        )
        decision = RouteDecision.model_validate(decision_payload)

        if decision.action == RouteAction.COMPLETE:
            return {
                "graph_name": request.graph_name,
                "graph_version": manifest.version,
                "graph_hash": manifest.graph_hash,
                "final_node": current_node,
                "state": state,
            }

        if decision.action == RouteAction.WAIT_FOR_EVENT:
            context.set_custom_status(
                build_status_payload(
                    request.graph_name,
                    manifest.version,
                    manifest.graph_hash,
                    current_node,
                    waiting_for_event=decision.event_name,
                    resume_node=decision.resume_node,
                )
            )
            event_payload = yield context.wait_for_external_event(decision.event_name)
            state = yield context.call_activity(
                EVENT_ACTIVITY_NAME,
                EventApplyRequest(
                    graph_name=request.graph_name,
                    graph_hash=request.graph_hash,
                    event_name=decision.event_name or "",
                    state=state,
                    event_payload=event_payload,
                ).model_dump(mode="python"),
            )
            current_node = decision.resume_node or current_node
            continue

        if not decision.next_node:  # pragma: no cover - defensive; validation guarantees this
            raise ValueError("route decision with action 'next' must set next_node")

        current_node = decision.next_node


async def execute_node(registry: GraphRegistry, payload: dict[str, Any]) -> dict[str, Any]:
    """Activity: execute a node handler and return the merged state."""
    request = NodeExecutionRequest.model_validate(payload)
    try:
        return await registry.execute_node(
            request.graph_name,
            request.graph_hash,
            request.node_name,
            request.state,
        )
    except Exception:
        logging.exception(
            "execute_node failed: graph=%s hash=%s node=%s",
            request.graph_name,
            request.graph_hash,
            request.node_name,
        )
        raise


async def resolve_route(registry: GraphRegistry, payload: dict[str, Any]) -> dict[str, Any]:
    """Activity: resolve the route decision for a node."""
    request = RouteResolutionRequest.model_validate(payload)
    try:
        return await registry.resolve_route(
            request.graph_name,
            request.graph_hash,
            request.node_name,
            request.state,
        )
    except Exception:
        logging.exception(
            "resolve_route failed: graph=%s hash=%s node=%s",
            request.graph_name,
            request.graph_hash,
            request.node_name,
        )
        raise


async def apply_event(registry: GraphRegistry, payload: dict[str, Any]) -> dict[str, Any]:
    """Activity: apply an external event to the state."""
    request = EventApplyRequest.model_validate(payload)
    try:
        return await registry.apply_event(
            request.graph_name,
            request.graph_hash,
            request.event_name,
            request.state,
            request.event_payload,
        )
    except Exception:
        logging.exception(
            "apply_event failed: graph=%s hash=%s event=%s",
            request.graph_name,
            request.graph_hash,
            request.event_name,
        )
        raise
