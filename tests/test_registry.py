from typing import Any

from pydantic import BaseModel
import pytest

from azure_functions_durable_graph import ManifestBuilder, RouteDecision
from azure_functions_durable_graph.contracts import RouteAction
from azure_functions_durable_graph.manifest import NodeDefinition
from azure_functions_durable_graph.registry import (
    GraphRegistry,
    _merge_state,
    _normalize_route_decision,
)


class DemoState(BaseModel):
    message: str
    approved: bool | None = None
    result: str | None = None


def classify(state: DemoState) -> dict[str, Any]:
    return {}


def route(state: DemoState) -> RouteDecision:
    if state.approved:
        return RouteDecision.next("finish")
    return RouteDecision.wait_for_event(
        event_name="approval",
        resume_node="finish",
    )


def finish(state: DemoState) -> dict[str, str]:
    return {"result": f"done:{state.message}"}


def apply_approval(state: DemoState, payload: Any) -> dict[str, bool]:
    return {"approved": bool(payload["approved"])}


@pytest.fixture()
def registry() -> tuple[GraphRegistry, str]:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("classify")
    builder.add_node("classify", classify, route=route)
    builder.add_event_handler("approval", apply_approval)
    builder.add_node("finish", finish, terminal=True)

    registration = builder.build()
    reg = GraphRegistry()
    reg.register(registration)
    return reg, registration.manifest.graph_hash


@pytest.mark.asyncio
async def test_registry_routes_to_wait_for_event(
    registry: tuple[GraphRegistry, str],
) -> None:
    reg, graph_hash = registry
    decision = await reg.resolve_route("demo", graph_hash, "classify", {"message": "hello"})
    assert decision["action"] == "wait_for_event"
    assert decision["event_name"] == "approval"


@pytest.mark.asyncio
async def test_registry_applies_event(registry: tuple[GraphRegistry, str]) -> None:
    reg, graph_hash = registry
    new_state = await reg.apply_event(
        "demo",
        graph_hash,
        "approval",
        {"message": "hello"},
        {"approved": True},
    )
    assert new_state["approved"] is True


@pytest.mark.asyncio
async def test_registration_by_hash_returns_correct_version(
    registry: tuple[GraphRegistry, str],
) -> None:
    """Verify that registration_by_hash resolves the exact version, not just the latest."""
    reg, graph_hash = registry
    registration = reg.registration_by_hash("demo", graph_hash)
    assert registration.manifest.graph_hash == graph_hash
    assert registration.manifest.graph_name == "demo"


def test_registration_by_hash_unknown_hash_raises() -> None:
    """Verify that an unknown hash raises KeyError."""
    reg = GraphRegistry()
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("classify")
    builder.add_node("classify", classify, next_node="finish")
    builder.add_node("finish", finish, terminal=True)
    reg.register(builder.build())

    with pytest.raises(KeyError, match="unknown graph"):
        reg.registration_by_hash("demo", "nonexistent_hash")


def test_multi_version_registration() -> None:
    """Multiple versions of the same graph should coexist by hash."""
    reg = GraphRegistry()

    builder_v1 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder_v1.set_entrypoint("classify")
    builder_v1.add_node("classify", classify, next_node="finish")
    builder_v1.add_node("finish", finish, terminal=True)
    reg_v1 = builder_v1.build()
    reg.register(reg_v1)
    hash_v1 = reg_v1.manifest.graph_hash

    builder_v2 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="2")
    builder_v2.set_entrypoint("classify")
    builder_v2.add_node("classify", classify, next_node="finish")
    builder_v2.add_node("finish", finish, terminal=True)
    reg_v2 = builder_v2.build()
    reg.register(reg_v2)
    hash_v2 = reg_v2.manifest.graph_hash

    assert hash_v1 != hash_v2
    # Latest by name is v2
    assert reg.manifest("demo").version == "2"
    # But by-hash still resolves v1
    assert reg.registration_by_hash("demo", hash_v1).manifest.version == "1"
    assert reg.registration_by_hash("demo", hash_v2).manifest.version == "2"



