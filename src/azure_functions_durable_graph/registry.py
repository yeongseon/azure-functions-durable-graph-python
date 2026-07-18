from __future__ import annotations

import inspect
from typing import Any
import warnings

from pydantic import BaseModel

from .contracts import RouteDecision
from .manifest import GraphManifest, GraphRegistration, NodeDefinition


class GraphRegistry:
    """In-memory store for graph registrations.

    .. note::
        This class is **not** thread-safe.  All ``register()`` calls should
        happen during application startup before the host begins accepting
        requests.  Concurrent registration from multiple threads is
        unsupported and may result in inconsistent internal state.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, GraphRegistration[Any]] = {}
        self._by_hash: dict[str, GraphRegistration[Any]] = {}
        self._versions: dict[str, list[str]] = {}

    def _composite_key(self, graph_name: str, graph_hash: str) -> str:
        return f"{graph_name}:{graph_hash}"

    def register(self, registration: GraphRegistration[Any]) -> None:
        graph_name = registration.manifest.graph_name
        graph_hash = registration.manifest.graph_hash
        composite = self._composite_key(graph_name, graph_hash)
        if composite in self._by_hash:
            raise ValueError(f"graph '{graph_name}' with hash '{graph_hash}' is already registered")
        if graph_name in self._registrations:
            warnings.warn(
                f"graph '{graph_name}' re-registered with a new hash '{graph_hash}'; "
                "the latest version now serves new runs (in-flight runs remain "
                "hash-fenced to the version they started with)",
                stacklevel=2,
            )
        self._registrations[graph_name] = registration
        self._by_hash[composite] = registration
        self._versions.setdefault(graph_name, []).append(registration.manifest.version)

    def versions(self, graph_name: str) -> list[str]:
        """Return the registration history (in order) for *graph_name*.

        Useful for operators to notice hot-reloads / multiple registered
        versions of the same graph.  Raises ``KeyError`` for unknown graphs.
        """
        try:
            return list(self._versions[graph_name])
        except KeyError as exc:
            raise KeyError(f"unknown graph '{graph_name}'") from exc

    def list_manifests(self) -> list[dict[str, Any]]:
        return [
            registration.manifest.openapi_schema_fragment()
            for registration in self._registrations.values()
        ]

    def manifest(self, graph_name: str) -> GraphManifest:
        return self.registration(graph_name).manifest

    def registration(self, graph_name: str) -> GraphRegistration[Any]:
        try:
            return self._registrations[graph_name]
        except KeyError as exc:
            raise KeyError(f"unknown graph '{graph_name}'") from exc

    def registration_by_hash(self, graph_name: str, graph_hash: str) -> GraphRegistration[Any]:
        composite = self._composite_key(graph_name, graph_hash)
        try:
            return self._by_hash[composite]
        except KeyError as exc:
            raise KeyError(f"unknown graph '{graph_name}' with hash '{graph_hash}'") from exc

    async def execute_node(
        self,
        graph_name: str,
        graph_hash: str,
        node_name: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        registration = self.registration_by_hash(graph_name, graph_hash)
        node = registration.manifest.nodes[node_name]
        handler = registration.node_handlers[node.handler_name]
        current_state = registration.state_model.model_validate(state)
        result = await _maybe_await(handler(current_state))
        merged = _merge_state(current_state, result, registration.state_model)
        return merged.model_dump(mode="python")

    async def resolve_route(
        self,
        graph_name: str,
        graph_hash: str,
        node_name: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        registration = self.registration_by_hash(graph_name, graph_hash)
        node = registration.manifest.nodes[node_name]
        current_state = registration.state_model.model_validate(state)

        if node.terminal:
            decision = RouteDecision.complete()

        elif node.route_handler_name:
            handler = registration.route_handlers[node.route_handler_name]
            raw = await _maybe_await(handler(current_state))
            decision = _normalize_route_decision(node=node, raw=raw)

        elif node.next_node:
            decision = RouteDecision.next(node.next_node)

        else:
            decision = RouteDecision.complete(note="implicit completion: no outgoing edge")

        # Validate that route decision targets exist in the manifest
        if decision.next_node and decision.next_node not in registration.manifest.nodes:
            raise ValueError(
                f"route decision references unknown node '{decision.next_node}' "
                f"in graph '{graph_name}'"
            )
        if decision.resume_node and decision.resume_node not in registration.manifest.nodes:
            raise ValueError(
                f"route decision references unknown resume_node '{decision.resume_node}' "
                f"in graph '{graph_name}'"
            )

        return decision.model_dump(mode="python")

    async def apply_event(
        self,
        graph_name: str,
        graph_hash: str,
        event_name: str,
        state: dict[str, Any],
        event_payload: Any,
    ) -> dict[str, Any]:
        registration = self.registration_by_hash(graph_name, graph_hash)
        try:
            handler = registration.event_handlers[event_name]
        except KeyError as exc:
            raise KeyError(f"unknown event handler '{event_name}'") from exc

        current_state = registration.state_model.model_validate(state)
        result = await _maybe_await(handler(current_state, event_payload))
        merged = _merge_state(current_state, result, registration.state_model)
        return merged.model_dump(mode="python")


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _merge_state(
    current_state: BaseModel,
    result: BaseModel | dict[str, Any] | None,
    state_model: type[BaseModel],
) -> BaseModel:
    if result is None:
        return current_state

    if isinstance(result, BaseModel):
        return state_model.model_validate(result.model_dump(mode="python"))

    if isinstance(result, dict):
        merged = current_state.model_dump(mode="python")
        merged.update(result)
        return state_model.model_validate(merged)

    raise TypeError(f"unsupported state merge result: {type(result)!r}")


def _normalize_route_decision(
    *,
    node: NodeDefinition,
    raw: RouteDecision | str | dict[str, Any] | None,
) -> RouteDecision:
    if raw is None:
        if node.next_node:
            return RouteDecision.next(node.next_node)
        return RouteDecision.complete(note="route handler returned None")

    if isinstance(raw, RouteDecision):
        return raw

    if isinstance(raw, str):
        if raw == "__complete__":
            return RouteDecision.complete()
        return RouteDecision.next(raw)

    if isinstance(raw, dict):
        return RouteDecision.model_validate(raw)

    raise TypeError(f"unsupported route decision: {type(raw)!r}")
