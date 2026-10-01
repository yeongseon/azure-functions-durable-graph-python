from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator

from .contracts import RouteDecision

StateModelT = TypeVar("StateModelT", bound=BaseModel)
NodeHandler = Callable[
    [StateModelT],
    BaseModel | dict[str, Any] | None | Awaitable[BaseModel | dict[str, Any] | None],
]
RouteHandler = Callable[
    [StateModelT],
    RouteDecision
    | str
    | dict[str, Any]
    | None
    | Awaitable[RouteDecision | str | dict[str, Any] | None],
]
EventHandler = Callable[
    [StateModelT, Any],
    BaseModel | dict[str, Any] | None | Awaitable[BaseModel | dict[str, Any] | None],
]


class NodeDefinition(BaseModel):
    name: str
    handler_name: str
    next_node: str | None = None
    route_handler_name: str | None = None
    terminal: bool = False

    @model_validator(mode="after")
    def validate_node(self) -> NodeDefinition:
        if self.terminal and (self.next_node or self.route_handler_name):
            raise ValueError("terminal nodes cannot define next_node or route_handler_name")
        return self


class GraphManifest(BaseModel):
    graph_name: str
    version: str
    graph_hash: str
    state_model_name: str
    entrypoint: str
    nodes: dict[str, NodeDefinition]
    event_handler_names: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def openapi_schema_fragment(self) -> dict[str, Any]:
        return {
            "graph_name": self.graph_name,
            "version": self.version,
            "graph_hash": self.graph_hash,
            "entrypoint": self.entrypoint,
            "state_model_name": self.state_model_name,
            "nodes": list(self.nodes.keys()),
            "events": self.event_handler_names,
        }


@dataclass(slots=True)
class GraphRegistration(Generic[StateModelT]):
    manifest: GraphManifest
    state_model: type[StateModelT]
    node_handlers: dict[str, NodeHandler[StateModelT]] = field(default_factory=dict)
    route_handlers: dict[str, RouteHandler[StateModelT]] = field(default_factory=dict)
    event_handlers: dict[str, EventHandler[StateModelT]] = field(default_factory=dict)


class ManifestBuilder(Generic[StateModelT]):
    def __init__(
        self,
        *,
        graph_name: str,
        state_model: type[StateModelT],
        version: str = "0.1.0",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.graph_name = graph_name
        self.state_model = state_model
        self.version = version
        self.metadata = metadata or {}
        self.entrypoint: str | None = None
        self._nodes: dict[str, NodeDefinition] = {}
        self._node_handlers: dict[str, NodeHandler[StateModelT]] = {}
        self._route_handlers: dict[str, RouteHandler[StateModelT]] = {}
        self._event_handlers: dict[str, EventHandler[StateModelT]] = {}

    def set_entrypoint(self, node_name: str) -> ManifestBuilder[StateModelT]:
        self.entrypoint = node_name
        return self

    def add_node(
        self,
        name: str,
        handler: NodeHandler[StateModelT],
        *,
        next_node: str | None = None,
        route: RouteHandler[StateModelT] | None = None,
        terminal: bool = False,
    ) -> ManifestBuilder[StateModelT]:
        if name in self._nodes:
            raise ValueError(f"duplicate node name '{name}'")
        handler_name = _callable_name(handler)
        if handler_name in self._node_handlers and self._node_handlers[handler_name] is not handler:
            raise ValueError(
                f"handler name '{handler_name}' already registered to a different callable"
            )
        route_name = _callable_name(route) if route else None
        if (
            route_name is not None
            and route_name in self._route_handlers
            and self._route_handlers[route_name] is not route
        ):
            raise ValueError(
                f"route handler name '{route_name}' already registered to a different callable"
            )
        self._nodes[name] = NodeDefinition(
            name=name,
            handler_name=handler_name,
            next_node=next_node,
            route_handler_name=route_name,
            terminal=terminal,
        )
        self._node_handlers[handler_name] = handler
        if route is not None and route_name is not None:
            self._route_handlers[route_name] = route
        return self

    def add_event_handler(
        self,
        event_name: str,
        handler: EventHandler[StateModelT],
    ) -> ManifestBuilder[StateModelT]:
        if event_name in self._event_handlers:
            raise ValueError(f"duplicate event handler for event '{event_name}'")
        self._event_handlers[event_name] = handler
        return self

    def build(self) -> GraphRegistration[StateModelT]:
        if not self.entrypoint:
            raise ValueError("entrypoint must be set before building the manifest")
        if self.entrypoint not in self._nodes:
            raise ValueError("entrypoint must reference a registered node")

        # Validate next_node references
        for name, node in self._nodes.items():
            if node.next_node and node.next_node not in self._nodes:
                raise ValueError(f"node '{name}' references unknown next_node '{node.next_node}'")

        # Validate entrypoint reachability (BFS)
        reachable: set[str] = set()
        queue = [self.entrypoint]
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            reachable.add(current)
            if current not in self._nodes:
                continue
            node = self._nodes[current]
            if node.next_node and node.next_node not in reachable:
                queue.append(node.next_node)
            # If node has a dynamic route handler, all nodes are potential targets
            if node.route_handler_name:
                for candidate in self._nodes:
                    if candidate not in reachable:
                        queue.append(candidate)
        unreachable = set(self._nodes.keys()) - reachable
        if unreachable:
            raise ValueError(
                f"nodes unreachable from entrypoint '{self.entrypoint}': {sorted(unreachable)}"
            )

        metadata = deepcopy(self.metadata)
        manifest_without_hash = {
            "graph_name": self.graph_name,
            "version": self.version,
            "state_model_name": self.state_model.__name__,
            "entrypoint": self.entrypoint,
            "nodes": {
                name: node.model_dump(mode="python") for name, node in sorted(self._nodes.items())
            },
            "event_handler_names": sorted(self._event_handlers.keys()),
            "metadata": metadata,
        }

        canonical = json.dumps(manifest_without_hash, sort_keys=True, separators=(",", ":"))
        graph_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

        manifest = GraphManifest(
            graph_name=self.graph_name,
            version=self.version,
            graph_hash=graph_hash,
            state_model_name=self.state_model.__name__,
            entrypoint=self.entrypoint,
            nodes=self._nodes,
            event_handler_names=sorted(self._event_handlers.keys()),
            metadata=metadata,
        )

        return GraphRegistration(
            manifest=manifest,
            state_model=self.state_model,
            node_handlers=self._node_handlers,
            route_handlers=self._route_handlers,
            event_handlers=self._event_handlers,
        )


def _callable_name(value: Callable[..., Any] | None) -> str:
    if value is None:
        raise ValueError("callable cannot be None")
    module = str(getattr(value, "__module__", "") or "")
    qualname = str(getattr(value, "__qualname__", None) or getattr(value, "__name__", repr(value)))
    return f"{module}.{qualname}" if module else qualname