# ---------------------------------------------------------------------------
# Direct unit tests for the pure helpers ``_merge_state`` and
# ``_normalize_route_decision``.  These complement the example-driven and
# end-to-end coverage with explicit, isolated assertions on every branch of
# the core state-merge and route-normalization logic (issue #83).
# ---------------------------------------------------------------------------


class MergeState(BaseModel):
    message: str
    approved: bool | None = None
    result: str | None = None


def test_merge_state_none_returns_current_unchanged() -> None:
    current = MergeState(message="hello")
    merged = _merge_state(current, None, MergeState)
    assert merged is current


def test_merge_state_basemodel_replaces_state() -> None:
    current = MergeState(message="hello", approved=True)
    result = MergeState(message="world")
    merged = _merge_state(current, result, MergeState)
    assert isinstance(merged, MergeState)
    assert merged.message == "world"
    # A BaseModel result fully replaces the state, so prior fields reset to
    # their defaults rather than being merged in.
    assert merged.approved is None


def test_merge_state_dict_shallow_merges() -> None:
    current = MergeState(message="hello", approved=True)
    merged = _merge_state(current, {"result": "done"}, MergeState)
    assert isinstance(merged, MergeState)
    assert merged.message == "hello"
    assert merged.approved is True
    assert merged.result == "done"


def test_merge_state_unsupported_type_raises_type_error() -> None:
    current = MergeState(message="hello")
    with pytest.raises(TypeError, match="unsupported state merge result"):
        _merge_state(current, 42, MergeState)  # type: ignore[arg-type]


def _node(*, next_node: str | None = None) -> NodeDefinition:
    return NodeDefinition(
        name="classify",
        handler_name="classify",
        next_node=next_node,
    )


def test_normalize_route_none_with_next_node_routes_next() -> None:
    decision = _normalize_route_decision(node=_node(next_node="finish"), raw=None)
    assert decision.action == RouteAction.NEXT
    assert decision.next_node == "finish"


def test_normalize_route_none_without_next_node_completes() -> None:
    decision = _normalize_route_decision(node=_node(), raw=None)
    assert decision.action == RouteAction.COMPLETE
    assert decision.note == "route handler returned None"


def test_normalize_route_decision_passthrough() -> None:
    raw = RouteDecision.next("finish")
    decision = _normalize_route_decision(node=_node(), raw=raw)
    assert decision is raw


def test_normalize_route_str_complete_sentinel() -> None:
    decision = _normalize_route_decision(node=_node(), raw="__complete__")
    assert decision.action == RouteAction.COMPLETE


def test_normalize_route_str_is_next_node() -> None:
    decision = _normalize_route_decision(node=_node(), raw="finish")
    assert decision.action == RouteAction.NEXT
    assert decision.next_node == "finish"


def test_normalize_route_dict_is_validated() -> None:
    decision = _normalize_route_decision(
        node=_node(),
        raw={"action": "next", "next_node": "finish"},
    )
    assert decision.action == RouteAction.NEXT
    assert decision.next_node == "finish"


def test_normalize_route_unsupported_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="unsupported route decision"):
        _normalize_route_decision(node=_node(), raw=42)  # type: ignore[arg-type]


def test_versions_tracks_registration_history() -> None:
    reg = GraphRegistry()

    builder_v1 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder_v1.set_entrypoint("classify")
    builder_v1.add_node("classify", classify, next_node="finish")
    builder_v1.add_node("finish", finish, terminal=True)
    reg.register(builder_v1.build())

    builder_v2 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="2")
    builder_v2.set_entrypoint("classify")
    builder_v2.add_node("classify", classify, next_node="finish")
    builder_v2.add_node("finish", finish, terminal=True)
    with pytest.warns(UserWarning, match="re-registered with a new hash"):
        reg.register(builder_v2.build())

    assert reg.versions("demo") == ["1", "2"]


def test_versions_unknown_graph_raises() -> None:
    reg = GraphRegistry()
    with pytest.raises(KeyError, match="unknown graph"):
        reg.versions("nope")
